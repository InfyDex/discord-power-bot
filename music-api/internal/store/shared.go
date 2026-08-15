package store

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"
)

// This file defines the control plane the API and the Discord bot share inside
// one sqlite file. Ownership is strict, so neither side ever fights the other:
//
//	guild_state, guild_queue  written by the bot (it owns the voice connection),
//	                          read by the API
//	commands                  written by the API, claimed and completed by the bot
//	workers                   heartbeat rows, written by both
//
// The Python side mirrors this schema in cogs/music_system/shared_db.py.

const sharedSchema = `
CREATE TABLE IF NOT EXISTS guild_state (
	guild_id TEXT PRIMARY KEY,
	status TEXT NOT NULL DEFAULT 'idle',
	current_video_id TEXT NOT NULL DEFAULT '',
	current_title TEXT NOT NULL DEFAULT '',
	current_duration INTEGER NOT NULL DEFAULT 0,
	current_thumbnail TEXT NOT NULL DEFAULT '',
	current_webpage_url TEXT NOT NULL DEFAULT '',
	position_seconds INTEGER NOT NULL DEFAULT 0,
	loop_mode TEXT NOT NULL DEFAULT 'off',
	autoplay INTEGER NOT NULL DEFAULT 0,
	volume INTEGER NOT NULL DEFAULT 100,
	voice_channel_id TEXT NOT NULL DEFAULT '',
	voice_channel_name TEXT NOT NULL DEFAULT '',
	text_channel_id TEXT NOT NULL DEFAULT '',
	updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_queue (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	guild_id TEXT NOT NULL,
	position INTEGER NOT NULL,
	video_id TEXT NOT NULL,
	title TEXT NOT NULL,
	duration INTEGER NOT NULL DEFAULT 0,
	thumbnail TEXT NOT NULL DEFAULT '',
	webpage_url TEXT NOT NULL DEFAULT '',
	requested_by TEXT NOT NULL DEFAULT '',
	added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_guild_queue_guild ON guild_queue(guild_id, position);

CREATE TABLE IF NOT EXISTS commands (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	guild_id TEXT NOT NULL,
	action TEXT NOT NULL,
	payload TEXT NOT NULL DEFAULT '{}',
	source TEXT NOT NULL DEFAULT 'api',
	status TEXT NOT NULL DEFAULT 'pending',
	result TEXT NOT NULL DEFAULT '',
	error TEXT NOT NULL DEFAULT '',
	created_at TEXT NOT NULL DEFAULT (datetime('now')),
	updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_commands_pending ON commands(status, id);

CREATE TABLE IF NOT EXISTS download_locks (
	video_id TEXT PRIMARY KEY,
	owner TEXT NOT NULL,
	acquired_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workers (
	name TEXT PRIMARY KEY,
	version TEXT NOT NULL DEFAULT '',
	guilds INTEGER NOT NULL DEFAULT 0,
	updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
`

// ---------- guild state ----------

// GuildState is the bot's live player, mirrored for the API to read.
type GuildState struct {
	GuildID          string `json:"guild_id"`
	Status           string `json:"status"`
	Current          *Track `json:"current"`
	PositionSeconds  int    `json:"position_seconds"`
	LoopMode         string `json:"loop_mode"`
	Autoplay         bool   `json:"autoplay"`
	VolumePercent    int    `json:"volume_percent"`
	VoiceChannelID   string `json:"voice_channel_id,omitempty"`
	VoiceChannelName string `json:"voice_channel_name,omitempty"`
	TextChannelID    string `json:"text_channel_id,omitempty"`
	UpdatedAt        string `json:"updated_at"`
}

// GetGuildState returns the mirrored state, or a zero-value idle state when the
// bot has never played in that guild.
func (d *DB) GetGuildState(guildID string) (GuildState, error) {
	row := d.db.QueryRow(`
		SELECT guild_id, status, current_video_id, current_title, current_duration,
		       current_thumbnail, current_webpage_url, position_seconds, loop_mode,
		       autoplay, volume, voice_channel_id, voice_channel_name, text_channel_id, updated_at
		  FROM guild_state WHERE guild_id = ?`, guildID)

	var (
		s                                     GuildState
		videoID, title, thumbnail, webpageURL string
		duration, autoplay                    int
	)
	err := row.Scan(&s.GuildID, &s.Status, &videoID, &title, &duration, &thumbnail,
		&webpageURL, &s.PositionSeconds, &s.LoopMode, &autoplay, &s.VolumePercent,
		&s.VoiceChannelID, &s.VoiceChannelName, &s.TextChannelID, &s.UpdatedAt)

	if errors.Is(err, sql.ErrNoRows) {
		return GuildState{
			GuildID:       guildID,
			Status:        "idle",
			LoopMode:      "off",
			VolumePercent: 100,
		}, nil
	}
	if err != nil {
		return GuildState{}, err
	}

	s.Autoplay = autoplay != 0
	if videoID != "" {
		s.Current = &Track{
			ID: videoID, Title: title, Duration: duration,
			Thumbnail: thumbnail, WebpageURL: webpageURL,
		}
	}
	return s, nil
}

// ListGuildStates returns every guild the bot has player state for.
func (d *DB) ListGuildStates() ([]GuildState, error) {
	rows, err := d.db.Query(`SELECT guild_id FROM guild_state ORDER BY guild_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	states := make([]GuildState, 0, len(ids))
	for _, id := range ids {
		s, err := d.GetGuildState(id)
		if err != nil {
			return nil, err
		}
		states = append(states, s)
	}
	return states, nil
}

// ---------- guild queue ----------

// QueueEntry is one mirrored queue slot. Position is 1-based.
type QueueEntry struct {
	Track
	Position    int    `json:"position"`
	RequestedBy string `json:"requested_by,omitempty"`
	AddedAt     string `json:"added_at"`
}

func (d *DB) GetQueue(guildID string) ([]QueueEntry, error) {
	rows, err := d.db.Query(`
		SELECT position, video_id, title, duration, thumbnail, webpage_url, requested_by, added_at
		  FROM guild_queue WHERE guild_id = ? ORDER BY position`, guildID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []QueueEntry{}
	for rows.Next() {
		var e QueueEntry
		if err := rows.Scan(&e.Position, &e.ID, &e.Title, &e.Duration, &e.Thumbnail,
			&e.WebpageURL, &e.RequestedBy, &e.AddedAt); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// MirrorGuild replaces a guild's mirrored state and queue in one transaction.
//
// In production the Python bridge writes these rows — it owns the live player.
// This exists so Go-side code (and tests) can produce an identical mirror.
func (d *DB) MirrorGuild(state GuildState, queue []QueueEntry) error {
	tx, err := d.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	var videoID, title, thumbnail, webpageURL string
	var duration int
	if state.Current != nil {
		videoID = state.Current.ID
		title = state.Current.Title
		duration = state.Current.Duration
		thumbnail = state.Current.Thumbnail
		webpageURL = state.Current.WebpageURL
	}

	autoplay := 0
	if state.Autoplay {
		autoplay = 1
	}

	if _, err := tx.Exec(`
		INSERT INTO guild_state (
			guild_id, status, current_video_id, current_title, current_duration,
			current_thumbnail, current_webpage_url, position_seconds, loop_mode,
			autoplay, volume, voice_channel_id, voice_channel_name, text_channel_id, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
		ON CONFLICT(guild_id) DO UPDATE SET
			status = excluded.status,
			current_video_id = excluded.current_video_id,
			current_title = excluded.current_title,
			current_duration = excluded.current_duration,
			current_thumbnail = excluded.current_thumbnail,
			current_webpage_url = excluded.current_webpage_url,
			position_seconds = excluded.position_seconds,
			loop_mode = excluded.loop_mode,
			autoplay = excluded.autoplay,
			volume = excluded.volume,
			voice_channel_id = excluded.voice_channel_id,
			voice_channel_name = excluded.voice_channel_name,
			text_channel_id = excluded.text_channel_id,
			updated_at = datetime('now')`,
		state.GuildID, state.Status, videoID, title, duration, thumbnail, webpageURL,
		state.PositionSeconds, state.LoopMode, autoplay, state.VolumePercent,
		state.VoiceChannelID, state.VoiceChannelName, state.TextChannelID); err != nil {
		return err
	}

	if _, err := tx.Exec(`DELETE FROM guild_queue WHERE guild_id = ?`, state.GuildID); err != nil {
		return err
	}
	for _, e := range queue {
		if _, err := tx.Exec(`
			INSERT INTO guild_queue (guild_id, position, video_id, title, duration, thumbnail, webpage_url, requested_by)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
			state.GuildID, e.Position, e.ID, e.Title, e.Duration, e.Thumbnail, e.WebpageURL, e.RequestedBy); err != nil {
			return err
		}
	}

	return tx.Commit()
}

// ---------- commands ----------

// Command actions the bot understands. Keep in sync with the Python executor.
const (
	ActionPlay     = "play"
	ActionSkip     = "skip"
	ActionPause    = "pause"
	ActionResume   = "resume"
	ActionStop     = "stop"
	ActionClear    = "clear"
	ActionRemove   = "remove"
	ActionShuffle  = "shuffle"
	ActionMix      = "mix"
	ActionLoop     = "loop"
	ActionVolume   = "volume"
	ActionAutoplay = "autoplay"
)

const (
	CommandPending = "pending"
	CommandClaimed = "claimed"
	CommandDone    = "done"
	CommandFailed  = "failed"
)

type Command struct {
	ID        int64          `json:"id"`
	GuildID   string         `json:"guild_id"`
	Action    string         `json:"action"`
	Payload   map[string]any `json:"payload"`
	Source    string         `json:"source"`
	Status    string         `json:"status"`
	Result    string         `json:"result,omitempty"`
	Error     string         `json:"error,omitempty"`
	CreatedAt string         `json:"created_at"`
	UpdatedAt string         `json:"updated_at"`
}

// EnqueueCommand hands an action to the bot and returns the stored command.
func (d *DB) EnqueueCommand(guildID, action string, payload map[string]any) (Command, error) {
	if payload == nil {
		payload = map[string]any{}
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		return Command{}, err
	}

	res, err := d.db.Exec(
		`INSERT INTO commands (guild_id, action, payload) VALUES (?, ?, ?)`,
		guildID, action, string(encoded))
	if err != nil {
		return Command{}, err
	}

	id, err := res.LastInsertId()
	if err != nil {
		return Command{}, err
	}
	return d.GetCommand(id)
}

func (d *DB) GetCommand(id int64) (Command, error) {
	row := d.db.QueryRow(`
		SELECT id, guild_id, action, payload, source, status, result, error, created_at, updated_at
		  FROM commands WHERE id = ?`, id)

	var (
		c       Command
		payload string
	)
	err := row.Scan(&c.ID, &c.GuildID, &c.Action, &payload, &c.Source, &c.Status,
		&c.Result, &c.Error, &c.CreatedAt, &c.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Command{}, ErrNotFound
	}
	if err != nil {
		return Command{}, err
	}

	if err := json.Unmarshal([]byte(payload), &c.Payload); err != nil {
		c.Payload = map[string]any{}
	}
	return c, nil
}

// ListCommands returns recent commands, newest first, optionally filtered.
func (d *DB) ListCommands(guildID, status string, limit int) ([]Command, error) {
	if limit <= 0 || limit > 200 {
		limit = 50
	}

	query := `SELECT id, guild_id, action, payload, source, status, result, error, created_at, updated_at
		        FROM commands`
	var (
		where []string
		args  []any
	)
	if guildID != "" {
		where = append(where, "guild_id = ?")
		args = append(args, guildID)
	}
	if status != "" {
		where = append(where, "status = ?")
		args = append(args, status)
	}
	if len(where) > 0 {
		query += " WHERE " + strings.Join(where, " AND ")
	}
	query += " ORDER BY id DESC LIMIT ?"
	args = append(args, limit)

	rows, err := d.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []Command{}
	for rows.Next() {
		var (
			c       Command
			payload string
		)
		if err := rows.Scan(&c.ID, &c.GuildID, &c.Action, &payload, &c.Source, &c.Status,
			&c.Result, &c.Error, &c.CreatedAt, &c.UpdatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal([]byte(payload), &c.Payload); err != nil {
			c.Payload = map[string]any{}
		}
		out = append(out, c)
	}
	return out, rows.Err()
}

// PurgeCommands drops finished commands older than the cutoff, so the shared
// table does not grow without bound.
func (d *DB) PurgeCommands(olderThan time.Duration) (int64, error) {
	cutoff := time.Now().UTC().Add(-olderThan).Format("2006-01-02 15:04:05")

	res, err := d.db.Exec(
		`DELETE FROM commands WHERE status IN (?, ?) AND updated_at < ?`,
		CommandDone, CommandFailed, cutoff)
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}

// ---------- download locks ----------

// lockTTL is how long a download lock is honoured before another process may
// steal it — long enough for a slow download, short enough to self-heal after
// a crash.
const lockTTL = 15 * time.Minute

// AcquireDownloadLock claims the right to download a video. It returns false
// when another live process holds the lock, in which case the caller should
// wait for that download rather than start a competing yt-dlp run: two writers
// on one output path corrupt the file.
func (d *DB) AcquireDownloadLock(videoID, owner string) (bool, error) {
	res, err := d.db.Exec(`
		INSERT INTO download_locks (video_id, owner) VALUES (?, ?)
		ON CONFLICT(video_id) DO NOTHING`, videoID, owner)
	if err != nil {
		return false, err
	}
	if n, err := res.RowsAffected(); err == nil && n > 0 {
		return true, nil
	}

	// Steal an abandoned lock (owner crashed mid-download).
	cutoff := time.Now().UTC().Add(-lockTTL).Format("2006-01-02 15:04:05")
	res, err = d.db.Exec(`
		UPDATE download_locks SET owner = ?, acquired_at = datetime('now')
		 WHERE video_id = ? AND acquired_at < ?`, owner, videoID, cutoff)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n > 0, err
}

func (d *DB) ReleaseDownloadLock(videoID, owner string) error {
	_, err := d.db.Exec(`DELETE FROM download_locks WHERE video_id = ? AND owner = ?`, videoID, owner)
	return err
}

// ---------- workers ----------

// Worker is a heartbeat row: which processes are alive on this database.
type Worker struct {
	Name      string `json:"name"`
	Version   string `json:"version"`
	Guilds    int    `json:"guilds"`
	UpdatedAt string `json:"updated_at"`
	Online    bool   `json:"online"`
	AgeSecond int    `json:"seconds_since_heartbeat"`
}

// Heartbeat records that this process is alive.
func (d *DB) Heartbeat(name, version string, guilds int) error {
	_, err := d.db.Exec(`
		INSERT INTO workers (name, version, guilds, updated_at)
		VALUES (?, ?, ?, datetime('now'))
		ON CONFLICT(name) DO UPDATE SET
			version = excluded.version, guilds = excluded.guilds, updated_at = datetime('now')`,
		name, version, guilds)
	return err
}

// staleAfter is how long a heartbeat stays valid. The bot beats every 10s.
const staleAfter = 45 * time.Second

func (d *DB) ListWorkers() ([]Worker, error) {
	rows, err := d.db.Query(
		`SELECT name, version, guilds, updated_at, (julianday('now') - julianday(updated_at)) * 86400.0
		   FROM workers ORDER BY name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []Worker{}
	for rows.Next() {
		var (
			w   Worker
			age float64
		)
		if err := rows.Scan(&w.Name, &w.Version, &w.Guilds, &w.UpdatedAt, &age); err != nil {
			return nil, err
		}
		if age < 0 {
			age = 0
		}
		w.AgeSecond = int(age)
		w.Online = time.Duration(age*float64(time.Second)) < staleAfter
		out = append(out, w)
	}
	return out, rows.Err()
}

// BotOnline reports whether the Discord bot has beaten recently enough to be
// able to execute commands.
func (d *DB) BotOnline() (bool, error) {
	workers, err := d.ListWorkers()
	if err != nil {
		return false, err
	}
	for _, w := range workers {
		if w.Name == "bot" {
			return w.Online, nil
		}
	}
	return false, nil
}

func (d *DB) applySharedSchema() error {
	if _, err := d.db.Exec(sharedSchema); err != nil {
		return fmt.Errorf("apply shared schema: %w", err)
	}
	return nil
}
