// Package config loads server configuration from the environment.
package config

import (
	"os"
	"path/filepath"
	"strconv"
	"time"
)

type Config struct {
	Addr        string
	APIKey      string
	DownloadDir string
	DBPath      string
	CacheLimit  int

	// YTDLPPath overrides yt-dlp discovery; empty means auto-detect.
	YTDLPPath string
	// PlaylistEnd caps how many entries a playlist URL contributes to the queue.
	PlaylistEnd int
	// ResolveTimeout bounds a single yt-dlp metadata call.
	ResolveTimeout time.Duration
	// DownloadTimeout bounds a single yt-dlp download.
	DownloadTimeout time.Duration
}

func Load() Config {
	downloadDir := env("DOWNLOAD_DIR", "downloads")

	return Config{
		Addr:            env("ADDR", ":"+env("PORT", "8080")),
		APIKey:          os.Getenv("API_KEY"),
		DownloadDir:     downloadDir,
		DBPath:          env("DB_PATH", filepath.Join(downloadDir, "tracks.db")),
		CacheLimit:      envInt("CACHE_LIMIT", 1000),
		YTDLPPath:       os.Getenv("YTDLP_PATH"),
		PlaylistEnd:     envInt("PLAYLIST_END", 50),
		ResolveTimeout:  envDuration("RESOLVE_TIMEOUT", 90*time.Second),
		DownloadTimeout: envDuration("DOWNLOAD_TIMEOUT", 10*time.Minute),
	}
}

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

func envDuration(key string, fallback time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return fallback
}
