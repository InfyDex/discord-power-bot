"""Bridge tests: the shared control plane between this bot and the music API.

The API is not running here — commands are inserted straight into the shared
database, exactly as the Go server would.
"""
import json
import os
from types import SimpleNamespace

import pytest

from cogs.music_system.player import LoopMode

from conftest import (
    FakeVoiceChannel,
    FakeVoiceClient,
    make_guild,
    make_text_channel,
    make_track,
    track_dict,
)


@pytest.fixture
def guild():
    g = make_guild()
    g.get_channel = lambda channel_id: None
    return g


@pytest.fixture
def bridge(music_cog, guild):
    """Cog bridge wired to a bot that knows about one guild."""
    music_cog.bot.get_guild = lambda gid: guild if int(gid) == guild.id else None
    return music_cog.bridge


def enqueue(db, guild_id, action, payload=None):
    """Insert a command the way the API does."""
    with db._lock:
        cursor = db.conn.execute(
            'INSERT INTO commands (guild_id, action, payload) VALUES (?, ?, ?)',
            (str(guild_id), action, json.dumps(payload or {})),
        )
        db.conn.commit()
        return cursor.lastrowid


def command_row(db, command_id):
    with db._lock:
        row = db.conn.execute(
            'SELECT status, result, error FROM commands WHERE id = ?', (command_id,)
        ).fetchone()
    return dict(row)


async def run_pending(bridge):
    for command in bridge.db.claim_commands():
        await bridge._run_command(command)


def connect_voice(music_cog, guild, channel=None):
    vc = FakeVoiceClient(guild=guild, channel=channel or FakeVoiceChannel(guild=guild))
    music_cog.bot.voice_clients.append(vc)
    return vc


# ---------- shared database ----------

class TestSharedDB:
    def test_mirror_round_trip(self, shared_db):
        state = {
            'status': 'playing',
            'current': track_dict(1),
            'position_seconds': 42,
            'loop_mode': 'queue',
            'autoplay': True,
            'volume': 80,
            'voice_channel_id': '555',
            'voice_channel_name': 'General',
            'text_channel_id': '777',
        }
        shared_db.mirror_guild('1234', state, [track_dict(2), track_dict(3)])

        with shared_db._lock:
            row = dict(shared_db.conn.execute(
                'SELECT * FROM guild_state WHERE guild_id = ?', ('1234',)
            ).fetchone())
            queue = [dict(r) for r in shared_db.conn.execute(
                'SELECT * FROM guild_queue WHERE guild_id = ? ORDER BY position', ('1234',)
            ).fetchall()]

        assert row['status'] == 'playing'
        assert row['current_video_id'] == track_dict(1)['id']
        assert row['position_seconds'] == 42
        assert row['loop_mode'] == 'queue'
        assert row['autoplay'] == 1
        assert row['volume'] == 80
        assert [q['position'] for q in queue] == [1, 2]
        assert queue[0]['video_id'] == track_dict(2)['id']

    def test_mirror_replaces_previous_queue(self, shared_db):
        shared_db.mirror_guild('1234', {'status': 'playing'}, [track_dict(1), track_dict(2)])
        shared_db.mirror_guild('1234', {'status': 'playing'}, [track_dict(9)])

        with shared_db._lock:
            queue = shared_db.conn.execute(
                'SELECT video_id FROM guild_queue WHERE guild_id = ?', ('1234',)
            ).fetchall()

        assert len(queue) == 1
        assert queue[0]['video_id'] == track_dict(9)['id']

    def test_forget_guild(self, shared_db):
        shared_db.mirror_guild('1234', {'status': 'playing'}, [track_dict(1)])
        shared_db.forget_guild('1234')

        with shared_db._lock:
            assert shared_db.conn.execute('SELECT COUNT(*) c FROM guild_state').fetchone()['c'] == 0
            assert shared_db.conn.execute('SELECT COUNT(*) c FROM guild_queue').fetchone()['c'] == 0

    def test_claim_is_once_only(self, shared_db):
        enqueue(shared_db, 1234, 'skip')

        first = shared_db.claim_commands()
        second = shared_db.claim_commands()

        assert len(first) == 1
        assert second == []

    def test_complete_and_fail(self, shared_db):
        done_id = enqueue(shared_db, 1234, 'skip')
        failed_id = enqueue(shared_db, 1234, 'pause')
        shared_db.claim_commands()

        shared_db.complete_command(done_id, 'skipped')
        shared_db.fail_command(failed_id, 'nothing is playing')

        assert command_row(shared_db, done_id) == {
            'status': 'done', 'result': 'skipped', 'error': ''}
        assert command_row(shared_db, failed_id)['status'] == 'failed'
        assert 'nothing is playing' in command_row(shared_db, failed_id)['error']

    def test_heartbeat_upserts_one_row(self, shared_db):
        shared_db.heartbeat(guilds=2, version='1.0.0')
        shared_db.heartbeat(guilds=3, version='1.0.0')

        with shared_db._lock:
            rows = [dict(r) for r in shared_db.conn.execute('SELECT * FROM workers').fetchall()]

        assert len(rows) == 1
        assert rows[0]['name'] == 'bot'
        assert rows[0]['guilds'] == 3

    def test_download_lock_is_exclusive(self, shared_db):
        assert shared_db.acquire_download_lock('vid1') is True

        # A different process cannot take a live lock.
        other_owner, shared_db.owner = shared_db.owner, 'api:999'
        assert shared_db.acquire_download_lock('vid1') is False
        shared_db.owner = other_owner

        shared_db.release_download_lock('vid1')
        assert shared_db.acquire_download_lock('vid1') is True

    def test_stale_download_lock_can_be_stolen(self, shared_db):
        shared_db.acquire_download_lock('vid1')
        with shared_db._lock:
            shared_db.conn.execute(
                "UPDATE download_locks SET acquired_at = datetime('now', '-1 day') WHERE video_id = ?",
                ('vid1',),
            )
            shared_db.conn.commit()

        shared_db.owner = 'api:999'
        assert shared_db.acquire_download_lock('vid1') is True


# ---------- state mirroring ----------

class TestSync:
    def test_sync_publishes_live_player(self, music_cog, guild, bridge):
        channel = FakeVoiceChannel(guild=guild, channel_id=99)
        vc = connect_voice(music_cog, guild, channel)
        vc._playing = True

        player = music_cog._get_player(guild.id, vc)
        player.text_channel = SimpleNamespace(id=4242, name='music')
        player.current = make_track(1)
        player.queue = [make_track(2), make_track(3)]
        player.loop_mode = LoopMode.TRACK
        player.autoplay = True
        player.volume = 0.5
        player.mark_started()

        bridge.sync(guild.id)

        with bridge.db._lock:
            state = dict(bridge.db.conn.execute(
                'SELECT * FROM guild_state WHERE guild_id = ?', (str(guild.id),)
            ).fetchone())
            queue = [dict(r) for r in bridge.db.conn.execute(
                'SELECT * FROM guild_queue WHERE guild_id = ? ORDER BY position', (str(guild.id),)
            ).fetchall()]

        assert state['status'] == 'playing'
        assert state['current_video_id'] == make_track(1).id
        assert state['loop_mode'] == 'track'
        assert state['autoplay'] == 1
        assert state['volume'] == 50
        assert state['voice_channel_id'] == '99'
        assert state['text_channel_id'] == '4242'
        assert [q['video_id'] for q in queue] == [make_track(2).id, make_track(3).id]

    def test_sync_reports_paused(self, music_cog, guild, bridge):
        vc = connect_voice(music_cog, guild)
        vc._playing = False
        vc._paused = True
        player = music_cog._get_player(guild.id, vc)
        player.current = make_track(1)

        bridge.sync(guild.id)

        with bridge.db._lock:
            state = dict(bridge.db.conn.execute(
                'SELECT status FROM guild_state WHERE guild_id = ?', (str(guild.id),)
            ).fetchone())
        assert state['status'] == 'paused'

    def test_sync_without_player_is_noop(self, bridge, guild):
        bridge.sync(guild.id)

        with bridge.db._lock:
            count = bridge.db.conn.execute('SELECT COUNT(*) c FROM guild_state').fetchone()['c']
        assert count == 0

    def test_sync_failure_does_not_raise(self, music_cog, guild, bridge, monkeypatch):
        music_cog._get_player(guild.id, connect_voice(music_cog, guild))
        monkeypatch.setattr(bridge.db, 'mirror_guild', _boom)

        bridge.sync(guild.id)  # must swallow: mirroring cannot break playback


def _boom(*args, **kwargs):
    raise RuntimeError('database is locked')


# ---------- command execution ----------

class TestPlayCommand:
    async def test_play_queues_resolved_tracks_and_starts(self, music_cog, guild, bridge, fake_youtube):
        channel = FakeVoiceChannel(guild=guild, channel_id=99)
        guild.get_channel = lambda cid: channel if cid == 99 else None
        fake_youtube.audio_files[make_track(1).id] = '/tmp/song1.mp3'

        command_id = enqueue(bridge.db, guild.id, 'play', {
            'tracks': [track_dict(1)],
            'voice_channel_id': '99',
        })
        await run_pending(bridge)

        row = command_row(bridge.db, command_id)
        assert row['status'] == 'done', row
        assert 'queued 1' in row['result']

        player = music_cog.players[guild.id]
        assert player.current.id == make_track(1).id
        assert player.voice_client.is_playing()

    async def test_play_falls_back_to_resolving_the_query(self, music_cog, guild, bridge, fake_youtube):
        channel = FakeVoiceChannel(guild=guild, channel_id=99)
        guild.get_channel = lambda cid: channel if cid == 99 else None
        fake_youtube.search_results = [track_dict(7)]
        fake_youtube.audio_files[make_track(7).id] = '/tmp/song7.mp3'

        command_id = enqueue(bridge.db, guild.id, 'play',
                             {'query': 'a song', 'voice_channel_id': '99'})
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'done'
        assert music_cog.players[guild.id].current.id == make_track(7).id

    async def test_play_uses_existing_connection(self, music_cog, guild, bridge, fake_youtube):
        connect_voice(music_cog, guild)
        fake_youtube.audio_files[make_track(1).id] = '/tmp/song1.mp3'

        command_id = enqueue(bridge.db, guild.id, 'play', {'tracks': [track_dict(1)]})
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'done'

    async def test_play_without_any_voice_channel_fails(self, guild, bridge):
        command_id = enqueue(bridge.db, guild.id, 'play', {'tracks': [track_dict(1)]})
        await run_pending(bridge)

        row = command_row(bridge.db, command_id)
        assert row['status'] == 'failed'
        assert 'voice_channel_id' in row['error']

    async def test_play_sets_announce_channel(self, music_cog, guild, bridge, fake_youtube):
        connect_voice(music_cog, guild)
        text_channel = make_text_channel()
        text_channel.id = 4242
        guild.get_channel = lambda cid: text_channel if cid == 4242 else None
        fake_youtube.audio_files[make_track(1).id] = '/tmp/song1.mp3'

        enqueue(bridge.db, guild.id, 'play',
                {'tracks': [track_dict(1)], 'text_channel_id': '4242'})
        await run_pending(bridge)

        assert music_cog.players[guild.id].text_channel is text_channel


class TestControlCommands:
    async def test_skip_stops_the_voice_client(self, music_cog, guild, bridge):
        vc = connect_voice(music_cog, guild)
        vc._playing = True
        music_cog._get_player(guild.id, vc)

        command_id = enqueue(bridge.db, guild.id, 'skip')
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'done'
        assert vc.stop_calls == 1

    async def test_skip_with_nothing_playing_fails(self, music_cog, guild, bridge):
        connect_voice(music_cog, guild)

        command_id = enqueue(bridge.db, guild.id, 'skip')
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'failed'

    async def test_pause_and_resume_move_the_clock(self, music_cog, guild, bridge):
        vc = connect_voice(music_cog, guild)
        vc._playing = True
        player = music_cog._get_player(guild.id, vc)
        player.current = make_track(1)
        player.mark_started()

        await run_pending_after(bridge, guild.id, 'pause')
        assert vc.is_paused()
        assert player.started_at is None
        paused_position = player.position()

        await run_pending_after(bridge, guild.id, 'resume')
        assert vc.is_playing()
        assert player.started_at is not None
        assert player.position() >= paused_position

    async def test_resume_when_not_paused_fails(self, music_cog, guild, bridge):
        vc = connect_voice(music_cog, guild)
        vc._playing = True

        command_id = enqueue(bridge.db, guild.id, 'resume')
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'failed'

    async def test_stop_clears_and_disconnects(self, music_cog, guild, bridge):
        vc = connect_voice(music_cog, guild)
        player = music_cog._get_player(guild.id, vc)
        player.queue = [make_track(2)]
        player.current = make_track(1)

        command_id = enqueue(bridge.db, guild.id, 'stop')
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'done'
        assert player.queue == []
        assert player.current is None
        assert vc.disconnected

    async def test_clear_and_remove(self, music_cog, guild, bridge):
        player = music_cog._get_player(guild.id, connect_voice(music_cog, guild))
        player.queue = [make_track(1), make_track(2), make_track(3)]

        remove_id = enqueue(bridge.db, guild.id, 'remove', {'position': 2})
        await run_pending(bridge)
        assert command_row(bridge.db, remove_id)['status'] == 'done'
        assert [t.id for t in player.queue] == [make_track(1).id, make_track(3).id]

        clear_id = enqueue(bridge.db, guild.id, 'clear')
        await run_pending(bridge)
        assert 'cleared 2' in command_row(bridge.db, clear_id)['result']
        assert player.queue == []

    async def test_remove_out_of_range_fails(self, music_cog, guild, bridge):
        music_cog._get_player(guild.id, connect_voice(music_cog, guild))

        command_id = enqueue(bridge.db, guild.id, 'remove', {'position': 4})
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'failed'

    async def test_shuffle_needs_two_tracks(self, music_cog, guild, bridge):
        player = music_cog._get_player(guild.id, connect_voice(music_cog, guild))
        player.queue = [make_track(1)]

        command_id = enqueue(bridge.db, guild.id, 'shuffle')
        await run_pending(bridge)
        assert command_row(bridge.db, command_id)['status'] == 'failed'

        player.queue = [make_track(1), make_track(2)]
        command_id = enqueue(bridge.db, guild.id, 'shuffle')
        await run_pending(bridge)
        assert command_row(bridge.db, command_id)['status'] == 'done'

    async def test_mix_plays_cached_tracks(self, music_cog, guild, bridge, fake_youtube, tmp_path):
        path = tmp_path / 'cached.mp3'
        path.write_bytes(b'audio')
        row = track_dict(5)
        row['file_path'] = str(path)
        fake_youtube.db = SimpleNamespace(all_downloaded=lambda: [row])
        fake_youtube.audio_files[row['id']] = str(path)

        connect_voice(music_cog, guild)

        command_id = enqueue(bridge.db, guild.id, 'mix')
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'done'
        player = music_cog.players[guild.id]
        assert player.loop_mode is LoopMode.QUEUE
        assert player.current.id == row['id']

    async def test_mix_without_cache_fails(self, music_cog, guild, bridge):
        connect_voice(music_cog, guild)

        command_id = enqueue(bridge.db, guild.id, 'mix')
        await run_pending(bridge)

        assert 'no cached songs' in command_row(bridge.db, command_id)['error']


class TestSettingCommands:
    async def test_loop_volume_autoplay(self, music_cog, guild, bridge):
        vc = connect_voice(music_cog, guild)
        player = music_cog._get_player(guild.id, vc)
        vc.source = SimpleNamespace(volume=1.0)

        await run_pending_after(bridge, guild.id, 'loop', {'mode': 'queue'})
        assert player.loop_mode is LoopMode.QUEUE

        await run_pending_after(bridge, guild.id, 'volume', {'percent': 40})
        assert player.volume == pytest.approx(0.4)
        assert vc.source.volume == pytest.approx(0.4)

        await run_pending_after(bridge, guild.id, 'autoplay', {'enabled': True})
        assert player.autoplay is True

        await run_pending_after(bridge, guild.id, 'autoplay', {'toggle': True})
        assert player.autoplay is False

    async def test_volume_is_clamped(self, music_cog, guild, bridge):
        player = music_cog._get_player(guild.id, connect_voice(music_cog, guild))

        await run_pending_after(bridge, guild.id, 'volume', {'percent': 900})
        assert player.volume == pytest.approx(2.0)

    async def test_invalid_loop_mode_fails(self, music_cog, guild, bridge):
        music_cog._get_player(guild.id, connect_voice(music_cog, guild))

        command_id = enqueue(bridge.db, guild.id, 'loop', {'mode': 'sideways'})
        await run_pending(bridge)

        assert command_row(bridge.db, command_id)['status'] == 'failed'


class TestCommandRouting:
    async def test_unknown_action_fails(self, guild, bridge):
        command_id = enqueue(bridge.db, guild.id, 'teleport')
        await run_pending(bridge)

        row = command_row(bridge.db, command_id)
        assert row['status'] == 'failed'
        assert 'unknown action' in row['error']

    async def test_command_for_unknown_guild_fails(self, bridge):
        command_id = enqueue(bridge.db, 9999, 'skip')
        await run_pending(bridge)

        row = command_row(bridge.db, command_id)
        assert row['status'] == 'failed'
        assert 'not in guild' in row['error']

    async def test_execution_mirrors_state_afterwards(self, music_cog, guild, bridge, fake_youtube):
        connect_voice(music_cog, guild)
        fake_youtube.audio_files[make_track(1).id] = '/tmp/song1.mp3'

        enqueue(bridge.db, guild.id, 'play', {'tracks': [track_dict(1)]})
        await run_pending(bridge)

        with bridge.db._lock:
            state = dict(bridge.db.conn.execute(
                'SELECT status, current_video_id FROM guild_state WHERE guild_id = ?',
                (str(guild.id),),
            ).fetchone())

        assert state['current_video_id'] == make_track(1).id
        assert state['status'] == 'playing'


async def run_pending_after(bridge, guild_id, action, payload=None):
    """Queue one command, run it, and assert it succeeded."""
    command_id = enqueue(bridge.db, guild_id, action, payload)
    await run_pending(bridge)

    row = command_row(bridge.db, command_id)
    assert row['status'] == 'done', row
    return row
