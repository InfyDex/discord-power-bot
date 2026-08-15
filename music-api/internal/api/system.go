package api

import (
	"net/http"
	"runtime"
	"time"

	"github.com/rasik/discord-power-bot/music-api/internal/httpx"
	"github.com/rasik/discord-power-bot/music-api/internal/player"
)

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	httpx.JSON(w, http.StatusOK, map[string]any{
		"status":  "ok",
		"version": Version,
	})
}

// handleInfo is the bot's !info / !uptime / !ping rolled into one payload,
// reported across both processes sharing the database.
func (s *Server) handleInfo(w http.ResponseWriter, r *http.Request) {
	guilds, err := s.control.Guilds()
	if err != nil {
		writeControlErr(w, err)
		return
	}

	playing := 0
	queued := 0
	for _, g := range guilds {
		if g.Status == player.StatusPlaying {
			playing++
		}
		queued += g.QueueLength
	}

	cached, err := s.db.Count()
	if err != nil {
		s.log.Warn("could not count cached tracks", "error", err)
	}
	botOnline, err := s.db.BotOnline()
	if err != nil {
		s.log.Warn("could not read bot heartbeat", "error", err)
	}
	pending, err := s.db.ListCommands("", "pending", 200)
	if err != nil {
		s.log.Warn("could not list pending commands", "error", err)
	}

	uptime := time.Since(s.started)
	httpx.JSON(w, http.StatusOK, map[string]any{
		"version":          Version,
		"go_version":       runtime.Version(),
		"uptime_seconds":   int(uptime.Seconds()),
		"uptime":           uptime.Round(time.Second).String(),
		"bot_online":       botOnline,
		"guilds":           len(guilds),
		"players_active":   playing,
		"queued_tracks":    queued,
		"pending_commands": len(pending),
		"cached_tracks":    cached,
		"cache_limit":      s.cfg.CacheLimit,
		"download_dir":     s.cfg.DownloadDir,
		"database":         s.cfg.DBPath,
	})
}

// handleDiagnostics is the bot's !testmusic: are yt-dlp, ffmpeg and cookies usable.
func (s *Server) handleDiagnostics(w http.ResponseWriter, r *http.Request) {
	httpx.JSON(w, http.StatusOK, s.yt.Diagnostics(r.Context()))
}

// handleWorkers shows which processes share this database and when each last
// checked in — the quickest way to see whether the bot is up.
func (s *Server) handleWorkers(w http.ResponseWriter, r *http.Request) {
	workers, err := s.db.ListWorkers()
	if err != nil {
		writeControlErr(w, err)
		return
	}
	httpx.JSON(w, http.StatusOK, map[string]any{
		"count":   len(workers),
		"workers": workers,
	})
}
