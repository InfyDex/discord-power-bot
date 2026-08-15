package youtube

import (
	"encoding/base64"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
)

// Cookies is the resolved YouTube auth for yt-dlp. At most one field is set.
type Cookies struct {
	File        string // --cookies <file>
	FromBrowser string // --cookies-from-browser <spec>, e.g. "chrome" or "chrome:Profile 1"
}

func (c Cookies) Configured() bool { return c.File != "" || c.FromBrowser != "" }

func (c Cookies) Source() string {
	switch {
	case c.File != "":
		return "file:" + c.File
	case c.FromBrowser != "":
		return "browser:" + c.FromBrowser
	default:
		return "none"
	}
}

// ResolveCookies mirrors the Python bot's priority order:
// YOUTUBE_COOKIES_B64 > YOUTUBE_COOKIES_FILE > cookies.txt next to the server
// or in its parent dir > COOKIES_FROM_BROWSER.
//
// The browser option only works when the server runs on the same machine as the
// browser, so it is last — servers should use a file.
func ResolveCookies(log *slog.Logger) Cookies {
	if b64 := os.Getenv("YOUTUBE_COOKIES_B64"); b64 != "" {
		if c, err := writeCookiesFromBase64(b64); err == nil {
			// Drop the blob from the env now that it is on disk: every child
			// process would otherwise inherit it and can hit E2BIG, since the
			// argument-length limit counts the environment too.
			os.Unsetenv("YOUTUBE_COOKIES_B64")
			log.Info("youtube cookies loaded", "source", "YOUTUBE_COOKIES_B64", "path", c.File)
			return c
		} else {
			log.Warn("failed to decode YOUTUBE_COOKIES_B64", "error", err)
		}
	}

	if path := os.Getenv("YOUTUBE_COOKIES_FILE"); path != "" {
		if _, err := os.Stat(path); err == nil {
			log.Info("youtube cookies loaded", "source", "YOUTUBE_COOKIES_FILE", "path", path)
			return Cookies{File: path}
		}
		log.Warn("YOUTUBE_COOKIES_FILE does not exist", "path", path)
	}

	for _, candidate := range []string{"cookies.txt", filepath.Join("..", "cookies.txt")} {
		if _, err := os.Stat(candidate); err == nil {
			abs, _ := filepath.Abs(candidate)
			log.Info("youtube cookies loaded", "source", "cookies.txt", "path", abs)
			return Cookies{File: abs}
		}
	}

	if browser := os.Getenv("COOKIES_FROM_BROWSER"); browser != "" {
		log.Info("youtube cookies loaded", "source", "COOKIES_FROM_BROWSER", "spec", browser)
		return Cookies{FromBrowser: strings.TrimSpace(browser)}
	}

	log.Warn("no youtube cookies configured; downloads may fail with 403 on server IPs. " +
		"Set YOUTUBE_COOKIES_B64, YOUTUBE_COOKIES_FILE, place cookies.txt next to the server, " +
		"or set COOKIES_FROM_BROWSER=chrome (local use only)")
	return Cookies{}
}

func writeCookiesFromBase64(b64 string) (Cookies, error) {
	data, err := base64.StdEncoding.DecodeString(strings.TrimSpace(b64))
	if err != nil {
		return Cookies{}, fmt.Errorf("base64 decode: %w", err)
	}

	f, err := os.CreateTemp("", "yt-cookies-*.txt")
	if err != nil {
		return Cookies{}, err
	}
	defer f.Close()

	if _, err := f.Write(data); err != nil {
		return Cookies{}, err
	}
	return Cookies{File: f.Name()}, nil
}
