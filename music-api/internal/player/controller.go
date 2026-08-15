// Package player is the API's half of the shared control plane: it reads the
// player state the Discord bot mirrors into sqlite, and hands the bot commands
// to execute. The bot owns the voice connection, so it does the playing; the
// API resolves queries, manages the download cache, and drives the bot.
package player

import (
	"context"
	"errors"
	"log/slog"
	"strings"

	"github.com/rasik/discord-power-bot/music-api/internal/store"
)

type LoopMode string

const (
	LoopOff   LoopMode = "off"
	LoopTrack LoopMode = "track"
	LoopQueue LoopMode = "queue"
)

func ParseLoopMode(s string) (LoopMode, bool) {
	switch LoopMode(s) {
	case LoopOff, LoopTrack, LoopQueue:
		return LoopMode(s), true
	default:
		return "", false
	}
}

// Playback statuses the bot mirrors.
const (
	StatusIdle    = "idle"
	StatusLoading = "loading"
	StatusPlaying = "playing"
	StatusPaused  = "paused"
)

var (
	ErrNothingPlaying = errors.New("nothing is playing")
	ErrNotPaused      = errors.New("playback is not paused")
	ErrAlreadyPaused  = errors.New("playback is already paused")
	ErrEmptyQueue     = errors.New("queue is empty")
	ErrQueueTooShort  = errors.New("not enough tracks in queue to shuffle")
	ErrInvalidPos     = errors.New("invalid queue position")
	ErrNoCached       = errors.New("no cached tracks yet")
	ErrNoResults      = errors.New("no results for query")
	ErrNoVoiceChannel = errors.New("bot is not in a voice channel; pass voice_channel_id")
)

// Source is the metadata + audio provider (the yt-dlp client).
type Source interface {
	Search(ctx context.Context, query string, limit int) ([]store.Track, error)
	Extract(ctx context.Context, url string) ([]store.Track, error)
	Related(ctx context.Context, videoID string, exclude map[string]bool) (store.Track, error)
	LookupCachedURL(url string) (store.Track, bool)
	GetAudioFile(ctx context.Context, t store.Track) (string, error)
}

// Controller turns HTTP calls into shared-database writes.
type Controller struct {
	yt  Source
	db  *store.DB
	log *slog.Logger
}

func NewController(yt Source, db *store.DB, log *slog.Logger) *Controller {
	return &Controller{yt: yt, db: db, log: log}
}

// Snapshot is the merged view of one guild: mirrored state plus mirrored queue.
type Snapshot struct {
	GuildID          string             `json:"guild_id"`
	Status           string             `json:"status"`
	Current          *store.Track       `json:"current"`
	PositionSeconds  int                `json:"position_seconds"`
	Queue            []store.QueueEntry `json:"queue"`
	QueueLength      int                `json:"queue_length"`
	Loop             string             `json:"loop"`
	Autoplay         bool               `json:"autoplay"`
	VolumePercent    int                `json:"volume_percent"`
	VoiceChannelID   string             `json:"voice_channel_id,omitempty"`
	VoiceChannelName string             `json:"voice_channel_name,omitempty"`
	BotOnline        bool               `json:"bot_online"`
	UpdatedAt        string             `json:"updated_at,omitempty"`
	StreamURL        string             `json:"stream_url,omitempty"`
}

func (c *Controller) Snapshot(guildID string) (Snapshot, error) {
	state, err := c.db.GetGuildState(guildID)
	if err != nil {
		return Snapshot{}, err
	}
	queue, err := c.db.GetQueue(guildID)
	if err != nil {
		return Snapshot{}, err
	}
	online, err := c.db.BotOnline()
	if err != nil {
		return Snapshot{}, err
	}
	return snapshotFrom(state, queue, online), nil
}

func snapshotFrom(state store.GuildState, queue []store.QueueEntry, botOnline bool) Snapshot {
	s := Snapshot{
		GuildID:          state.GuildID,
		Status:           state.Status,
		Current:          state.Current,
		PositionSeconds:  state.PositionSeconds,
		Queue:            queue,
		QueueLength:      len(queue),
		Loop:             state.LoopMode,
		Autoplay:         state.Autoplay,
		VolumePercent:    state.VolumePercent,
		VoiceChannelID:   state.VoiceChannelID,
		VoiceChannelName: state.VoiceChannelName,
		BotOnline:        botOnline,
		UpdatedAt:        state.UpdatedAt,
	}
	if state.Current != nil {
		s.StreamURL = "/v1/tracks/" + state.Current.ID + "/stream"
	}
	return s
}

func (c *Controller) Guilds() ([]Snapshot, error) {
	states, err := c.db.ListGuildStates()
	if err != nil {
		return nil, err
	}
	online, err := c.db.BotOnline()
	if err != nil {
		return nil, err
	}

	out := make([]Snapshot, 0, len(states))
	for _, state := range states {
		queue, err := c.db.GetQueue(state.GuildID)
		if err != nil {
			return nil, err
		}
		out = append(out, snapshotFrom(state, queue, online))
	}
	return out, nil
}

// ---------- resolution ----------

// Resolve turns a query into tracks. A URL already in the download cache skips
// the network entirely; a playlist URL is expanded in full.
func (c *Controller) Resolve(ctx context.Context, query string) ([]store.Track, error) {
	query = strings.TrimSpace(query)
	if query == "" {
		return nil, ErrNoResults
	}

	if strings.HasPrefix(query, "http://") || strings.HasPrefix(query, "https://") {
		if cached, ok := c.yt.LookupCachedURL(query); ok {
			c.log.Info("url already downloaded, skipping extraction", "url", query)
			return []store.Track{cached}, nil
		}
		return c.yt.Extract(ctx, query)
	}
	return c.yt.Search(ctx, query, 1)
}

func (c *Controller) Search(ctx context.Context, query string, limit int) ([]store.Track, error) {
	return c.yt.Search(ctx, query, limit)
}

// ---------- command dispatch ----------

// Dispatch is what an API control call produces: the queued command plus enough
// context for the caller to know whether the bot will act on it soon.
type Dispatch struct {
	Command   store.Command `json:"command"`
	BotOnline bool          `json:"bot_online"`
	Tracks    []store.Track `json:"tracks,omitempty"`
}

func (c *Controller) dispatch(guildID, action string, payload map[string]any) (Dispatch, error) {
	online, err := c.db.BotOnline()
	if err != nil {
		return Dispatch{}, err
	}

	cmd, err := c.db.EnqueueCommand(guildID, action, payload)
	if err != nil {
		return Dispatch{}, err
	}

	c.log.Info("command queued for bot",
		"guild_id", guildID, "action", action, "command_id", cmd.ID, "bot_online", online)
	return Dispatch{Command: cmd, BotOnline: online}, nil
}

// PlayRequest is the API-side play payload.
type PlayRequest struct {
	Query string
	// VoiceChannelID tells the bot where to connect when it is not already in a
	// voice channel for this guild.
	VoiceChannelID string
	// TextChannelID is where the bot posts its "Now Playing" messages.
	TextChannelID string
	RequestedBy   string
}

// Play resolves the query here — so the API answers with exactly what will be
// queued, and the bot does not repeat the yt-dlp work — then hands the resolved
// tracks to the bot.
func (c *Controller) Play(ctx context.Context, guildID string, req PlayRequest) (Dispatch, error) {
	tracks, err := c.Resolve(ctx, req.Query)
	if err != nil {
		return Dispatch{}, err
	}
	if len(tracks) == 0 {
		return Dispatch{}, ErrNoResults
	}

	state, err := c.db.GetGuildState(guildID)
	if err != nil {
		return Dispatch{}, err
	}
	if req.VoiceChannelID == "" && state.VoiceChannelID == "" {
		return Dispatch{}, ErrNoVoiceChannel
	}

	payload := map[string]any{
		"query":  req.Query,
		"tracks": tracksPayload(tracks),
	}
	if req.VoiceChannelID != "" {
		payload["voice_channel_id"] = req.VoiceChannelID
	}
	if req.TextChannelID != "" {
		payload["text_channel_id"] = req.TextChannelID
	}
	if req.RequestedBy != "" {
		payload["requested_by"] = req.RequestedBy
	}

	d, err := c.dispatch(guildID, store.ActionPlay, payload)
	if err != nil {
		return Dispatch{}, err
	}
	d.Tracks = tracks
	return d, nil
}

func tracksPayload(tracks []store.Track) []map[string]any {
	out := make([]map[string]any, 0, len(tracks))
	for _, t := range tracks {
		out = append(out, map[string]any{
			"id":          t.ID,
			"title":       t.Title,
			"duration":    t.Duration,
			"thumbnail":   t.Thumbnail,
			"webpage_url": t.WebpageURL,
		})
	}
	return out
}

// Skip, Pause, Resume and friends check the mirrored state first so obviously
// impossible calls fail immediately instead of queueing a doomed command.

func (c *Controller) Skip(guildID string) (Dispatch, error) {
	state, err := c.db.GetGuildState(guildID)
	if err != nil {
		return Dispatch{}, err
	}
	if state.Status != StatusPlaying && state.Status != StatusPaused {
		return Dispatch{}, ErrNothingPlaying
	}
	return c.dispatch(guildID, store.ActionSkip, nil)
}

func (c *Controller) Pause(guildID string) (Dispatch, error) {
	state, err := c.db.GetGuildState(guildID)
	if err != nil {
		return Dispatch{}, err
	}
	switch state.Status {
	case StatusPaused:
		return Dispatch{}, ErrAlreadyPaused
	case StatusPlaying:
		return c.dispatch(guildID, store.ActionPause, nil)
	default:
		return Dispatch{}, ErrNothingPlaying
	}
}

func (c *Controller) Resume(guildID string) (Dispatch, error) {
	state, err := c.db.GetGuildState(guildID)
	if err != nil {
		return Dispatch{}, err
	}
	if state.Status != StatusPaused {
		return Dispatch{}, ErrNotPaused
	}
	return c.dispatch(guildID, store.ActionResume, nil)
}

func (c *Controller) Stop(guildID string) (Dispatch, error) {
	return c.dispatch(guildID, store.ActionStop, nil)
}

func (c *Controller) ClearQueue(guildID string) (Dispatch, error) {
	queue, err := c.db.GetQueue(guildID)
	if err != nil {
		return Dispatch{}, err
	}
	if len(queue) == 0 {
		return Dispatch{}, ErrEmptyQueue
	}
	return c.dispatch(guildID, store.ActionClear, map[string]any{"cleared": len(queue)})
}

// RemoveAt drops a 1-based queue position, validated against the mirror.
func (c *Controller) RemoveAt(guildID string, position int) (Dispatch, store.QueueEntry, error) {
	queue, err := c.db.GetQueue(guildID)
	if err != nil {
		return Dispatch{}, store.QueueEntry{}, err
	}
	if position < 1 || position > len(queue) {
		return Dispatch{}, store.QueueEntry{}, ErrInvalidPos
	}

	target := queue[position-1]
	d, err := c.dispatch(guildID, store.ActionRemove, map[string]any{
		"position": position,
		"video_id": target.ID,
	})
	return d, target, err
}

func (c *Controller) Shuffle(guildID string) (Dispatch, error) {
	queue, err := c.db.GetQueue(guildID)
	if err != nil {
		return Dispatch{}, err
	}
	if len(queue) < 2 {
		return Dispatch{}, ErrQueueTooShort
	}
	return c.dispatch(guildID, store.ActionShuffle, nil)
}

// Mix asks the bot to shuffle every cached track into a looping queue.
func (c *Controller) Mix(guildID, voiceChannelID string) (Dispatch, int, error) {
	records, err := c.db.AllDownloaded()
	if err != nil {
		return Dispatch{}, 0, err
	}
	if len(records) == 0 {
		return Dispatch{}, 0, ErrNoCached
	}

	state, err := c.db.GetGuildState(guildID)
	if err != nil {
		return Dispatch{}, 0, err
	}
	if voiceChannelID == "" && state.VoiceChannelID == "" {
		return Dispatch{}, 0, ErrNoVoiceChannel
	}

	payload := map[string]any{"cached_tracks": len(records)}
	if voiceChannelID != "" {
		payload["voice_channel_id"] = voiceChannelID
	}

	d, err := c.dispatch(guildID, store.ActionMix, payload)
	return d, len(records), err
}

func (c *Controller) SetLoop(guildID string, mode LoopMode) (Dispatch, error) {
	return c.dispatch(guildID, store.ActionLoop, map[string]any{"mode": string(mode)})
}

func (c *Controller) SetVolume(guildID string, percent int) (Dispatch, error) {
	return c.dispatch(guildID, store.ActionVolume, map[string]any{"percent": percent})
}

// SetAutoplay sets autoplay explicitly; passing nil toggles it bot-side.
func (c *Controller) SetAutoplay(guildID string, enabled *bool) (Dispatch, error) {
	payload := map[string]any{}
	if enabled != nil {
		payload["enabled"] = *enabled
	} else {
		payload["toggle"] = true
	}
	return c.dispatch(guildID, store.ActionAutoplay, payload)
}

// ---------- command inspection ----------

func (c *Controller) Command(id int64) (store.Command, error) {
	return c.db.GetCommand(id)
}

func (c *Controller) Commands(guildID, status string, limit int) ([]store.Command, error) {
	return c.db.ListCommands(guildID, status, limit)
}

// CurrentFile is the local audio path of what the bot is playing, if cached.
func (c *Controller) CurrentFile(guildID string) (string, bool) {
	state, err := c.db.GetGuildState(guildID)
	if err != nil || state.Current == nil {
		return "", false
	}

	rec, err := c.db.Get(state.Current.ID)
	if err != nil {
		return "", false
	}
	return rec.FilePath, true
}
