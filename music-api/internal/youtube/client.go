// Package youtube wraps yt-dlp for metadata resolution and audio downloads,
// backed by the sqlite download registry so a track is fetched at most once.
package youtube

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/rasik/discord-power-bot/music-api/internal/config"
	"github.com/rasik/discord-power-bot/music-api/internal/store"
)

// playerClients matches the Python bot: the mobile clients negotiate formats
// most reliably from server IPs.
const playerClients = "ios,android"

// lockPollInterval is how often to re-check a track another process is
// downloading.
const lockPollInterval = 2 * time.Second

var (
	ErrNotFound   = errors.New("no results")
	videoIDRegexp = regexp.MustCompile(`(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{11})`)
)

// ExtractVideoID pulls an 11-char YouTube video id out of a
// watch/shorts/embed/youtu.be URL, if present.
func ExtractVideoID(url string) string {
	m := videoIDRegexp.FindStringSubmatch(url)
	if m == nil {
		return ""
	}
	return m[1]
}

type Client struct {
	cmd     []string // runnable yt-dlp invocation, e.g. ["yt-dlp"] or ["python", "-m", "yt_dlp"]
	cookies Cookies
	cfg     config.Config
	db      *store.DB
	log     *slog.Logger
	// owner identifies this process in the shared download-lock table.
	owner string

	mu       sync.Mutex
	inflight map[string]*download // one download per video id, shared by all waiters
}

type download struct {
	done chan struct{}
	path string
	err  error
}

func New(cfg config.Config, db *store.DB, log *slog.Logger) (*Client, error) {
	cmd, err := findYTDLP(cfg.YTDLPPath, log)
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(cfg.DownloadDir, 0o755); err != nil {
		return nil, err
	}

	return &Client{
		cmd:      cmd,
		cookies:  ResolveCookies(log),
		cfg:      cfg,
		db:       db,
		log:      log,
		owner:    fmt.Sprintf("api:%d", os.Getpid()),
		inflight: make(map[string]*download),
	}, nil
}

// findYTDLP locates a runnable yt-dlp: explicit override, PATH, the sibling
// Python venv, then `python -m yt_dlp`.
func findYTDLP(override string, log *slog.Logger) ([]string, error) {
	if override != "" {
		return []string{override}, nil
	}
	if found, err := exec.LookPath("yt-dlp"); err == nil {
		return []string{found}, nil
	}

	venvCandidates := []string{
		filepath.Join("..", ".venv", "Scripts", "yt-dlp.exe"),
		filepath.Join("..", ".venv", "bin", "yt-dlp"),
		filepath.Join(".venv", "Scripts", "yt-dlp.exe"),
		filepath.Join(".venv", "bin", "yt-dlp"),
	}
	for _, c := range venvCandidates {
		if _, err := os.Stat(c); err == nil {
			abs, _ := filepath.Abs(c)
			return []string{abs}, nil
		}
	}

	for _, py := range []string{"python", "python3", "py"} {
		if found, err := exec.LookPath(py); err == nil {
			log.Info("yt-dlp binary not found in PATH; falling back to python -m yt_dlp", "python", found)
			return []string{found, "-m", "yt_dlp"}, nil
		}
	}

	return nil, errors.New("yt-dlp not found: install it (pip install yt-dlp) or set YTDLP_PATH")
}

func (c *Client) Cookies() Cookies { return c.cookies }

// ---------- metadata ----------

type entry struct {
	ID         string   `json:"id"`
	Title      string   `json:"title"`
	Duration   *float64 `json:"duration"`
	Thumbnail  string   `json:"thumbnail"`
	WebpageURL string   `json:"webpage_url"`
	URL        string   `json:"url"`
	Thumbnails []struct {
		URL string `json:"url"`
	} `json:"thumbnails"`
	Entries []*entry `json:"entries"`
}

func (e *entry) track() (store.Track, bool) {
	if e == nil || e.ID == "" || e.Title == "" {
		return store.Track{}, false
	}

	t := store.Track{
		ID:         e.ID,
		Title:      e.Title,
		WebpageURL: e.WebpageURL,
		Thumbnail:  e.Thumbnail,
	}
	if e.Duration != nil {
		t.Duration = int(*e.Duration)
	}
	if t.WebpageURL == "" {
		// Flat playlist entries carry the watch URL in `url` and nothing else.
		if strings.HasPrefix(e.URL, "http") {
			t.WebpageURL = e.URL
		} else {
			t.WebpageURL = "https://www.youtube.com/watch?v=" + e.ID
		}
	}
	if t.Thumbnail == "" && len(e.Thumbnails) > 0 {
		t.Thumbnail = e.Thumbnails[len(e.Thumbnails)-1].URL
	}
	return t, true
}

// Search returns up to limit results for a free-text query.
func (c *Client) Search(ctx context.Context, query string, limit int) ([]store.Track, error) {
	if limit < 1 {
		limit = 1
	}
	return c.resolve(ctx, fmt.Sprintf("ytsearch%d:%s", limit, query), false)
}

// Extract resolves a single video or a whole playlist from a URL.
func (c *Client) Extract(ctx context.Context, url string) ([]store.Track, error) {
	return c.resolve(ctx, url, false)
}

// Related returns the first track of the video's auto-generated Mix that is not
// in exclude — the autoplay source when a queue runs dry.
func (c *Client) Related(ctx context.Context, videoID string, exclude map[string]bool) (store.Track, error) {
	url := fmt.Sprintf("https://www.youtube.com/watch?v=%s&list=RD%s", videoID, videoID)

	// Flat extraction: the mix can be hundreds of entries and only the first
	// unseen one is needed, so full per-video extraction would be wasted work.
	tracks, err := c.resolve(ctx, url, true)
	if err != nil {
		return store.Track{}, err
	}
	for _, t := range tracks {
		if !exclude[t.ID] {
			return t, nil
		}
	}
	return store.Track{}, ErrNotFound
}

func (c *Client) resolve(ctx context.Context, target string, flat bool) ([]store.Track, error) {
	ctx, cancel := context.WithTimeout(ctx, c.cfg.ResolveTimeout)
	defer cancel()

	args := []string{
		"-J",
		"--no-warnings",
		"--ignore-errors",
		"--no-check-certificates",
		"--extractor-args", "youtube:player_client=" + playerClients,
		"--playlist-end", fmt.Sprint(c.cfg.PlaylistEnd),
	}
	if flat {
		args = append(args, "--flat-playlist")
	}
	args = append(args, c.cookieArgs()...)
	args = append(args, target)

	out, err := c.run(ctx, args)
	if err != nil {
		return nil, err
	}
	if len(strings.TrimSpace(string(out))) == 0 {
		return nil, ErrNotFound
	}

	var root entry
	if err := json.Unmarshal(out, &root); err != nil {
		return nil, fmt.Errorf("parse yt-dlp output: %w", err)
	}

	if root.Entries == nil {
		t, ok := root.track()
		if !ok {
			return nil, ErrNotFound
		}
		return []store.Track{t}, nil
	}

	var tracks []store.Track
	for _, e := range root.Entries {
		if t, ok := e.track(); ok {
			tracks = append(tracks, t)
		}
	}
	if len(tracks) == 0 {
		return nil, ErrNotFound
	}
	return tracks, nil
}

// LookupCachedURL returns the track for a URL already on disk, without touching
// the network. Playlist URLs always report a miss: resolving only their lead
// video would silently drop the rest of the playlist.
func (c *Client) LookupCachedURL(url string) (store.Track, bool) {
	if strings.Contains(url, "list=") {
		return store.Track{}, false
	}
	videoID := ExtractVideoID(url)
	if videoID == "" {
		return store.Track{}, false
	}

	rec, err := c.db.Get(videoID)
	if err != nil {
		return store.Track{}, false
	}
	if _, err := os.Stat(rec.FilePath); err != nil {
		return store.Track{}, false
	}
	return rec.Track, true
}

// ---------- download ----------

// GetAudioFile returns a local audio path for the track, downloading it only on
// a cache miss. Concurrent callers for the same video share one download —
// within this process via inflight, and across processes (the Discord bot runs
// the same pipeline on the same files) via a lock row in the shared database.
func (c *Client) GetAudioFile(ctx context.Context, t store.Track) (string, error) {
	if path, ok := c.cached(t); ok {
		return path, nil
	}

	c.mu.Lock()
	if d, ok := c.inflight[t.ID]; ok {
		c.mu.Unlock()
		select {
		case <-d.done:
			return d.path, d.err
		case <-ctx.Done():
			return "", ctx.Err()
		}
	}
	d := &download{done: make(chan struct{})}
	c.inflight[t.ID] = d
	c.mu.Unlock()

	d.path, d.err = c.downloadExclusive(ctx, t)
	close(d.done)

	c.mu.Lock()
	delete(c.inflight, t.ID)
	c.mu.Unlock()

	if d.err != nil {
		return "", d.err
	}

	if err := c.db.Upsert(t, d.path); err != nil {
		c.log.Error("could not record download", "video_id", t.ID, "error", err)
	}
	c.recordPlay(t.ID)
	c.evict()
	return d.path, nil
}

// cached returns the on-disk path when the registry has a usable entry, and
// clears rows whose file has gone missing.
func (c *Client) cached(t store.Track) (string, bool) {
	rec, err := c.db.Get(t.ID)
	if err != nil {
		return "", false
	}
	if _, statErr := os.Stat(rec.FilePath); statErr == nil {
		c.recordPlay(t.ID)
		c.log.Info("cache hit", "title", t.Title, "path", rec.FilePath)
		return rec.FilePath, true
	}

	c.log.Warn("registry row points at a missing file, re-downloading", "video_id", t.ID)
	_ = c.db.Delete(t.ID)
	return "", false
}

// downloadExclusive takes the cross-process download lock before shelling out
// to yt-dlp. When another process (the bot) holds it, this waits for that
// download to land in the registry instead of racing it onto the same file.
func (c *Client) downloadExclusive(ctx context.Context, t store.Track) (string, error) {
	for {
		acquired, err := c.db.AcquireDownloadLock(t.ID, c.owner)
		if err != nil {
			return "", fmt.Errorf("acquire download lock: %w", err)
		}
		if acquired {
			defer func() {
				if err := c.db.ReleaseDownloadLock(t.ID, c.owner); err != nil {
					c.log.Warn("could not release download lock", "video_id", t.ID, "error", err)
				}
			}()
			return c.download(ctx, t)
		}

		c.log.Info("another process is downloading this track, waiting", "video_id", t.ID)
		select {
		case <-ctx.Done():
			return "", ctx.Err()
		case <-time.After(lockPollInterval):
		}

		if path, ok := c.cached(t); ok {
			return path, nil
		}
	}
}

func (c *Client) download(ctx context.Context, t store.Track) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, c.cfg.DownloadTimeout)
	defer cancel()

	c.log.Info("yt-dlp download", "title", t.Title, "video_id", t.ID)

	args := []string{
		"--no-playlist",
		"-f", "bestaudio/best",
		"-x", "--audio-format", "mp3", "--audio-quality", "192K",
		"--no-check-certificates",
		"--extractor-args", "youtube:player_client=" + playerClients,
		"-o", filepath.Join(c.cfg.DownloadDir, "%(id)s.%(ext)s"),
	}
	args = append(args, c.cookieArgs()...)
	args = append(args, t.WebpageURL)

	if _, err := c.run(ctx, args); err != nil {
		return "", err
	}

	path, err := c.findDownloaded(t.ID)
	if err != nil {
		return "", err
	}
	return path, nil
}

// findDownloaded locates the produced file: yt-dlp yields .mp3 when ffmpeg is
// available and a native audio format otherwise.
func (c *Client) findDownloaded(videoID string) (string, error) {
	matches, err := filepath.Glob(filepath.Join(c.cfg.DownloadDir, videoID+".*"))
	if err != nil {
		return "", err
	}

	var candidates []string
	for _, m := range matches {
		if strings.HasSuffix(m, ".part") || strings.HasSuffix(m, ".ytdl") {
			continue
		}
		candidates = append(candidates, m)
	}
	if len(candidates) == 0 {
		return "", fmt.Errorf("yt-dlp produced no output file for video_id=%s", videoID)
	}

	sort.SliceStable(candidates, func(i, j int) bool {
		return strings.HasSuffix(candidates[i], ".mp3") && !strings.HasSuffix(candidates[j], ".mp3")
	})
	return candidates[0], nil
}

func (c *Client) recordPlay(videoID string) {
	if err := c.db.RecordPlay(videoID); err != nil {
		c.log.Warn("could not record play", "video_id", videoID, "error", err)
	}
}

// evict trims the registry to the cache limit and deletes the evicted files, so
// the downloads dir stays bounded across the server's lifetime.
func (c *Client) evict() {
	evicted, err := c.db.EvictLRU(c.cfg.CacheLimit)
	if err != nil {
		c.log.Error("cache eviction failed", "error", err)
	}
	for _, e := range evicted {
		if err := os.Remove(e.FilePath); err != nil && !os.IsNotExist(err) {
			c.log.Warn("could not delete evicted file", "path", e.FilePath, "error", err)
			continue
		}
		c.log.Info("cache evicted", "limit", c.cfg.CacheLimit, "path", e.FilePath)
	}
}

// ---------- process plumbing ----------

func (c *Client) cookieArgs() []string {
	switch {
	case c.cookies.File != "":
		return []string{"--cookies", c.cookies.File}
	case c.cookies.FromBrowser != "":
		return []string{"--cookies-from-browser", c.cookies.FromBrowser}
	default:
		return nil
	}
}

func (c *Client) run(ctx context.Context, args []string) ([]byte, error) {
	full := append(append([]string{}, c.cmd[1:]...), args...)
	cmd := exec.CommandContext(ctx, c.cmd[0], full...)

	// Strip the cookie blob so the child never inherits it: it is already on
	// disk and passed via --cookies.
	cmd.Env = filterEnv(os.Environ(), "YOUTUBE_COOKIES_B64")

	var stderr strings.Builder
	cmd.Stderr = &stderr

	out, err := cmd.Output()
	if err != nil {
		msg := strings.TrimSpace(stderr.String())
		if ctx.Err() != nil {
			return nil, fmt.Errorf("yt-dlp timed out: %w", ctx.Err())
		}
		if msg == "" {
			msg = err.Error()
		}
		return nil, fmt.Errorf("yt-dlp failed: %s", msg)
	}
	return out, nil
}

func filterEnv(env []string, drop string) []string {
	out := env[:0:0]
	for _, kv := range env {
		if strings.HasPrefix(kv, drop+"=") {
			continue
		}
		out = append(out, kv)
	}
	return out
}

// ---------- diagnostics ----------

// Diagnostics mirrors the bot's !testmusic command.
type Diagnostics struct {
	YTDLP struct {
		Command   string `json:"command"`
		Available bool   `json:"available"`
		Version   string `json:"version,omitempty"`
		Error     string `json:"error,omitempty"`
	} `json:"ytdlp"`
	FFmpeg struct {
		Available bool   `json:"available"`
		Version   string `json:"version,omitempty"`
		Error     string `json:"error,omitempty"`
	} `json:"ffmpeg"`
	Cookies struct {
		Configured bool   `json:"configured"`
		Source     string `json:"source"`
	} `json:"cookies"`
	Cache struct {
		DownloadDir string `json:"download_dir"`
		Tracks      int    `json:"tracks"`
		Limit       int    `json:"limit"`
	} `json:"cache"`
}

func (c *Client) Diagnostics(ctx context.Context) Diagnostics {
	var d Diagnostics

	d.YTDLP.Command = strings.Join(c.cmd, " ")
	if out, err := c.run(ctx, []string{"--version"}); err == nil {
		d.YTDLP.Available = true
		d.YTDLP.Version = strings.TrimSpace(string(out))
	} else {
		d.YTDLP.Error = err.Error()
	}

	ffmpegCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	if out, err := exec.CommandContext(ffmpegCtx, "ffmpeg", "-version").Output(); err == nil {
		d.FFmpeg.Available = true
		// Trim per line: on Windows the banner lines end with CR.
		d.FFmpeg.Version = strings.TrimSpace(strings.SplitN(string(out), "\n", 2)[0])
	} else {
		d.FFmpeg.Error = "ffmpeg not installed or not in PATH"
	}

	d.Cookies.Configured = c.cookies.Configured()
	d.Cookies.Source = c.cookies.Source()

	d.Cache.DownloadDir = c.cfg.DownloadDir
	d.Cache.Limit = c.cfg.CacheLimit
	if n, err := c.db.Count(); err == nil {
		d.Cache.Tracks = n
	}

	return d
}
