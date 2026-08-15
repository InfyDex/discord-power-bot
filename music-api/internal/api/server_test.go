package api

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"github.com/rasik/discord-power-bot/music-api/internal/config"
	"github.com/rasik/discord-power-bot/music-api/internal/player"
	"github.com/rasik/discord-power-bot/music-api/internal/store"
	"github.com/rasik/discord-power-bot/music-api/internal/youtube"
)

// fakeSource resolves canned tracks so the HTTP layer can be tested without
// yt-dlp or the network.
type fakeSource struct {
	tracks []store.Track
}

func (f *fakeSource) Search(context.Context, string, int) ([]store.Track, error) {
	if len(f.tracks) == 0 {
		return nil, youtube.ErrNotFound
	}
	return f.tracks, nil
}

func (f *fakeSource) Extract(context.Context, string) ([]store.Track, error) {
	return f.tracks, nil
}

func (f *fakeSource) LookupCachedURL(string) (store.Track, bool) { return store.Track{}, false }

func (f *fakeSource) Related(context.Context, string, map[string]bool) (store.Track, error) {
	return store.Track{}, errors.New("none")
}

func (f *fakeSource) GetAudioFile(_ context.Context, t store.Track) (string, error) {
	return "downloads/" + t.ID + ".mp3", nil
}

func (f *fakeSource) Diagnostics(context.Context) youtube.Diagnostics {
	var d youtube.Diagnostics
	d.YTDLP.Available = true
	d.YTDLP.Version = "2026.01.01"
	return d
}

func newTestServer(t *testing.T, apiKey string, tracks ...store.Track) (http.Handler, *store.DB) {
	t.Helper()

	dir := t.TempDir()
	db, err := store.Open(filepath.Join(dir, "tracks.db"))
	if err != nil {
		t.Fatalf("open store: %v", err)
	}
	t.Cleanup(func() { db.Close() })

	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	cfg := config.Config{DownloadDir: dir, CacheLimit: 10, APIKey: apiKey}
	src := &fakeSource{tracks: tracks}

	return NewServer(cfg, player.NewController(src, db, log), src, db, log).Handler(), db
}

func do(t *testing.T, h http.Handler, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()

	var reader io.Reader
	if body != "" {
		reader = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, reader)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func decode(t *testing.T, rec *httptest.ResponseRecorder) map[string]any {
	t.Helper()

	var out map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("decode body %q: %v", rec.Body.String(), err)
	}
	return out
}

func testTrack(id string) store.Track {
	return store.Track{
		ID:         id,
		Title:      "Track " + id,
		Duration:   600,
		WebpageURL: "https://www.youtube.com/watch?v=" + id,
	}
}

// seedBotState fakes what the Python bridge mirrors while the bot is playing.
func seedBotState(t *testing.T, db *store.DB, guildID, status string, current *store.Track, queue []store.Track) {
	t.Helper()

	if err := db.Heartbeat("bot", "test", 1); err != nil {
		t.Fatalf("heartbeat: %v", err)
	}

	state := store.GuildState{
		GuildID:        guildID,
		Status:         status,
		Current:        current,
		LoopMode:       "off",
		VolumePercent:  100,
		VoiceChannelID: "voice-1",
	}
	entries := make([]store.QueueEntry, 0, len(queue))
	for i, tr := range queue {
		entries = append(entries, store.QueueEntry{Track: tr, Position: i + 1, RequestedBy: "tester"})
	}
	if err := db.MirrorGuild(state, entries); err != nil {
		t.Fatalf("mirror guild: %v", err)
	}
}

func TestHealthAndInfo(t *testing.T) {
	h, _ := newTestServer(t, "")

	rec := do(t, h, http.MethodGet, "/health", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("health status = %d", rec.Code)
	}
	if decode(t, rec)["status"] != "ok" {
		t.Fatalf("health body = %s", rec.Body.String())
	}

	rec = do(t, h, http.MethodGet, "/v1/system/info", "")
	body := decode(t, rec)
	if rec.Code != http.StatusOK || body["version"] != Version {
		t.Fatalf("info status = %d body = %s", rec.Code, rec.Body.String())
	}
	if body["bot_online"] != false {
		t.Fatalf("bot_online = %v; want false with no heartbeat", body["bot_online"])
	}
}

func TestWorkersReportsBotHeartbeat(t *testing.T) {
	h, db := newTestServer(t, "")

	rec := do(t, h, http.MethodGet, "/v1/system/workers", "")
	if rec.Code != http.StatusOK || decode(t, rec)["count"] != float64(0) {
		t.Fatalf("empty workers body = %s", rec.Body.String())
	}

	if err := db.Heartbeat("bot", "1.2.3", 2); err != nil {
		t.Fatalf("heartbeat: %v", err)
	}

	rec = do(t, h, http.MethodGet, "/v1/system/workers", "")
	workers := decode(t, rec)["workers"].([]any)
	if len(workers) != 1 {
		t.Fatalf("workers = %v", workers)
	}
	bot := workers[0].(map[string]any)
	if bot["name"] != "bot" || bot["online"] != true {
		t.Fatalf("worker = %v", bot)
	}

	if body := decode(t, do(t, h, http.MethodGet, "/v1/system/info", "")); body["bot_online"] != true {
		t.Fatalf("info bot_online = %v; want true", body["bot_online"])
	}
}

func TestDiagnostics(t *testing.T) {
	h, _ := newTestServer(t, "")

	rec := do(t, h, http.MethodGet, "/v1/system/diagnostics", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d", rec.Code)
	}
	ytdlp, ok := decode(t, rec)["ytdlp"].(map[string]any)
	if !ok || ytdlp["available"] != true {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestAPIKeyGate(t *testing.T) {
	h, _ := newTestServer(t, "s3cret", testTrack("a"))

	// Health stays open so container probes work without the key.
	if rec := do(t, h, http.MethodGet, "/health", ""); rec.Code != http.StatusOK {
		t.Fatalf("health with auth enabled = %d", rec.Code)
	}

	rec := do(t, h, http.MethodGet, "/v1/system/info", "")
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("unauthenticated status = %d; want 401", rec.Code)
	}

	req := httptest.NewRequest(http.MethodGet, "/v1/system/info", nil)
	req.Header.Set("X-API-Key", "s3cret")
	authed := httptest.NewRecorder()
	h.ServeHTTP(authed, req)
	if authed.Code != http.StatusOK {
		t.Fatalf("X-API-Key status = %d", authed.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/v1/system/info", nil)
	req.Header.Set("Authorization", "Bearer s3cret")
	bearer := httptest.NewRecorder()
	h.ServeHTTP(bearer, req)
	if bearer.Code != http.StatusOK {
		t.Fatalf("bearer status = %d", bearer.Code)
	}
}

func TestSearchValidation(t *testing.T) {
	h, _ := newTestServer(t, "", testTrack("s1"))

	if rec := do(t, h, http.MethodGet, "/v1/search", ""); rec.Code != http.StatusBadRequest {
		t.Fatalf("missing q status = %d; want 400", rec.Code)
	}
	if rec := do(t, h, http.MethodGet, "/v1/search?q=x&limit=99", ""); rec.Code != http.StatusBadRequest {
		t.Fatalf("bad limit status = %d; want 400", rec.Code)
	}

	rec := do(t, h, http.MethodGet, "/v1/search?q=some+song", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("search status = %d", rec.Code)
	}
	if got := decode(t, rec)["count"]; got != float64(1) {
		t.Fatalf("count = %v; want 1", got)
	}
}

func TestSearchNoResults(t *testing.T) {
	h, _ := newTestServer(t, "")

	rec := do(t, h, http.MethodGet, "/v1/search?q=nothing", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d; want 404", rec.Code)
	}
}

func TestPlayQueuesCommandForBot(t *testing.T) {
	h, db := newTestServer(t, "", testTrack("p1"))

	rec := do(t, h, http.MethodPost, "/v1/guilds/g1/play",
		`{"query":"a song","voice_channel_id":"voice-1","requested_by":"rasik"}`)
	if rec.Code != http.StatusAccepted {
		t.Fatalf("play status = %d body = %s", rec.Code, rec.Body.String())
	}

	body := decode(t, rec)
	if body["added_count"] != float64(1) {
		t.Fatalf("added_count = %v", body["added_count"])
	}
	if body["bot_online"] != false || body["warning"] == nil {
		t.Fatalf("offline bot should be flagged: %s", rec.Body.String())
	}

	cmd := body["command"].(map[string]any)
	if cmd["action"] != "play" || cmd["status"] != "pending" {
		t.Fatalf("command = %v", cmd)
	}

	// The resolved tracks travel with the command, so the bot does not repeat
	// the yt-dlp work.
	payload := cmd["payload"].(map[string]any)
	tracks := payload["tracks"].([]any)
	if len(tracks) != 1 || tracks[0].(map[string]any)["id"] != "p1" {
		t.Fatalf("payload tracks = %v", tracks)
	}

	pending, err := db.ListCommands("g1", "pending", 10)
	if err != nil || len(pending) != 1 {
		t.Fatalf("pending commands = %v, %v", pending, err)
	}
}

func TestPlayNeedsVoiceChannelWhenBotIsNotConnected(t *testing.T) {
	h, _ := newTestServer(t, "", testTrack("p1"))

	rec := do(t, h, http.MethodPost, "/v1/guilds/g1/play", `{"query":"a song"}`)
	if rec.Code != http.StatusConflict {
		t.Fatalf("status = %d; want 409", rec.Code)
	}
	if decode(t, rec)["error"].(map[string]any)["code"] != "no_voice_channel" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestPlayUsesBotsCurrentVoiceChannel(t *testing.T) {
	h, db := newTestServer(t, "", testTrack("p1"))
	seedBotState(t, db, "g1", "playing", ptr(testTrack("live")), nil)

	rec := do(t, h, http.MethodPost, "/v1/guilds/g1/play", `{"query":"a song"}`)
	if rec.Code != http.StatusAccepted {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}
	if decode(t, rec)["bot_online"] != true {
		t.Fatalf("bot should read as online: %s", rec.Body.String())
	}
}

func TestPlayRequiresQuery(t *testing.T) {
	h, _ := newTestServer(t, "")

	if rec := do(t, h, http.MethodPost, "/v1/guilds/g1/play", `{"query":"  "}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("blank query status = %d; want 400", rec.Code)
	}
	if rec := do(t, h, http.MethodPost, "/v1/guilds/g1/play", `{"nope":1}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("unknown field status = %d; want 400", rec.Code)
	}
}

func TestPlayerReflectsBotMirror(t *testing.T) {
	h, db := newTestServer(t, "")
	seedBotState(t, db, "g1", "playing", ptr(testTrack("live")), []store.Track{testTrack("next1"), testTrack("next2")})

	body := decode(t, do(t, h, http.MethodGet, "/v1/guilds/g1/player", ""))
	if body["status"] != "playing" {
		t.Fatalf("status = %v", body["status"])
	}
	if body["current"].(map[string]any)["id"] != "live" {
		t.Fatalf("current = %v", body["current"])
	}
	if body["queue_length"] != float64(2) {
		t.Fatalf("queue_length = %v", body["queue_length"])
	}
	if body["stream_url"] != "/v1/tracks/live/stream" {
		t.Fatalf("stream_url = %v", body["stream_url"])
	}

	queue := decode(t, do(t, h, http.MethodGet, "/v1/guilds/g1/queue", ""))
	entries := queue["queue"].([]any)
	if len(entries) != 2 || entries[0].(map[string]any)["position"] != float64(1) {
		t.Fatalf("queue = %v", entries)
	}

	guilds := decode(t, do(t, h, http.MethodGet, "/v1/guilds", ""))
	if guilds["count"] != float64(1) {
		t.Fatalf("guild count = %v", guilds["count"])
	}

	np := decode(t, do(t, h, http.MethodGet, "/v1/guilds/g1/nowplaying", ""))
	if np["track"].(map[string]any)["id"] != "live" {
		t.Fatalf("nowplaying = %v", np)
	}
}

func TestControlsOnIdlePlayer(t *testing.T) {
	h, _ := newTestServer(t, "")

	cases := []struct {
		method, path string
		want         int
	}{
		{http.MethodPost, "/v1/guilds/g1/skip", http.StatusConflict},
		{http.MethodPost, "/v1/guilds/g1/pause", http.StatusConflict},
		{http.MethodPost, "/v1/guilds/g1/resume", http.StatusConflict},
		{http.MethodPost, "/v1/guilds/g1/shuffle", http.StatusConflict},
		{http.MethodPost, "/v1/guilds/g1/mix", http.StatusConflict},
		{http.MethodDelete, "/v1/guilds/g1/queue", http.StatusConflict},
		{http.MethodGet, "/v1/guilds/g1/nowplaying", http.StatusNotFound},
		{http.MethodGet, "/v1/guilds/g1/stream", http.StatusNotFound},
		{http.MethodPost, "/v1/guilds/g1/stop", http.StatusAccepted},
	}

	for _, c := range cases {
		if rec := do(t, h, c.method, c.path, ""); rec.Code != c.want {
			t.Errorf("%s %s = %d; want %d (%s)", c.method, c.path, rec.Code, c.want, rec.Body.String())
		}
	}
}

func TestControlsAgainstLivePlayerQueueCommands(t *testing.T) {
	h, db := newTestServer(t, "")
	seedBotState(t, db, "g1", "playing", ptr(testTrack("live")),
		[]store.Track{testTrack("q1"), testTrack("q2")})

	for _, c := range []struct {
		method, path, body, action string
	}{
		{http.MethodPost, "/v1/guilds/g1/skip", "", "skip"},
		{http.MethodPost, "/v1/guilds/g1/pause", "", "pause"},
		{http.MethodPost, "/v1/guilds/g1/shuffle", "", "shuffle"},
		{http.MethodDelete, "/v1/guilds/g1/queue", "", "clear"},
		{http.MethodDelete, "/v1/guilds/g1/queue/2", "", "remove"},
		{http.MethodPut, "/v1/guilds/g1/loop", `{"mode":"queue"}`, "loop"},
		{http.MethodPut, "/v1/guilds/g1/volume", `{"percent":40}`, "volume"},
		{http.MethodPut, "/v1/guilds/g1/autoplay", `{"enabled":true}`, "autoplay"},
		{http.MethodPost, "/v1/guilds/g1/autoplay/toggle", "", "autoplay"},
		{http.MethodPost, "/v1/guilds/g1/stop", "", "stop"},
	} {
		rec := do(t, h, c.method, c.path, c.body)
		if rec.Code != http.StatusAccepted {
			t.Fatalf("%s %s = %d (%s)", c.method, c.path, rec.Code, rec.Body.String())
		}

		body := decode(t, rec)
		cmd := body["command"].(map[string]any)
		if cmd["action"] != c.action {
			t.Errorf("%s %s queued action %v; want %s", c.method, c.path, cmd["action"], c.action)
		}
		if body["bot_online"] != true {
			t.Errorf("%s %s reported bot offline", c.method, c.path)
		}
	}
}

func TestRemoveValidatesAgainstMirroredQueue(t *testing.T) {
	h, db := newTestServer(t, "")
	seedBotState(t, db, "g1", "playing", ptr(testTrack("live")), []store.Track{testTrack("q1")})

	if rec := do(t, h, http.MethodDelete, "/v1/guilds/g1/queue/abc", ""); rec.Code != http.StatusBadRequest {
		t.Fatalf("non-numeric position = %d; want 400", rec.Code)
	}
	if rec := do(t, h, http.MethodDelete, "/v1/guilds/g1/queue/5", ""); rec.Code != http.StatusBadRequest {
		t.Fatalf("out of range position = %d; want 400", rec.Code)
	}

	rec := do(t, h, http.MethodDelete, "/v1/guilds/g1/queue/1", "")
	if rec.Code != http.StatusAccepted {
		t.Fatalf("valid position = %d (%s)", rec.Code, rec.Body.String())
	}
	if decode(t, rec)["removing"].(map[string]any)["id"] != "q1" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestSettingsValidation(t *testing.T) {
	h, _ := newTestServer(t, "")

	if rec := do(t, h, http.MethodPut, "/v1/guilds/g1/loop", `{"mode":"sideways"}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("invalid loop mode = %d; want 400", rec.Code)
	}
	if rec := do(t, h, http.MethodPut, "/v1/guilds/g1/volume", `{"percent":500}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("out of range volume = %d; want 400", rec.Code)
	}
	if rec := do(t, h, http.MethodPut, "/v1/guilds/g1/autoplay", `{}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("missing enabled = %d; want 400", rec.Code)
	}
}

func TestMixRequiresCachedTracks(t *testing.T) {
	h, db := newTestServer(t, "")

	if rec := do(t, h, http.MethodPost, "/v1/guilds/g1/mix", ""); rec.Code != http.StatusConflict {
		t.Fatalf("empty cache mix = %d; want 409", rec.Code)
	}

	if err := db.Upsert(testTrack("c1"), "downloads/c1.mp3"); err != nil {
		t.Fatalf("upsert: %v", err)
	}

	rec := do(t, h, http.MethodPost, "/v1/guilds/g1/mix", `{"voice_channel_id":"voice-9"}`)
	if rec.Code != http.StatusAccepted {
		t.Fatalf("mix = %d (%s)", rec.Code, rec.Body.String())
	}
	if decode(t, rec)["cached_tracks"] != float64(1) {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestCommandLog(t *testing.T) {
	h, db := newTestServer(t, "")
	seedBotState(t, db, "g1", "playing", ptr(testTrack("live")), nil)

	rec := do(t, h, http.MethodPost, "/v1/guilds/g1/skip", "")
	id := int64(decode(t, rec)["command"].(map[string]any)["id"].(float64))

	list := decode(t, do(t, h, http.MethodGet, "/v1/commands?guild_id=g1", ""))
	if list["count"] != float64(1) {
		t.Fatalf("command list = %s", rec.Body.String())
	}

	one := decode(t, do(t, h, http.MethodGet, "/v1/commands/"+strconv.FormatInt(id, 10), ""))
	if one["action"] != "skip" || one["status"] != "pending" {
		t.Fatalf("command = %v", one)
	}

	if got := do(t, h, http.MethodGet, "/v1/commands/999999", ""); got.Code != http.StatusNotFound {
		t.Fatalf("missing command = %d; want 404", got.Code)
	}
	if got := do(t, h, http.MethodGet, "/v1/commands/abc", ""); got.Code != http.StatusBadRequest {
		t.Fatalf("bad id = %d; want 400", got.Code)
	}
}

func TestCacheEndpoints(t *testing.T) {
	h, db := newTestServer(t, "")

	rec := do(t, h, http.MethodGet, "/v1/cache/tracks", "")
	if rec.Code != http.StatusOK || decode(t, rec)["count"] != float64(0) {
		t.Fatalf("empty cache body = %s", rec.Body.String())
	}

	dir := t.TempDir()
	path := filepath.Join(dir, "c1.mp3")
	if err := os.WriteFile(path, []byte("fake audio"), 0o644); err != nil {
		t.Fatalf("write file: %v", err)
	}
	if err := db.Upsert(testTrack("c1"), path); err != nil {
		t.Fatalf("upsert: %v", err)
	}

	rec = do(t, h, http.MethodGet, "/v1/cache/tracks", "")
	if decode(t, rec)["count"] != float64(1) {
		t.Fatalf("cache list body = %s", rec.Body.String())
	}

	rec = do(t, h, http.MethodGet, "/v1/cache/tracks/c1", "")
	if rec.Code != http.StatusOK || decode(t, rec)["on_disk"] != true {
		t.Fatalf("cache get body = %s", rec.Body.String())
	}

	rec = do(t, h, http.MethodGet, "/v1/tracks/c1/stream", "")
	if rec.Code != http.StatusOK || rec.Body.String() != "fake audio" {
		t.Fatalf("stream status = %d body = %q", rec.Code, rec.Body.String())
	}
	if got := rec.Header().Get("Accept-Ranges"); got != "bytes" {
		t.Errorf("Accept-Ranges = %q; want bytes", got)
	}

	rec = do(t, h, http.MethodDelete, "/v1/cache/tracks/c1", "")
	if rec.Code != http.StatusOK || decode(t, rec)["file_removed"] != true {
		t.Fatalf("delete body = %s", rec.Body.String())
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Error("cached file should be gone after delete")
	}

	for _, p := range []string{"/v1/cache/tracks/missing", "/v1/tracks/missing/stream"} {
		if rec := do(t, h, http.MethodGet, p, ""); rec.Code != http.StatusNotFound {
			t.Errorf("GET %s = %d; want 404", p, rec.Code)
		}
	}
	if rec := do(t, h, http.MethodDelete, "/v1/cache/tracks/missing", ""); rec.Code != http.StatusNotFound {
		t.Errorf("delete missing = %d; want 404", rec.Code)
	}
}

func TestGuildStreamServesCurrentTrack(t *testing.T) {
	h, db := newTestServer(t, "")

	dir := t.TempDir()
	path := filepath.Join(dir, "live.mp3")
	if err := os.WriteFile(path, []byte("live audio"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	if err := db.Upsert(testTrack("live"), path); err != nil {
		t.Fatalf("upsert: %v", err)
	}
	seedBotState(t, db, "g1", "playing", ptr(testTrack("live")), nil)

	rec := do(t, h, http.MethodGet, "/v1/guilds/g1/stream", "")
	if rec.Code != http.StatusOK || rec.Body.String() != "live audio" {
		t.Fatalf("stream = %d %q", rec.Code, rec.Body.String())
	}
}

func TestCacheTrackDownloadsUpFront(t *testing.T) {
	h, _ := newTestServer(t, "", testTrack("dl1"))

	rec := do(t, h, http.MethodPost, "/v1/cache/tracks", `{"query":"a song"}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}

	results, ok := decode(t, rec)["results"].([]any)
	if !ok || len(results) != 1 {
		t.Fatalf("body = %s", rec.Body.String())
	}
	if results[0].(map[string]any)["file_path"] != "downloads/dl1.mp3" {
		t.Fatalf("file path = %v", results[0])
	}
}

func TestResolveEndpoint(t *testing.T) {
	h, _ := newTestServer(t, "", testTrack("r1"))

	rec := do(t, h, http.MethodPost, "/v1/resolve", `{"query":"a song"}`)
	if rec.Code != http.StatusOK || decode(t, rec)["count"] != float64(1) {
		t.Fatalf("resolve body = %s", rec.Body.String())
	}
	if rec := do(t, h, http.MethodPost, "/v1/resolve", `{"query":""}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("blank query = %d; want 400", rec.Code)
	}
}

func TestUnknownRouteReturnsJSONError(t *testing.T) {
	h, _ := newTestServer(t, "")

	rec := do(t, h, http.MethodGet, "/v1/nope", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d; want 404", rec.Code)
	}
	errObj, ok := decode(t, rec)["error"].(map[string]any)
	if !ok || errObj["code"] != "not_found" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func ptr(t store.Track) *store.Track { return &t }
