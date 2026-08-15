"""YTDLPClient tests: video-id parsing, cookie resolution, cache/eviction, download plumbing.
All network and subprocess calls are stubbed.
"""
import base64
import os
from unittest.mock import AsyncMock

import pytest

from cogs.music_system import youtube as yt_mod
from cogs.music_system.youtube import YTDLPClient, extract_video_id, resolve_cookies

from conftest import track_dict


VID = 'dQw4w9WgXcQ'


class TestExtractVideoId:
    @pytest.mark.parametrize('url', [
        f'https://www.youtube.com/watch?v={VID}',
        f'https://youtube.com/watch?v={VID}&t=42s',
        f'https://youtu.be/{VID}',
        f'https://youtu.be/{VID}?si=share',
        f'https://www.youtube.com/shorts/{VID}',
        f'https://www.youtube.com/embed/{VID}',
        f'https://music.youtube.com/watch?v={VID}&list=RD{VID}',
    ])
    def test_valid_urls(self, url):
        assert extract_video_id(url) == VID

    @pytest.mark.parametrize('url', [
        'https://example.com/watch?v=abc',
        'https://www.youtube.com/playlist?list=PL123',
        'not a url',
        '',
    ])
    def test_invalid_urls(self, url):
        assert extract_video_id(url) is None


class TestResolveCookies:
    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch, tmp_path):
        for var in ('YOUTUBE_COOKIES_B64', 'YOUTUBE_COOKIES_FILE', 'COOKIES_FROM_BROWSER'):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(yt_mod, 'BOT_ROOT', str(tmp_path))  # no stray cookies.txt

    def test_nothing_configured(self):
        assert resolve_cookies() == (None, None)

    def test_b64_env_wins_and_is_popped(self, monkeypatch):
        monkeypatch.setenv('YOUTUBE_COOKIES_B64', base64.b64encode(b'cookiedata').decode())
        path, browser = resolve_cookies()
        assert browser is None
        assert path and os.path.exists(path)
        with open(path, 'rb') as f:
            assert f.read() == b'cookiedata'
        assert 'YOUTUBE_COOKIES_B64' not in os.environ
        os.remove(path)

    def test_invalid_b64_falls_through(self, monkeypatch):
        monkeypatch.setenv('YOUTUBE_COOKIES_B64', '!!!not-base64!!!')
        assert resolve_cookies() == (None, None)

    def test_cookies_file_env(self, monkeypatch, tmp_path):
        f = tmp_path / 'ck.txt'
        f.write_text('data')
        monkeypatch.setenv('YOUTUBE_COOKIES_FILE', str(f))
        assert resolve_cookies() == (str(f), None)

    def test_cookies_file_env_missing_file_ignored(self, monkeypatch, tmp_path):
        monkeypatch.setenv('YOUTUBE_COOKIES_FILE', str(tmp_path / 'ghost.txt'))
        assert resolve_cookies() == (None, None)

    def test_default_cookies_txt_in_root(self, tmp_path):
        (tmp_path / 'cookies.txt').write_text('data')
        path, browser = resolve_cookies()
        assert path == str(tmp_path / 'cookies.txt')
        assert browser is None

    def test_browser_spec_plain(self, monkeypatch):
        monkeypatch.setenv('COOKIES_FROM_BROWSER', 'chrome')
        assert resolve_cookies() == (None, ('chrome',))

    def test_browser_spec_with_profile(self, monkeypatch):
        monkeypatch.setenv('COOKIES_FROM_BROWSER', 'chrome:Profile 1')
        assert resolve_cookies() == (None, ('chrome', 'Profile 1'))


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # 'downloads/' + tracks.db land in tmp
    monkeypatch.setattr(yt_mod, 'find_ytdlp_cmd', lambda: ['yt-dlp-fake'])
    monkeypatch.setattr(yt_mod, 'resolve_cookies', lambda: (None, None))
    c = YTDLPClient(cache_limit=3)
    yield c
    c.db.conn.close()


def _write_audio(client, video_id, content=b'mp3'):
    path = os.path.join(yt_mod.DOWNLOAD_DIR, f'{video_id}.mp3')
    with open(path, 'wb') as f:
        f.write(content)
    return path


class TestToTrackDict:
    def test_full_entry(self):
        entry = {'id': 'x', 'title': 'T', 'duration': 9, 'thumbnail': 'th', 'webpage_url': 'u'}
        assert YTDLPClient._to_track_dict(entry) == {
            'id': 'x', 'title': 'T', 'duration': 9, 'thumbnail': 'th', 'webpage_url': 'u',
        }

    def test_none_duration_and_missing_url(self):
        entry = {'id': 'x', 'title': 'T', 'duration': None}
        d = YTDLPClient._to_track_dict(entry)
        assert d['duration'] == 0
        assert d['webpage_url'] == 'https://www.youtube.com/watch?v=x'
        assert d['thumbnail'] == ''


class TestLookupCachedUrl:
    def test_miss_unknown_video(self, client):
        assert client.lookup_cached_url(f'https://youtu.be/{VID}') is None

    def test_non_youtube_url(self, client):
        assert client.lookup_cached_url('https://example.com/song') is None

    def test_hit_when_downloaded_and_file_exists(self, client):
        t = track_dict(1, id=VID, webpage_url=f'https://www.youtube.com/watch?v={VID}')
        path = _write_audio(client, VID)
        client.db.upsert(t, path)
        hit = client.lookup_cached_url(f'https://www.youtube.com/watch?v={VID}')
        assert hit is not None and hit['id'] == VID
        assert 'file_path' not in hit  # track dict shape, not db row

    def test_miss_when_file_deleted(self, client):
        t = track_dict(1, id=VID)
        client.db.upsert(t, os.path.join(yt_mod.DOWNLOAD_DIR, f'{VID}.mp3'))  # never written
        assert client.lookup_cached_url(f'https://www.youtube.com/watch?v={VID}') is None

    def test_playlist_url_bypasses_cache(self, client):
        """A watch URL carrying a playlist must NOT short-circuit to the single cached video,
        otherwise pasting a playlist whose first video is cached silently drops the playlist."""
        t = track_dict(1, id=VID)
        path = _write_audio(client, VID)
        client.db.upsert(t, path)
        url = f'https://www.youtube.com/watch?v={VID}&list=PLabcdef123456'
        assert client.lookup_cached_url(url) is None


class TestGetAudioFile:
    async def test_download_on_miss_records_db(self, client):
        t = track_dict(1)

        async def fake_download(track):
            return _write_audio(client, track['id'])

        client._download = AsyncMock(side_effect=fake_download)
        path = await client.get_audio_file(t)
        assert path and os.path.exists(path)
        row = client.db.get(t['id'])
        assert row['file_path'] == path
        count = client.db.conn.execute(
            'SELECT play_count FROM tracks WHERE video_id = ?', (t['id'],)
        ).fetchone()[0]
        assert count == 1

    async def test_memory_cache_hit_skips_download(self, client):
        t = track_dict(1)
        path = _write_audio(client, t['id'])
        client._cache[t['id']] = path
        client.db.upsert(t, path)
        client._download = AsyncMock()
        assert await client.get_audio_file(t) == path
        client._download.assert_not_awaited()

    async def test_db_hit_after_restart_skips_download(self, client):
        # simulate restart: db row exists, memory cache empty
        t = track_dict(1)
        path = _write_audio(client, t['id'])
        client.db.upsert(t, path)
        client._download = AsyncMock()
        assert await client.get_audio_file(t) == path
        client._download.assert_not_awaited()
        assert client._cache[t['id']] == path  # re-warmed

    async def test_stale_db_row_triggers_redownload(self, client):
        t = track_dict(1)
        client.db.upsert(t, os.path.join(yt_mod.DOWNLOAD_DIR, f"{t['id']}.mp3"))  # file missing

        async def fake_download(track):
            return _write_audio(client, track['id'], b'fresh')

        client._download = AsyncMock(side_effect=fake_download)
        path = await client.get_audio_file(t)
        assert path and os.path.exists(path)
        client._download.assert_awaited_once()

    async def test_stale_memory_entry_falls_back(self, client):
        t = track_dict(1)
        client._cache[t['id']] = os.path.join(yt_mod.DOWNLOAD_DIR, 'ghost.mp3')

        async def fake_download(track):
            return _write_audio(client, track['id'])

        client._download = AsyncMock(side_effect=fake_download)
        assert await client.get_audio_file(t) is not None

    async def test_download_failure_returns_none(self, client):
        t = track_dict(1)
        client._download = AsyncMock(return_value=None)
        assert await client.get_audio_file(t) is None
        assert client.db.get(t['id']) is None  # nothing recorded

    async def test_lru_eviction_deletes_files_past_limit(self, client):
        # cache_limit=3; download 4 distinct tracks, oldest-played gets evicted from db+disk
        async def fake_download(track):
            return _write_audio(client, track['id'])

        client._download = AsyncMock(side_effect=fake_download)
        paths = []
        for i in range(4):
            t = track_dict(i)
            paths.append(await client.get_audio_file(t))
            # spread recency so ordering is deterministic
            client.db.conn.execute(
                "UPDATE tracks SET last_played_at = datetime('2026-01-01', ? || ' minutes') WHERE video_id = ?",
                (str(i), t['id']),
            )
            client.db.conn.commit()
        assert not os.path.exists(paths[0])            # evicted
        assert all(os.path.exists(p) for p in paths[1:])
        assert client.db.get(track_dict(0)['id']) is None
        assert track_dict(0)['id'] not in client._cache


class TestDownloadCmd:
    def test_basic_shape(self, client):
        t = track_dict(1)
        cmd = client._download_cmd(t)
        assert cmd[0] == 'yt-dlp-fake'
        assert cmd[-1] == t['webpage_url']
        assert '-x' in cmd and 'mp3' in cmd
        assert '--no-playlist' in cmd
        joined = ' '.join(cmd)
        assert '%(id)s.%(ext)s' in joined
        assert '--cookies' not in cmd

    def test_cookiefile_flag(self, client):
        client.cookiefile = '/tmp/ck.txt'
        cmd = client._download_cmd(track_dict(1))
        assert cmd[cmd.index('--cookies') + 1] == '/tmp/ck.txt'

    def test_browser_cookie_flag(self, client):
        client.cookies_from_browser = ('chrome', 'Profile 1')
        cmd = client._download_cmd(track_dict(1))
        assert cmd[cmd.index('--cookies-from-browser') + 1] == 'chrome:Profile 1'
