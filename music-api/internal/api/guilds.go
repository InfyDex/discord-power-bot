package api

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/rasik/discord-power-bot/music-api/internal/httpx"
	"github.com/rasik/discord-power-bot/music-api/internal/player"
)

func guildID(r *http.Request) string { return r.PathValue("guildID") }

func (s *Server) handleListGuilds(w http.ResponseWriter, r *http.Request) {
	guilds, err := s.control.Guilds()
	if err != nil {
		writeControlErr(w, err)
		return
	}
	httpx.JSON(w, http.StatusOK, map[string]any{
		"count":  len(guilds),
		"guilds": guilds,
	})
}

// handlePlayer returns the guild's player as the bot last mirrored it.
func (s *Server) handlePlayer(w http.ResponseWriter, r *http.Request) {
	state, err := s.control.Snapshot(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	httpx.JSON(w, http.StatusOK, state)
}

type playRequest struct {
	Query string `json:"query"`
	// VoiceChannelID is required only when the bot is not already connected in
	// this guild.
	VoiceChannelID string `json:"voice_channel_id"`
	TextChannelID  string `json:"text_channel_id"`
	RequestedBy    string `json:"requested_by"`
}

// handlePlay is the bot's !play / /play. The API resolves the query itself and
// hands the resolved tracks to the bot, which queues and plays them in voice.
func (s *Server) handlePlay(w http.ResponseWriter, r *http.Request) {
	var req playRequest
	if err := httpx.Decode(r, &req); err != nil {
		httpx.Error(w, http.StatusBadRequest, "bad_request", "body must be {\"query\": \"...\"}")
		return
	}
	if strings.TrimSpace(req.Query) == "" {
		httpx.Error(w, http.StatusBadRequest, "missing_query", "query is required")
		return
	}

	d, err := s.control.Play(r.Context(), guildID(r), player.PlayRequest{
		Query:          req.Query,
		VoiceChannelID: req.VoiceChannelID,
		TextChannelID:  req.TextChannelID,
		RequestedBy:    req.RequestedBy,
	})
	if err != nil {
		writeControlErr(w, err)
		return
	}

	s.writeDispatch(w, d, map[string]any{
		"added_count": len(d.Tracks),
		"cached":      s.cachedOnly(d.Tracks),
	})
}

func (s *Server) handleQueue(w http.ResponseWriter, r *http.Request) {
	state, err := s.control.Snapshot(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	httpx.JSON(w, http.StatusOK, map[string]any{
		"guild_id":   state.GuildID,
		"current":    state.Current,
		"queue":      state.Queue,
		"length":     state.QueueLength,
		"loop":       state.Loop,
		"autoplay":   state.Autoplay,
		"bot_online": state.BotOnline,
		"updated_at": state.UpdatedAt,
	})
}

func (s *Server) handleClearQueue(w http.ResponseWriter, r *http.Request) {
	d, err := s.control.ClearQueue(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

// handleRemoveFromQueue drops a 1-based queue position (the bot's !remove).
func (s *Server) handleRemoveFromQueue(w http.ResponseWriter, r *http.Request) {
	position, err := strconv.Atoi(r.PathValue("position"))
	if err != nil {
		httpx.Error(w, http.StatusBadRequest, "invalid_position", "position must be a number")
		return
	}

	d, target, err := s.control.RemoveAt(guildID(r), position)
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, map[string]any{"removing": target})
}

func (s *Server) handleShuffle(w http.ResponseWriter, r *http.Request) {
	d, err := s.control.Shuffle(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

type mixRequest struct {
	VoiceChannelID string `json:"voice_channel_id"`
}

// handleMix asks the bot to shuffle every cached track into a looping queue.
func (s *Server) handleMix(w http.ResponseWriter, r *http.Request) {
	var req mixRequest
	if r.ContentLength > 0 {
		if err := httpx.Decode(r, &req); err != nil {
			httpx.Error(w, http.StatusBadRequest, "bad_request", "body must be {\"voice_channel_id\": \"...\"}")
			return
		}
	}

	d, count, err := s.control.Mix(guildID(r), req.VoiceChannelID)
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, map[string]any{"cached_tracks": count})
}

func (s *Server) handleSkip(w http.ResponseWriter, r *http.Request) {
	d, err := s.control.Skip(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

func (s *Server) handlePause(w http.ResponseWriter, r *http.Request) {
	d, err := s.control.Pause(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

func (s *Server) handleResume(w http.ResponseWriter, r *http.Request) {
	d, err := s.control.Resume(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

func (s *Server) handleStop(w http.ResponseWriter, r *http.Request) {
	d, err := s.control.Stop(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

func (s *Server) handleNowPlaying(w http.ResponseWriter, r *http.Request) {
	state, err := s.control.Snapshot(guildID(r))
	if err != nil {
		writeControlErr(w, err)
		return
	}
	if state.Current == nil {
		httpx.Error(w, http.StatusNotFound, "nothing_playing", "nothing is playing")
		return
	}

	httpx.JSON(w, http.StatusOK, map[string]any{
		"track":            state.Current,
		"status":           state.Status,
		"position_seconds": state.PositionSeconds,
		"volume_percent":   state.VolumePercent,
		"loop":             state.Loop,
		"autoplay":         state.Autoplay,
		"voice_channel_id": state.VoiceChannelID,
		"stream_url":       state.StreamURL,
		"bot_online":       state.BotOnline,
	})
}

type loopRequest struct {
	Mode string `json:"mode"`
}

func (s *Server) handleSetLoop(w http.ResponseWriter, r *http.Request) {
	var req loopRequest
	if err := httpx.Decode(r, &req); err != nil {
		httpx.Error(w, http.StatusBadRequest, "bad_request", "body must be {\"mode\": \"off|track|queue\"}")
		return
	}

	mode, ok := player.ParseLoopMode(req.Mode)
	if !ok {
		httpx.Error(w, http.StatusBadRequest, "invalid_mode", "mode must be one of: off, track, queue")
		return
	}

	d, err := s.control.SetLoop(guildID(r), mode)
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

type volumeRequest struct {
	Percent *int `json:"percent"`
}

func (s *Server) handleSetVolume(w http.ResponseWriter, r *http.Request) {
	var req volumeRequest
	if err := httpx.Decode(r, &req); err != nil || req.Percent == nil {
		httpx.Error(w, http.StatusBadRequest, "bad_request", "body must be {\"percent\": 0-200}")
		return
	}
	if *req.Percent < 0 || *req.Percent > 200 {
		httpx.Error(w, http.StatusBadRequest, "invalid_volume", "percent must be between 0 and 200")
		return
	}

	d, err := s.control.SetVolume(guildID(r), *req.Percent)
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

type autoplayRequest struct {
	Enabled *bool `json:"enabled"`
}

func (s *Server) handleSetAutoplay(w http.ResponseWriter, r *http.Request) {
	var req autoplayRequest
	if err := httpx.Decode(r, &req); err != nil || req.Enabled == nil {
		httpx.Error(w, http.StatusBadRequest, "bad_request", "body must be {\"enabled\": true|false}")
		return
	}

	d, err := s.control.SetAutoplay(guildID(r), req.Enabled)
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

func (s *Server) handleToggleAutoplay(w http.ResponseWriter, r *http.Request) {
	d, err := s.control.SetAutoplay(guildID(r), nil)
	if err != nil {
		writeControlErr(w, err)
		return
	}
	s.writeDispatch(w, d, nil)
}

// handleGuildStream serves the audio of whatever the bot is playing now.
func (s *Server) handleGuildStream(w http.ResponseWriter, r *http.Request) {
	path, ok := s.control.CurrentFile(guildID(r))
	if !ok {
		httpx.Error(w, http.StatusNotFound, "nothing_playing", "nothing is playing, or its audio is not cached")
		return
	}
	s.serveAudio(w, r, path)
}
