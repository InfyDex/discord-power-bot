"""Shared fakes for music-system tests. No real network, no real Discord, no real ffmpeg."""
import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402

from cogs.music_system import bridge as bridge_module  # noqa: E402
from cogs.music_system import cog as cog_module  # noqa: E402
from cogs.music_system.player import Track  # noqa: E402
from cogs.music_system.shared_db import SharedDB  # noqa: E402


def make_track(i: int = 1, **overrides) -> Track:
    data = {
        'id': f'video{i:07d}',
        'title': f'Song {i}',
        'duration': 180 + i,
        'thumbnail': f'https://img.example/{i}.jpg',
        'webpage_url': f'https://www.youtube.com/watch?v=video{i:07d}',
    }
    data.update(overrides)
    return Track.from_dict(data)


def track_dict(i: int = 1, **overrides) -> dict:
    t = make_track(i, **overrides)
    return {
        'id': t.id, 'title': t.title, 'duration': t.duration,
        'thumbnail': t.thumbnail, 'webpage_url': t.webpage_url,
    }


class FakeVoiceClient:
    def __init__(self, guild=None, channel=None):
        self.guild = guild
        self.channel = channel
        self._connected = True
        self._playing = False
        self._paused = False
        self.source = None
        self.after = None
        self.play_calls = []
        self.stop_calls = 0
        self.disconnected = False

    def is_connected(self):
        return self._connected

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused

    def play(self, source, after=None):
        self.source = source
        self.after = after
        self._playing = True
        self._paused = False
        self.play_calls.append(source)

    def stop(self):
        self.stop_calls += 1
        self._playing = False
        self._paused = False

    def pause(self):
        self._playing = False
        self._paused = True

    def resume(self):
        self._paused = False
        self._playing = True

    async def disconnect(self, *, force=False):
        self.disconnected = True
        self._connected = False

    async def move_to(self, channel):
        self.channel = channel


class FakeVoiceChannel:
    def __init__(self, name='General', guild=None, channel_id=555):
        self.name = name
        self.guild = guild
        self.id = channel_id

    async def connect(self):
        vc = FakeVoiceClient(guild=self.guild, channel=self)
        return vc


class FakeYouTube:
    """Stands in for YTDLPClient; every knob is a plain attribute tests can set."""

    def __init__(self):
        self.search_results = []
        self.extract_results = []
        self.cached_urls = {}
        self.related_result = None
        self.audio_files = {}       # video_id -> path returned by get_audio_file
        self.audio_requests = []    # every track dict passed to get_audio_file
        self.cookiefile = None
        self.cookies_from_browser = None
        self.db = SimpleNamespace(all_downloaded=lambda: [])

    async def search(self, query, limit=1):
        return self.search_results[:limit]

    async def extract(self, url):
        return list(self.extract_results)

    def lookup_cached_url(self, url):
        return self.cached_urls.get(url)

    async def related(self, video_id, exclude_ids):
        return self.related_result

    async def get_audio_file(self, track):
        self.audio_requests.append(track)
        return self.audio_files.get(track['id'])


def make_guild(guild_id=1234):
    return SimpleNamespace(id=guild_id, name=f'guild-{guild_id}')


def make_member(guild, in_voice=True, channel=None):
    voice = None
    if in_voice:
        voice = SimpleNamespace(channel=channel or FakeVoiceChannel(guild=guild))
    return SimpleNamespace(voice=voice, display_name='tester')


def make_text_channel(name='music'):
    return SimpleNamespace(name=name, send=AsyncMock())


def make_interaction(guild, user, channel=None):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.user = user
    interaction.channel = channel or make_text_channel()
    interaction.response = SimpleNamespace(
        defer=AsyncMock(),
        send_message=AsyncMock(),
    )
    message = SimpleNamespace(edit=AsyncMock())
    interaction.followup = SimpleNamespace(send=AsyncMock(return_value=message))
    interaction.edit_original_response = AsyncMock()
    return interaction


def make_ctx(guild, author, channel=None):
    message = SimpleNamespace(edit=AsyncMock())
    return SimpleNamespace(
        guild=guild,
        author=author,
        channel=channel or make_text_channel(),
        send=AsyncMock(return_value=message),
    )


def sent_text(async_mock_send):
    """Concatenated str of positional/keyword content across all calls to an AsyncMock send."""
    parts = []
    for call in async_mock_send.call_args_list:
        if call.args and call.args[0]:
            parts.append(str(call.args[0]))
        if call.kwargs.get('content'):
            parts.append(str(call.kwargs['content']))
    return ' | '.join(parts)


@pytest.fixture
def fake_youtube():
    return FakeYouTube()


@pytest.fixture
def shared_db(tmp_path):
    """Isolated copy of the control-plane database shared with the music API."""
    db = SharedDB(str(tmp_path / 'tracks.db'))
    yield db
    db.close()


@pytest.fixture
def music_cog(monkeypatch, fake_youtube, shared_db):
    monkeypatch.setattr(cog_module, 'YTDLPClient', lambda: fake_youtube)
    # Keep the bridge off the real downloads/tracks.db during tests.
    monkeypatch.setattr(bridge_module, 'get_shared_db', lambda: shared_db)
    monkeypatch.setattr(discord, 'FFmpegPCMAudio', lambda path, **kw: SimpleNamespace(path=path), raising=True)

    def fake_transformer(source, volume=1.0):
        return SimpleNamespace(inner=source, volume=volume, path=source.path)

    monkeypatch.setattr(discord, 'PCMVolumeTransformer', fake_transformer, raising=True)

    bot = SimpleNamespace(voice_clients=[], loop=asyncio.new_event_loop())
    cog = cog_module.Music(bot)
    yield cog
    bot.loop.close()
