"""Shared control plane between the Discord bot and the music API.

Both processes open the same sqlite file (downloads/tracks.db). Ownership is
strict so neither side fights the other:

    guild_state, guild_queue   written here (the bot owns the voice connection),
                               read by the API
    commands                   written by the API, claimed and completed here
    workers                    heartbeat rows, written by both
    download_locks             advisory locks so one video is downloaded once

The Go side defines the same schema in music-api/internal/store/shared.go.
"""
import json
import logging
import os
import sqlite3
import threading
from typing import Any, Optional

logger = logging.getLogger('discord.music')

DB_PATH = os.path.join('downloads', 'tracks.db')

WORKER_NAME = 'bot'

SCHEMA = """
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
"""

# A crashed downloader must not block the track forever; matches lockTTL in Go.
LOCK_TTL_MINUTES = 15


class SharedDB:
    """Thread-safe accessor for the shared control-plane tables."""

    def __init__(self, db_path: str = DB_PATH):
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        # timeout lets writes wait out the API's transactions instead of raising
        # "database is locked" the moment both processes write at once.
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.commit()

        self._lock = threading.Lock()
        self.owner = f'bot:{os.getpid()}'

    def close(self):
        with self._lock:
            self.conn.close()

    # ---------- heartbeat ----------

    def heartbeat(self, guilds: int, version: str = ''):
        """Advertise that the bot is alive, so the API knows commands will run."""
        with self._lock:
            self.conn.execute('''
                INSERT INTO workers (name, version, guilds, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(name) DO UPDATE SET
                    version = excluded.version, guilds = excluded.guilds,
                    updated_at = datetime('now')
            ''', (WORKER_NAME, version, guilds))
            self.conn.commit()

    # ---------- state mirror ----------

    def mirror_guild(self, guild_id: str, state: dict, queue: list[dict]):
        """Replace a guild's mirrored state and queue in one transaction."""
        current = state.get('current') or {}

        with self._lock:
            self.conn.execute('''
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
                    updated_at = datetime('now')
            ''', (
                guild_id,
                state.get('status', 'idle'),
                current.get('id', ''),
                current.get('title', ''),
                current.get('duration', 0) or 0,
                current.get('thumbnail', '') or '',
                current.get('webpage_url', '') or '',
                int(state.get('position_seconds', 0)),
                state.get('loop_mode', 'off'),
                1 if state.get('autoplay') else 0,
                int(state.get('volume', 100)),
                state.get('voice_channel_id', '') or '',
                state.get('voice_channel_name', '') or '',
                state.get('text_channel_id', '') or '',
            ))

            self.conn.execute('DELETE FROM guild_queue WHERE guild_id = ?', (guild_id,))
            self.conn.executemany('''
                INSERT INTO guild_queue (guild_id, position, video_id, title, duration,
                                         thumbnail, webpage_url, requested_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                (
                    guild_id, index + 1, track.get('id', ''), track.get('title', ''),
                    track.get('duration', 0) or 0, track.get('thumbnail', '') or '',
                    track.get('webpage_url', '') or '', track.get('requested_by', '') or '',
                )
                for index, track in enumerate(queue)
            ])
            self.conn.commit()

    def forget_guild(self, guild_id: str):
        """Drop a guild's mirror (used when the bot leaves a guild)."""
        with self._lock:
            self.conn.execute('DELETE FROM guild_state WHERE guild_id = ?', (guild_id,))
            self.conn.execute('DELETE FROM guild_queue WHERE guild_id = ?', (guild_id,))
            self.conn.commit()

    # ---------- commands ----------

    def claim_commands(self, limit: int = 10) -> list[dict]:
        """Take pending commands off the queue. Claiming marks them so a second
        poll (or a second bot process) cannot run the same command twice.
        """
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM commands WHERE status = 'pending' ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
            if not rows:
                return []

            ids = [row['id'] for row in rows]
            placeholders = ','.join('?' * len(ids))
            self.conn.execute(
                f"UPDATE commands SET status = 'claimed', updated_at = datetime('now') "
                f"WHERE id IN ({placeholders}) AND status = 'pending'",
                ids,
            )
            self.conn.commit()

            claimed = self.conn.execute(
                f"SELECT id, guild_id, action, payload FROM commands "
                f"WHERE id IN ({placeholders}) AND status = 'claimed' ORDER BY id",
                ids,
            ).fetchall()

        commands = []
        for row in claimed:
            try:
                payload = json.loads(row['payload'])
            except (TypeError, ValueError):
                payload = {}
            commands.append({
                'id': row['id'],
                'guild_id': row['guild_id'],
                'action': row['action'],
                'payload': payload,
            })
        return commands

    def complete_command(self, command_id: int, result: str = ''):
        self._finish_command(command_id, 'done', result=result)

    def fail_command(self, command_id: int, error: str):
        self._finish_command(command_id, 'failed', error=error)

    def _finish_command(self, command_id: int, status: str, result: str = '', error: str = ''):
        with self._lock:
            self.conn.execute(
                "UPDATE commands SET status = ?, result = ?, error = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (status, result[:2000], error[:2000], command_id),
            )
            self.conn.commit()

    # ---------- download locks ----------

    def acquire_download_lock(self, video_id: str) -> bool:
        """Claim the right to download a video. False means another process is
        already downloading it — wait for that instead of racing yt-dlp onto the
        same output path.
        """
        with self._lock:
            cursor = self.conn.execute(
                'INSERT INTO download_locks (video_id, owner) VALUES (?, ?) '
                'ON CONFLICT(video_id) DO NOTHING',
                (video_id, self.owner),
            )
            if cursor.rowcount > 0:
                self.conn.commit()
                return True

            # Steal an abandoned lock (owner crashed mid-download).
            cursor = self.conn.execute(
                "UPDATE download_locks SET owner = ?, acquired_at = datetime('now') "
                "WHERE video_id = ? AND acquired_at < datetime('now', ?)",
                (self.owner, video_id, f'-{LOCK_TTL_MINUTES} minutes'),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def release_download_lock(self, video_id: str):
        with self._lock:
            self.conn.execute(
                'DELETE FROM download_locks WHERE video_id = ? AND owner = ?',
                (video_id, self.owner),
            )
            self.conn.commit()


_shared: Optional[SharedDB] = None


def get_shared_db() -> SharedDB:
    """Process-wide SharedDB, so the bridge and the downloader share one handle."""
    global _shared
    if _shared is None:
        _shared = SharedDB()
    return _shared
