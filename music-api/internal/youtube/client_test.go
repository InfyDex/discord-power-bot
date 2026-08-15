package youtube

import (
	"encoding/base64"
	"encoding/json"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/rasik/discord-power-bot/music-api/internal/config"
)

func discardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func TestExtractVideoID(t *testing.T) {
	cases := map[string]string{
		"https://www.youtube.com/watch?v=dQw4w9WgXcQ":         "dQw4w9WgXcQ",
		"https://youtu.be/dQw4w9WgXcQ":                        "dQw4w9WgXcQ",
		"https://www.youtube.com/shorts/dQw4w9WgXcQ":          "dQw4w9WgXcQ",
		"https://www.youtube.com/embed/dQw4w9WgXcQ":           "dQw4w9WgXcQ",
		"https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RD": "dQw4w9WgXcQ",
		"https://example.com/watch?v=dQw4w9WgXcQ":             "",
		"not a url": "",
	}

	for url, want := range cases {
		if got := ExtractVideoID(url); got != want {
			t.Errorf("ExtractVideoID(%q) = %q; want %q", url, got, want)
		}
	}
}

func TestEntryToTrack(t *testing.T) {
	duration := 215.7
	raw := `{
		"id": "abc12345678",
		"title": "Some Song",
		"duration": 215.7,
		"webpage_url": "https://www.youtube.com/watch?v=abc12345678",
		"thumbnail": "https://img/large.jpg"
	}`

	var e entry
	if err := json.Unmarshal([]byte(raw), &e); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	tr, ok := e.track()
	if !ok {
		t.Fatal("track() reported not ok for a complete entry")
	}
	if tr.Duration != int(duration) {
		t.Errorf("duration = %d; want %d", tr.Duration, int(duration))
	}
	if tr.Thumbnail != "https://img/large.jpg" {
		t.Errorf("thumbnail = %q", tr.Thumbnail)
	}
}

func TestEntryToTrackFillsMissingFields(t *testing.T) {
	// A flat-playlist entry: no webpage_url, no duration, thumbnails list only.
	raw := `{
		"id": "flat1234567",
		"title": "Flat Entry",
		"thumbnails": [{"url": "https://img/small.jpg"}, {"url": "https://img/big.jpg"}]
	}`

	var e entry
	if err := json.Unmarshal([]byte(raw), &e); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	tr, ok := e.track()
	if !ok {
		t.Fatal("track() reported not ok")
	}
	if tr.WebpageURL != "https://www.youtube.com/watch?v=flat1234567" {
		t.Errorf("webpage url = %q; want a synthesized watch URL", tr.WebpageURL)
	}
	if tr.Thumbnail != "https://img/big.jpg" {
		t.Errorf("thumbnail = %q; want the last (largest) thumbnail", tr.Thumbnail)
	}
	if tr.Duration != 0 {
		t.Errorf("duration = %d; want 0 when absent", tr.Duration)
	}
}

func TestEntryToTrackRejectsIncomplete(t *testing.T) {
	var nilEntry *entry
	if _, ok := nilEntry.track(); ok {
		t.Error("nil entry should not produce a track")
	}
	if _, ok := (&entry{Title: "no id"}).track(); ok {
		t.Error("entry without an id should not produce a track")
	}
	if _, ok := (&entry{ID: "no title"}).track(); ok {
		t.Error("entry without a title should not produce a track")
	}
}

func TestFindDownloadedPrefersMP3(t *testing.T) {
	dir := t.TempDir()
	c := &Client{cfg: config.Config{DownloadDir: dir}, log: discardLogger()}

	for _, name := range []string{"vid.webm", "vid.mp3", "vid.mp3.part"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o644); err != nil {
			t.Fatalf("write %s: %v", name, err)
		}
	}

	path, err := c.findDownloaded("vid")
	if err != nil {
		t.Fatalf("findDownloaded: %v", err)
	}
	if filepath.Base(path) != "vid.mp3" {
		t.Fatalf("picked %q; want vid.mp3", filepath.Base(path))
	}
}

func TestFindDownloadedIgnoresPartials(t *testing.T) {
	dir := t.TempDir()
	c := &Client{cfg: config.Config{DownloadDir: dir}, log: discardLogger()}

	if err := os.WriteFile(filepath.Join(dir, "vid.mp3.part"), []byte("x"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}

	if _, err := c.findDownloaded("vid"); err == nil {
		t.Fatal("a .part file alone should not count as a download")
	}
}

func TestFilterEnvDropsCookieBlob(t *testing.T) {
	env := []string{"PATH=/usr/bin", "YOUTUBE_COOKIES_B64=abc", "HOME=/root"}

	got := filterEnv(env, "YOUTUBE_COOKIES_B64")
	if len(got) != 2 {
		t.Fatalf("got %d entries; want 2", len(got))
	}
	for _, kv := range got {
		if strings.HasPrefix(kv, "YOUTUBE_COOKIES_B64=") {
			t.Fatal("cookie blob survived filtering")
		}
	}
}

func TestResolveCookiesPrefersBase64(t *testing.T) {
	t.Setenv("YOUTUBE_COOKIES_B64", base64.StdEncoding.EncodeToString([]byte("# Netscape HTTP Cookie File\n")))
	t.Setenv("YOUTUBE_COOKIES_FILE", "")
	t.Setenv("COOKIES_FROM_BROWSER", "")

	c := ResolveCookies(discardLogger())
	if c.File == "" {
		t.Fatal("expected a cookie file written from the base64 blob")
	}
	t.Cleanup(func() { os.Remove(c.File) })

	data, err := os.ReadFile(c.File)
	if err != nil {
		t.Fatalf("read cookie file: %v", err)
	}
	if !strings.HasPrefix(string(data), "# Netscape") {
		t.Fatalf("cookie file content = %q", string(data))
	}

	// The blob must be cleared from the env so children don't inherit it.
	if os.Getenv("YOUTUBE_COOKIES_B64") != "" {
		t.Error("YOUTUBE_COOKIES_B64 should be unset after being written to disk")
	}
	if !c.Configured() || !strings.HasPrefix(c.Source(), "file:") {
		t.Errorf("source = %q, configured = %v", c.Source(), c.Configured())
	}
}

func TestResolveCookiesFallsBackToBrowser(t *testing.T) {
	dir := t.TempDir()
	t.Chdir(dir) // no cookies.txt here

	t.Setenv("YOUTUBE_COOKIES_B64", "")
	t.Setenv("YOUTUBE_COOKIES_FILE", "")
	t.Setenv("COOKIES_FROM_BROWSER", "chrome:Profile 1")

	c := ResolveCookies(discardLogger())
	if c.FromBrowser != "chrome:Profile 1" {
		t.Fatalf("from browser = %q", c.FromBrowser)
	}
	if c.Source() != "browser:chrome:Profile 1" {
		t.Fatalf("source = %q", c.Source())
	}
}

func TestResolveCookiesNoneConfigured(t *testing.T) {
	t.Chdir(t.TempDir())
	t.Setenv("YOUTUBE_COOKIES_B64", "")
	t.Setenv("YOUTUBE_COOKIES_FILE", "")
	t.Setenv("COOKIES_FROM_BROWSER", "")

	c := ResolveCookies(discardLogger())
	if c.Configured() || c.Source() != "none" {
		t.Fatalf("expected no cookies, got %+v", c)
	}
}

func TestCookieArgs(t *testing.T) {
	fileClient := &Client{cookies: Cookies{File: "/tmp/c.txt"}}
	if got := strings.Join(fileClient.cookieArgs(), " "); got != "--cookies /tmp/c.txt" {
		t.Errorf("file args = %q", got)
	}

	browserClient := &Client{cookies: Cookies{FromBrowser: "chrome"}}
	if got := strings.Join(browserClient.cookieArgs(), " "); got != "--cookies-from-browser chrome" {
		t.Errorf("browser args = %q", got)
	}

	if args := (&Client{}).cookieArgs(); args != nil {
		t.Errorf("unconfigured cookies should add no args, got %v", args)
	}
}
