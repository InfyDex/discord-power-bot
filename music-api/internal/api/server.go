// Package api wires the HTTP surface: one endpoint per bot command.
package api

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"time"

	"github.com/rasik/discord-power-bot/music-api/internal/config"
	"github.com/rasik/discord-power-bot/music-api/internal/httpx"
	"github.com/rasik/discord-power-bot/music-api/internal/player"
	"github.com/rasik/discord-power-bot/music-api/internal/store"
	"github.com/rasik/discord-power-bot/music-api/internal/youtube"
)

// Version is stamped into /v1/system/info and the worker heartbeat.
const Version = "1.0.0"

// Source is what the handlers need from the yt-dlp layer: everything the
// controller uses, plus the diagnostics probe. *youtube.Client implements it.
type Source interface {
	player.Source
	Diagnostics(ctx context.Context) youtube.Diagnostics
}

type Server struct {
	cfg     config.Config
	control *player.Controller
	yt      Source
	db      *store.DB
	log     *slog.Logger
	started time.Time
}

func NewServer(cfg config.Config, c *player.Controller, yt Source, db *store.DB, log *slog.Logger) *Server {
	return &Server{
		cfg:     cfg,
		control: c,
		yt:      yt,
		db:      db,
		log:     log,
		started: time.Now(),
	}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()

	// system
	mux.HandleFunc("GET /health", s.handleHealth)
	mux.HandleFunc("GET /v1/system/info", s.handleInfo)
	mux.HandleFunc("GET /v1/system/diagnostics", s.handleDiagnostics)
	mux.HandleFunc("GET /v1/system/workers", s.handleWorkers)

	// resolution
	mux.HandleFunc("GET /v1/search", s.handleSearch)
	mux.HandleFunc("POST /v1/resolve", s.handleResolve)

	// guild players — control calls are queued for the bot to execute
	mux.HandleFunc("GET /v1/guilds", s.handleListGuilds)
	mux.HandleFunc("GET /v1/guilds/{guildID}/player", s.handlePlayer)
	mux.HandleFunc("POST /v1/guilds/{guildID}/play", s.handlePlay)
	mux.HandleFunc("GET /v1/guilds/{guildID}/queue", s.handleQueue)
	mux.HandleFunc("DELETE /v1/guilds/{guildID}/queue", s.handleClearQueue)
	mux.HandleFunc("DELETE /v1/guilds/{guildID}/queue/{position}", s.handleRemoveFromQueue)
	mux.HandleFunc("POST /v1/guilds/{guildID}/shuffle", s.handleShuffle)
	mux.HandleFunc("POST /v1/guilds/{guildID}/mix", s.handleMix)
	mux.HandleFunc("POST /v1/guilds/{guildID}/skip", s.handleSkip)
	mux.HandleFunc("POST /v1/guilds/{guildID}/pause", s.handlePause)
	mux.HandleFunc("POST /v1/guilds/{guildID}/resume", s.handleResume)
	mux.HandleFunc("POST /v1/guilds/{guildID}/stop", s.handleStop)
	mux.HandleFunc("GET /v1/guilds/{guildID}/nowplaying", s.handleNowPlaying)
	mux.HandleFunc("PUT /v1/guilds/{guildID}/loop", s.handleSetLoop)
	mux.HandleFunc("PUT /v1/guilds/{guildID}/volume", s.handleSetVolume)
	mux.HandleFunc("PUT /v1/guilds/{guildID}/autoplay", s.handleSetAutoplay)
	mux.HandleFunc("POST /v1/guilds/{guildID}/autoplay/toggle", s.handleToggleAutoplay)
	mux.HandleFunc("GET /v1/guilds/{guildID}/stream", s.handleGuildStream)

	// command log — what the API asked the bot to do, and how it went
	mux.HandleFunc("GET /v1/commands", s.handleListCommands)
	mux.HandleFunc("GET /v1/commands/{id}", s.handleGetCommand)

	// download cache
	mux.HandleFunc("GET /v1/cache/tracks", s.handleListCache)
	mux.HandleFunc("POST /v1/cache/tracks", s.handleCacheTrack)
	mux.HandleFunc("GET /v1/cache/tracks/{videoID}", s.handleGetCachedTrack)
	mux.HandleFunc("DELETE /v1/cache/tracks/{videoID}", s.handleDeleteCachedTrack)
	mux.HandleFunc("GET /v1/tracks/{videoID}/stream", s.handleTrackStream)

	mux.HandleFunc("/", s.handleNotFound)

	return httpx.Chain(mux,
		httpx.Recover(s.log),
		httpx.Logger(s.log),
		httpx.APIKey(s.cfg.APIKey, "/health"),
	)
}

func (s *Server) handleNotFound(w http.ResponseWriter, r *http.Request) {
	httpx.Error(w, http.StatusNotFound, "not_found", "no route for "+r.Method+" "+r.URL.Path)
}

// writeDispatch is the common answer for a control call: the queued command and
// whether the bot is alive to run it.
func (s *Server) writeDispatch(w http.ResponseWriter, d player.Dispatch, extra map[string]any) {
	body := map[string]any{
		"command":    d.Command,
		"bot_online": d.BotOnline,
	}
	if !d.BotOnline {
		body["warning"] = "the Discord bot is offline; the command stays pending until it comes back"
	}
	if d.Tracks != nil {
		body["tracks"] = d.Tracks
	}
	for k, v := range extra {
		body[k] = v
	}
	httpx.JSON(w, http.StatusAccepted, body)
}

// writeControlErr maps controller errors onto HTTP status codes.
func writeControlErr(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, player.ErrNothingPlaying):
		httpx.Error(w, http.StatusConflict, "nothing_playing", err.Error())
	case errors.Is(err, player.ErrNotPaused):
		httpx.Error(w, http.StatusConflict, "not_paused", err.Error())
	case errors.Is(err, player.ErrAlreadyPaused):
		httpx.Error(w, http.StatusConflict, "already_paused", err.Error())
	case errors.Is(err, player.ErrEmptyQueue):
		httpx.Error(w, http.StatusConflict, "queue_empty", err.Error())
	case errors.Is(err, player.ErrQueueTooShort):
		httpx.Error(w, http.StatusConflict, "queue_too_short", err.Error())
	case errors.Is(err, player.ErrNoCached):
		httpx.Error(w, http.StatusConflict, "no_cached_tracks", err.Error()+" — play something first")
	case errors.Is(err, player.ErrNoVoiceChannel):
		httpx.Error(w, http.StatusConflict, "no_voice_channel", err.Error())
	case errors.Is(err, player.ErrInvalidPos):
		httpx.Error(w, http.StatusBadRequest, "invalid_position", err.Error())
	case errors.Is(err, player.ErrNoResults), errors.Is(err, youtube.ErrNotFound):
		httpx.Error(w, http.StatusNotFound, "no_results", err.Error())
	case errors.Is(err, store.ErrNotFound):
		httpx.Error(w, http.StatusNotFound, "not_found", err.Error())
	default:
		httpx.Error(w, http.StatusBadGateway, "upstream_error", err.Error())
	}
}
