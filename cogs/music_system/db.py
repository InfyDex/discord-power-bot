"""SQLite-backed download registry: persists video_id -> mp3 path across bot restarts,
and drives LRU eviction so the downloads dir doesn't grow forever.
"""
import logging
import os
import sqlite3
from typing import Optional

logger = logging.getLogger('discord.music')

DB_PATH = os.path.join('downloads', 'tracks.db')


class TrackDB:
    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('''
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
            )
        ''')
        self.conn.commit()

    def get(self, video_id: str) -> Optional[dict]:
        row = self.conn.execute(
            'SELECT video_id, title, webpage_url, duration, thumbnail, file_path FROM tracks WHERE video_id = ?',
            (video_id,),
        ).fetchone()
        if not row:
            return None
        return {
            'id': row[0], 'title': row[1], 'webpage_url': row[2],
            'duration': row[3], 'thumbnail': row[4], 'file_path': row[5],
        }

    def upsert(self, track: dict, file_path: str):
        self.conn.execute('''
            INSERT INTO tracks (video_id, title, webpage_url, duration, thumbnail, file_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title, webpage_url = excluded.webpage_url,
                duration = excluded.duration, thumbnail = excluded.thumbnail,
                file_path = excluded.file_path
        ''', (
            track['id'], track['title'], track.get('webpage_url', ''),
            track.get('duration') or 0, track.get('thumbnail') or '', file_path,
        ))
        self.conn.commit()

    def record_play(self, video_id: str):
        self.conn.execute(
            "UPDATE tracks SET play_count = play_count + 1, last_played_at = datetime('now') WHERE video_id = ?",
            (video_id,),
        )
        self.conn.commit()

    def delete(self, video_id: str):
        self.conn.execute('DELETE FROM tracks WHERE video_id = ?', (video_id,))
        self.conn.commit()

    def all_downloaded(self) -> list[dict]:
        rows = self.conn.execute(
            'SELECT video_id, title, webpage_url, duration, thumbnail, file_path FROM tracks'
        ).fetchall()
        return [
            {'id': r[0], 'title': r[1], 'webpage_url': r[2], 'duration': r[3], 'thumbnail': r[4], 'file_path': r[5]}
            for r in rows
        ]

    def evict_lru(self, limit: int) -> list[tuple[str, str]]:
        """Delete rows past `limit`, oldest-played-first (falls back to download time). Returns (video_id, file_path) evicted."""
        rows = self.conn.execute(
            "SELECT video_id, file_path FROM tracks ORDER BY COALESCE(last_played_at, downloaded_at) DESC"
        ).fetchall()
        to_evict = rows[limit:]
        for video_id, _ in to_evict:
            self.conn.execute('DELETE FROM tracks WHERE video_id = ?', (video_id,))
        if to_evict:
            self.conn.commit()
        return to_evict
