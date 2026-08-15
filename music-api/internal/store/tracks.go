// Package store persists the download registry: video_id -> audio file on disk.
// Schema is identical to the Python bot's cogs/music_system/db.py so both can
// share one downloads/tracks.db file.
package store

import (
	"database/sql"
	"errors"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite" // pure-Go driver, no cgo
)

// Track is the metadata subset the queue and the API speak in.
type Track struct {
	ID         string `json:"id"`
	Title      string `json:"title"`
	Duration   int    `json:"duration"`
	Thumbnail  string `json:"thumbnail"`
	WebpageURL string `json:"webpage_url"`
}

// Record is a cached track plus its on-disk location and play accounting.
type Record struct {
	Track
	FilePath     string `json:"file_path"`
	DownloadedAt string `json:"downloaded_at"`
	LastPlayedAt string `json:"last_played_at,omitempty"`
	PlayCount    int    `json:"play_count"`
}

// Evicted names a row dropped by EvictLRU, so the caller can delete the file.
type Evicted struct {
	VideoID  string
	FilePath string
}

var ErrNotFound = errors.New("track not found")

type DB struct {
	db *sql.DB
}

func Open(path string) (*DB, error) {
	if dir := filepath.Dir(path); dir != "" && dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, err
		}
	}

	// _busy_timeout keeps concurrent writers (API + the Python bot) from
	// failing instantly on SQLITE_BUSY.
	sqldb, err := sql.Open("sqlite", path+"?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)")
	if err != nil {
		return nil, err
	}

	if _, err := sqldb.Exec(`
		CREATE TABLE IF NOT EXISTS tracks (
			video_id TEXT PRIMARY KEY,
			title TEXT NOT NULL,
			webpage_url TEXT NOT NULL,
			duration INTEGER NOT NULL DEFAULT 0,
			thumbnail TEXT NOT NULL DEFAULT '',
			file_path TEXT NOT NULL,
			downloaded_at TEXT NOT NULL DEFAULT (datetime('now')),
			last_played_at TEXT,
			play_count INTEGER NOT NULL DEFAULT 0
		)`); err != nil {
		sqldb.Close()
		return nil, err
	}

	db := &DB{db: sqldb}
	if err := db.applySharedSchema(); err != nil {
		sqldb.Close()
		return nil, err
	}
	return db, nil
}

func (d *DB) Close() error { return d.db.Close() }

func (d *DB) Get(videoID string) (Record, error) {
	row := d.db.QueryRow(`
		SELECT video_id, title, webpage_url, duration, thumbnail, file_path,
		       downloaded_at, COALESCE(last_played_at, ''), play_count
		  FROM tracks WHERE video_id = ?`, videoID)

	var r Record
	err := row.Scan(&r.ID, &r.Title, &r.WebpageURL, &r.Duration, &r.Thumbnail,
		&r.FilePath, &r.DownloadedAt, &r.LastPlayedAt, &r.PlayCount)
	if errors.Is(err, sql.ErrNoRows) {
		return Record{}, ErrNotFound
	}
	return r, err
}

func (d *DB) Upsert(t Track, filePath string) error {
	_, err := d.db.Exec(`
		INSERT INTO tracks (video_id, title, webpage_url, duration, thumbnail, file_path)
		VALUES (?, ?, ?, ?, ?, ?)
		ON CONFLICT(video_id) DO UPDATE SET
			title = excluded.title, webpage_url = excluded.webpage_url,
			duration = excluded.duration, thumbnail = excluded.thumbnail,
			file_path = excluded.file_path`,
		t.ID, t.Title, t.WebpageURL, t.Duration, t.Thumbnail, filePath)
	return err
}

func (d *DB) RecordPlay(videoID string) error {
	_, err := d.db.Exec(
		`UPDATE tracks SET play_count = play_count + 1, last_played_at = datetime('now') WHERE video_id = ?`,
		videoID)
	return err
}

func (d *DB) Delete(videoID string) error {
	_, err := d.db.Exec(`DELETE FROM tracks WHERE video_id = ?`, videoID)
	return err
}

// AllDownloaded returns every cached track, most recently played first.
func (d *DB) AllDownloaded() ([]Record, error) {
	rows, err := d.db.Query(`
		SELECT video_id, title, webpage_url, duration, thumbnail, file_path,
		       downloaded_at, COALESCE(last_played_at, ''), play_count
		  FROM tracks
		 ORDER BY COALESCE(last_played_at, downloaded_at) DESC, rowid DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []Record
	for rows.Next() {
		var r Record
		if err := rows.Scan(&r.ID, &r.Title, &r.WebpageURL, &r.Duration, &r.Thumbnail,
			&r.FilePath, &r.DownloadedAt, &r.LastPlayedAt, &r.PlayCount); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (d *DB) Count() (int, error) {
	var n int
	err := d.db.QueryRow(`SELECT COUNT(*) FROM tracks`).Scan(&n)
	return n, err
}

// EvictLRU deletes rows past limit, oldest-played-first (falling back to
// download time), and returns them so their files can be removed.
func (d *DB) EvictLRU(limit int) ([]Evicted, error) {
	if limit <= 0 {
		return nil, nil
	}

	// rowid breaks ties: timestamps have second granularity, so several tracks
	// touched in the same second would otherwise evict in arbitrary order.
	rows, err := d.db.Query(`
		SELECT video_id, file_path FROM tracks
		 ORDER BY COALESCE(last_played_at, downloaded_at) DESC, rowid DESC
		 LIMIT -1 OFFSET ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var evicted []Evicted
	for rows.Next() {
		var e Evicted
		if err := rows.Scan(&e.VideoID, &e.FilePath); err != nil {
			return nil, err
		}
		evicted = append(evicted, e)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	for _, e := range evicted {
		if err := d.Delete(e.VideoID); err != nil {
			return evicted, err
		}
	}
	return evicted, nil
}
