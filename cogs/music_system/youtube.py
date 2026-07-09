"""YouTube search/download layer: yt-dlp resolution, cookie auth, and a disk-backed LRU audio cache."""
import asyncio
import base64
import glob
import logging
import os
import re
import shutil
import sys
import tempfile
from collections import OrderedDict
from typing import Optional

import yt_dlp

from .db import TrackDB

logger = logging.getLogger('discord.music')

DOWNLOAD_DIR = 'downloads'
PLAYER_CLIENTS = 'ios,android'
BOT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_VIDEO_ID_RE = re.compile(
    r'(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{11})'
)


def extract_video_id(url: str) -> Optional[str]:
    """Pull an 11-char YouTube video id out of a watch/shorts/embed/youtu.be URL, if present."""
    match = _VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


def find_ytdlp_cmd() -> list[str]:
    """Locate a runnable yt-dlp: PATH bin, venv bin, then `python -m yt_dlp`."""
    found = shutil.which('yt-dlp')
    if found:
        return [found]
    venv_dir = os.path.dirname(sys.executable)
    for name in ('yt-dlp', 'yt-dlp.exe'):
        venv_bin = os.path.join(venv_dir, name)
        if os.path.exists(venv_bin):
            return [venv_bin]
    try:
        import yt_dlp as _yt  # noqa: F401
        logger.info("yt-dlp binary not found in PATH; falling back to 'python -m yt_dlp'")
        return [sys.executable, '-m', 'yt_dlp']
    except ImportError:
        pass
    raise FileNotFoundError("yt-dlp not found. Install it with: pip install yt-dlp")


def resolve_cookies() -> tuple[Optional[str], Optional[tuple]]:
    """Resolve YouTube auth for yt-dlp.

    Returns (cookiefile_path, cookies_from_browser_spec) — at most one is set.
    Priority: YOUTUBE_COOKIES_B64 > YOUTUBE_COOKIES_FILE > cookies.txt in bot root > COOKIES_FROM_BROWSER.
    The browser option (`COOKIES_FROM_BROWSER=chrome` or `chrome:ProfileName`) only works when the
    bot runs on the same machine as the browser, so it's last priority — servers should use a file.
    """
    b64 = os.environ.get('YOUTUBE_COOKIES_B64')
    if b64:
        try:
            data = base64.b64decode(b64)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='wb')
            tmp.write(data)
            tmp.close()
            # Drop the large B64 blob from the env now that it's on disk. Otherwise every
            # child process (ffmpeg included) inherits it and can hit E2BIG / "Argument
            # list too long", since ARGV_MAX counts the environment too.
            os.environ.pop('YOUTUBE_COOKIES_B64', None)
            logger.info(f"YouTube cookies loaded from YOUTUBE_COOKIES_B64 -> {tmp.name}")
            return tmp.name, None
        except Exception as e:
            logger.warning(f"Failed to decode YOUTUBE_COOKIES_B64: {e}")

    env_path = os.environ.get('YOUTUBE_COOKIES_FILE')
    if env_path and os.path.exists(env_path):
        logger.info(f"YouTube cookies loaded from YOUTUBE_COOKIES_FILE -> {env_path}")
        return env_path, None

    default = os.path.join(BOT_ROOT, 'cookies.txt')
    if os.path.exists(default):
        logger.info(f"YouTube cookies loaded from {default}")
        return default, None

    browser = os.environ.get('COOKIES_FROM_BROWSER')
    if browser:
        parts = browser.split(':', 1)
        spec = tuple(parts)
        logger.info(f"YouTube cookies loaded from browser: {browser}")
        return None, spec

    logger.warning(
        "No YouTube cookies configured. Downloads may fail with 403 on server IPs. "
        "Set YOUTUBE_COOKIES_B64, YOUTUBE_COOKIES_FILE, place cookies.txt in the bot root, "
        "or set COOKIES_FROM_BROWSER=chrome (local use only)."
    )
    return None, None


class YTDLPClient:
    """Wraps yt-dlp for search/extraction (Python API) and download (CLI subprocess).

    The CLI is used for downloads because it handles PO tokens, retries, and format
    negotiation more reliably than the Python API on server IPs.
    """

    def __init__(self, cache_limit: int = 100):
        self.ytdlp_cmd = find_ytdlp_cmd()
        self.cookiefile, self.cookies_from_browser = resolve_cookies()

        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': False,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
            'playlistend': 50,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
        }
        if self.cookiefile:
            ydl_opts['cookiefile'] = self.cookiefile
        if self.cookies_from_browser:
            ydl_opts['cookiesfrombrowser'] = self.cookies_from_browser
        self._ydl = yt_dlp.YoutubeDL(ydl_opts)

        self.cache_limit = cache_limit
        self._cache: OrderedDict[str, str] = OrderedDict()
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self.db = TrackDB()

    @staticmethod
    def _to_track_dict(entry: dict) -> dict:
        return {
            'id': entry['id'],
            'title': entry['title'],
            'duration': entry.get('duration') or 0,
            'thumbnail': entry.get('thumbnail', ''),
            'webpage_url': entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry['id']}",
        }

    async def search(self, query: str, limit: int = 1) -> list[dict]:
        """Search YouTube; returns up to `limit` result dicts."""
        try:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None, lambda: self._ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            )
            if not data:
                return []
            entries = data.get('entries', [data])
            return [self._to_track_dict(e) for e in entries if e]
        except Exception as e:
            logger.error(f"Error searching YouTube for '{query}': {e}", exc_info=True)
            return []

    async def extract(self, url: str) -> list[dict]:
        """Extract a single video or a full playlist from a URL."""
        try:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, lambda: self._ydl.extract_info(url, download=False))
            if not data:
                return []
            if 'entries' not in data:
                return [self._to_track_dict(data)]
            return [self._to_track_dict(e) for e in data['entries'] if e]
        except Exception as e:
            logger.error(f"Error extracting '{url}': {e}", exc_info=True)
            return []

    def lookup_cached_url(self, url: str) -> Optional[dict]:
        """If `url` names a video we already downloaded, return its track dict without hitting the network."""
        video_id = extract_video_id(url)
        if not video_id:
            return None
        row = self.db.get(video_id)
        if not row or not os.path.exists(row['file_path']):
            return None
        return {
            'id': row['id'], 'title': row['title'], 'duration': row['duration'],
            'thumbnail': row['thumbnail'], 'webpage_url': row['webpage_url'],
        }

    async def related(self, video_id: str, exclude_ids: set) -> Optional[dict]:
        """First unseen track from YouTube's auto-generated Mix, for autoplay."""
        url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
        for track in await self.extract(url):
            if track['id'] not in exclude_ids:
                return track
        return None

    def _download_cmd(self, track: dict) -> list[str]:
        cmd = [
            *self.ytdlp_cmd,
            '--no-playlist',
            '-f', 'bestaudio/best',
            '-x', '--audio-format', 'mp3', '--audio-quality', '192K',
            '--no-check-certificates',
            '--extractor-args', f'youtube:player_client={PLAYER_CLIENTS}',
            '-o', os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        ]
        if self.cookiefile:
            cmd += ['--cookies', self.cookiefile]
        if self.cookies_from_browser:
            cmd += ['--cookies-from-browser', ':'.join(self.cookies_from_browser)]
        cmd.append(track['webpage_url'])
        return cmd

    async def _download(self, track: dict) -> Optional[str]:
        video_id = track['id']
        cmd = self._download_cmd(track)

        # Strip large env vars that would push the subprocess over E2BIG (ARGV_MAX).
        # Cookies are already written to a temp file and passed via --cookies.
        sub_env = os.environ.copy()
        sub_env.pop('YOUTUBE_COOKIES_B64', None)

        logger.info(f"yt-dlp download: {track['title']}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=sub_env,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"yt-dlp exited {proc.returncode}: {stderr.decode(errors='replace').strip()}")
                return None
        except Exception as e:
            logger.error(f"yt-dlp subprocess error: {e}", exc_info=True)
            return None

        # yt-dlp may produce .mp3 (with ffmpeg) or a native format if ffmpeg is unavailable.
        matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*"))
        if not matches:
            logger.error(f"yt-dlp produced no output file for video_id={video_id}")
            return None
        return matches[0]

    async def get_audio_file(self, track: dict) -> Optional[str]:
        """Cached download: checks in-memory cache, then the sqlite registry (survives restarts),
        then downloads. New downloads are recorded in the DB, which drives LRU eviction so the
        downloads dir stays bounded across the bot's lifetime, not just within one process run.
        """
        video_id = track['id']
        if video_id in self._cache:
            path = self._cache[video_id]
            if os.path.exists(path):
                self._cache.move_to_end(video_id)
                self.db.record_play(video_id)
                logger.info(f"Cache hit (memory) for '{track['title']}' -> {path}")
                return path
            del self._cache[video_id]

        row = self.db.get(video_id)
        if row:
            if os.path.exists(row['file_path']):
                self._cache[video_id] = row['file_path']
                self._cache.move_to_end(video_id)
                self.db.record_play(video_id)
                logger.info(f"Cache hit (already downloaded) for '{track['title']}' -> {row['file_path']}")
                return row['file_path']
            logger.warning(f"DB row for {video_id} points at missing file, re-downloading")
            self.db.delete(video_id)

        logger.info(f"Cache miss for '{track['title']}' — downloading...")
        path = await self._download(track)
        if not path:
            return None

        self.db.upsert(track, path)
        self.db.record_play(video_id)
        self._cache[video_id] = path
        self._cache.move_to_end(video_id)

        for old_id, old_path in self.db.evict_lru(self.cache_limit):
            self._cache.pop(old_id, None)
            try:
                if os.path.exists(old_path):
                    os.remove(old_path)
                    logger.info(f"Cache evicted (limit {self.cache_limit}): {old_path}")
            except OSError as e:
                logger.warning(f"Could not delete evicted file {old_path}: {e}")
        return path
