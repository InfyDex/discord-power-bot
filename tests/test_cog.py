"""Music cog command tests. Discord objects are faked; playback sources are stubbed in conftest."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext import commands

from cogs.music_system.cog import Music, _Responder
from cogs.music_system.player import LoopMode

from conftest import (
    FakeVoiceChannel,
    FakeVoiceClient,
    make_ctx,
    make_guild,
    make_interaction,
    make_member,
    make_text_channel,
    make_track,
    sent_text,
    track_dict,
)


@pytest.fixture
def guild():
    return make_guild()


@pytest.fixture
def connected(music_cog, guild):
    """Guild with an established voice connection and player."""
    vc = FakeVoiceClient(guild=guild)
    music_cog.bot.voice_clients.append(vc)
    player = music_cog._get_player(guild.id, vc)
    return SimpleNamespace(vc=vc, player=player)


# ---------- _Responder ----------

class TestResponder:
    async def test_ctx_send_then_edit(self, guild):
        ctx = make_ctx(guild, make_member(guild))
        r = _Responder(ctx)
        await r.send(content='hello')
        ctx.send.assert_awaited_once()
        await r.edit(content='changed')
        ctx.send.return_value.edit.assert_awaited_once_with(content='changed', embed=None)

    async def test_ctx_edit_before_send_does_not_crash(self, guild):
        ctx = make_ctx(guild, make_member(guild))
        r = _Responder(ctx)
        await r.edit(content='first contact')  # must fall back to send, not AttributeError
        ctx.send.assert_awaited_once()

    async def test_interaction_paths(self, guild):
        member = make_member(guild)
        interaction = make_interaction(guild, member)
        r = _Responder(interaction)
        await r.send(content='hi')
        interaction.followup.send.assert_awaited_once()
        await r.edit(content='new')
        interaction.edit_original_response.assert_awaited_once()
        assert r.author is member
        assert r.guild is guild


# ---------- play ----------

class TestPlay:
    async def test_requires_voice(self, music_cog, guild):
        ctx = make_ctx(guild, make_member(guild, in_voice=False))
        await Music.play_prefix.callback(music_cog, ctx, query='some song')
        assert 'voice channel' in sent_text(ctx.send)

    async def test_connect_failure_reports(self, music_cog, guild):
        channel = FakeVoiceChannel(guild=guild)
        channel.connect = AsyncMock(side_effect=discord.ClientException('boom'))
        ctx = make_ctx(guild, make_member(guild, channel=channel))
        await Music.play_prefix.callback(music_cog, ctx, query='song')
        assert 'Failed to connect' in sent_text(ctx.send)

    async def test_no_results(self, music_cog, fake_youtube, guild):
        fake_youtube.search_results = []
        ctx = make_ctx(guild, make_member(guild))
        await Music.play_prefix.callback(music_cog, ctx, query='gibberish')
        edit = ctx.send.return_value.edit
        assert 'Could not find' in str(edit.call_args)

    async def test_single_track_starts_playback(self, music_cog, fake_youtube, guild):
        t = track_dict(1)
        fake_youtube.search_results = [t]
        fake_youtube.audio_files[t['id']] = '/audio/1.mp3'
        ctx = make_ctx(guild, make_member(guild))
        await Music.play_prefix.callback(music_cog, ctx, query='song one')

        player = music_cog.players[guild.id]
        assert player.current.id == t['id']
        assert player.queue == []  # popped into playback
        assert player.voice_client.play_calls, 'voice_client.play was never called'
        assert player.voice_client.play_calls[0].path == '/audio/1.mp3'

    async def test_queue_while_playing_does_not_interrupt(self, music_cog, fake_youtube, guild, connected):
        connected.vc._playing = True
        connected.player.current = make_track(1)
        t = track_dict(2)
        fake_youtube.search_results = [t]
        ctx = make_ctx(guild, make_member(guild))
        await Music.play_prefix.callback(music_cog, ctx, query='song two')
        assert [q.id for q in connected.player.queue] == [t['id']]
        assert connected.vc.play_calls == []  # current song untouched

    async def test_playlist_url_queues_all(self, music_cog, fake_youtube, guild):
        tracks = [track_dict(i) for i in range(3)]
        fake_youtube.extract_results = tracks
        fake_youtube.audio_files[tracks[0]['id']] = '/audio/0.mp3'
        ctx = make_ctx(guild, make_member(guild))
        await Music.play_prefix.callback(music_cog, ctx, query='https://www.youtube.com/playlist?list=PLxyz')
        player = music_cog.players[guild.id]
        # first popped into playback, other two remain queued
        assert player.current.id == tracks[0]['id']
        assert [q.id for q in player.queue] == [tracks[1]['id'], tracks[2]['id']]

    async def test_cached_url_skips_extraction(self, music_cog, fake_youtube, guild):
        url = 'https://www.youtube.com/watch?v=abcdefghijk'
        t = track_dict(1, id='abcdefghijk', webpage_url=url)
        fake_youtube.cached_urls[url] = t
        fake_youtube.audio_files[t['id']] = '/audio/c.mp3'
        fake_youtube.extract = AsyncMock()
        ctx = make_ctx(guild, make_member(guild))
        await Music.play_prefix.callback(music_cog, ctx, query=url)
        fake_youtube.extract.assert_not_awaited()
        assert music_cog.players[guild.id].current.id == t['id']

    async def test_slash_play_defers_then_plays(self, music_cog, fake_youtube, guild):
        t = track_dict(1)
        fake_youtube.search_results = [t]
        fake_youtube.audio_files[t['id']] = '/audio/1.mp3'
        interaction = make_interaction(guild, make_member(guild))
        await Music.play.callback(music_cog, interaction, 'song')
        interaction.response.defer.assert_awaited_once()
        assert music_cog.players[guild.id].current.id == t['id']


# ---------- _advance edge cases ----------

class TestAdvance:
    async def test_no_player_is_noop(self, music_cog, guild):
        await music_cog._advance(guild)  # must not raise

    async def test_disconnected_voice_is_noop(self, music_cog, guild, connected):
        connected.vc._connected = False
        connected.player.queue = [make_track(1)]
        await music_cog._advance(guild)
        assert connected.vc.play_calls == []

    async def test_empty_queue_clears_current(self, music_cog, guild, connected):
        connected.player.current = make_track(1)
        await music_cog._advance(guild)
        assert connected.player.current is None

    async def test_failed_download_skips_to_next(self, music_cog, fake_youtube, guild, connected):
        bad, good = make_track(1), make_track(2)
        fake_youtube.audio_files[good.id] = '/audio/good.mp3'  # bad.id absent -> download fails
        connected.player.queue = [bad, good]
        await music_cog._advance(guild)
        assert connected.player.current.id == good.id
        assert connected.vc.play_calls[0].path == '/audio/good.mp3'

    async def test_all_downloads_failing_terminates(self, music_cog, fake_youtube, guild, connected):
        connected.player.queue = [make_track(i) for i in range(5)]
        await music_cog._advance(guild)
        assert connected.player.current is None
        assert connected.vc.play_calls == []
        assert connected.player.queue == []

    async def test_loop_track_with_failing_download_terminates(self, music_cog, fake_youtube, guild, connected):
        """LoopMode.TRACK + failing download must not retry the same track forever."""
        connected.player.loop_mode = LoopMode.TRACK
        connected.player.current = make_track(1)  # never downloadable
        await music_cog._advance(guild)
        assert connected.vc.play_calls == []
        assert connected.player.current is None

    async def test_loop_queue_drops_failing_track(self, music_cog, fake_youtube, guild, connected):
        """LoopMode.QUEUE must not re-append a track whose download failed on its own turn."""
        connected.player.loop_mode = LoopMode.QUEUE
        bad, good = make_track(1), make_track(2)
        fake_youtube.audio_files[good.id] = '/audio/g.mp3'
        connected.player.queue = [bad, good]
        await music_cog._advance(guild)
        assert connected.player.current.id == good.id
        assert all(q.id != bad.id for q in connected.player.queue)

    async def test_loop_track_replays_current(self, music_cog, fake_youtube, guild, connected):
        t = make_track(1)
        fake_youtube.audio_files[t.id] = '/audio/1.mp3'
        connected.player.loop_mode = LoopMode.TRACK
        connected.player.current = t
        await music_cog._advance(guild)
        assert connected.player.current.id == t.id
        assert connected.vc.play_calls[0].path == '/audio/1.mp3'

    async def test_loop_queue_cycles(self, music_cog, fake_youtube, guild, connected):
        t1, t2 = make_track(1), make_track(2)
        fake_youtube.audio_files = {t1.id: '/a/1.mp3', t2.id: '/a/2.mp3'}
        connected.player.loop_mode = LoopMode.QUEUE
        connected.player.current = t1
        connected.player.queue = [t2]
        await music_cog._advance(guild)
        assert connected.player.current.id == t2.id
        assert [q.id for q in connected.player.queue] == [t1.id]  # t1 re-appended

    async def test_autoplay_pulls_related(self, music_cog, fake_youtube, guild, connected):
        cur = make_track(1)
        rel = track_dict(99)
        fake_youtube.related_result = rel
        fake_youtube.audio_files[rel['id']] = '/audio/rel.mp3'
        connected.player.autoplay = True
        connected.player.current = cur
        await music_cog._advance(guild)
        assert connected.player.current.id == rel['id']
        assert connected.vc.play_calls[0].path == '/audio/rel.mp3'

    async def test_autoplay_no_related_stops(self, music_cog, fake_youtube, guild, connected):
        fake_youtube.related_result = None
        connected.player.autoplay = True
        connected.player.current = make_track(1)
        await music_cog._advance(guild)
        assert connected.player.current is None
        assert connected.vc.play_calls == []

    async def test_volume_applied_to_source(self, music_cog, fake_youtube, guild, connected):
        t = make_track(1)
        fake_youtube.audio_files[t.id] = '/a/1.mp3'
        connected.player.volume = 0.35
        connected.player.queue = [t]
        await music_cog._advance(guild)
        assert connected.vc.play_calls[0].volume == 0.35


# ---------- now-playing announcements ----------

def _last_embed(send_mock) -> discord.Embed:
    return send_mock.call_args.kwargs['embed']


class TestNowPlayingAnnounce:
    async def test_announced_on_track_switch(self, music_cog, fake_youtube, guild, connected):
        channel = make_text_channel()
        connected.player.text_channel = channel
        t = make_track(1)
        fake_youtube.audio_files[t.id] = '/a/1.mp3'
        connected.player.queue = [t]
        await music_cog._advance(guild)
        channel.send.assert_awaited_once()
        embed = _last_embed(channel.send)
        assert embed.title == '🎶 Now Playing'
        assert t.title in embed.description

    async def test_announces_each_new_song(self, music_cog, fake_youtube, guild, connected):
        channel = make_text_channel()
        connected.player.text_channel = channel
        t1, t2 = make_track(1), make_track(2)
        fake_youtube.audio_files = {t1.id: '/a/1.mp3', t2.id: '/a/2.mp3'}
        connected.player.queue = [t1, t2]
        await music_cog._advance(guild)
        connected.vc._playing = False
        await music_cog._advance(guild)
        assert channel.send.await_count == 2
        assert t2.title in _last_embed(channel.send).description

    async def test_repeat_of_same_track_not_reannounced(self, music_cog, fake_youtube, guild, connected):
        """Loop-track repeats shouldn't spam the channel with the same embed every lap."""
        channel = make_text_channel()
        connected.player.text_channel = channel
        connected.player.loop_mode = LoopMode.TRACK
        t = make_track(1)
        fake_youtube.audio_files[t.id] = '/a/1.mp3'
        connected.player.queue = [t]
        await music_cog._advance(guild)
        await music_cog._advance(guild)
        assert channel.send.await_count == 1

    async def test_no_channel_is_silent(self, music_cog, fake_youtube, guild, connected):
        connected.player.text_channel = None
        t = make_track(1)
        fake_youtube.audio_files[t.id] = '/a/1.mp3'
        connected.player.queue = [t]
        await music_cog._advance(guild)  # must not raise
        assert connected.vc.play_calls

    async def test_send_failure_does_not_break_playback(self, music_cog, fake_youtube, guild, connected):
        channel = make_text_channel()
        channel.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=403), 'forbidden'))
        connected.player.text_channel = channel
        t = make_track(1)
        fake_youtube.audio_files[t.id] = '/a/1.mp3'
        connected.player.queue = [t]
        await music_cog._advance(guild)
        assert connected.vc.play_calls  # playback survived the failed announcement

    async def test_play_sets_announce_channel(self, music_cog, fake_youtube, guild):
        t = track_dict(1)
        fake_youtube.search_results = [t]
        fake_youtube.audio_files[t['id']] = '/a/1.mp3'
        channel = make_text_channel()
        ctx = make_ctx(guild, make_member(guild), channel=channel)
        await Music.play_prefix.callback(music_cog, ctx, query='song')
        assert music_cog.players[guild.id].text_channel is channel
        channel.send.assert_awaited_once()

    async def test_mix_sets_announce_channel(self, music_cog, fake_youtube, guild, tmp_path):
        p = tmp_path / '0.mp3'
        p.write_bytes(b'x')
        row = dict(track_dict(0), file_path=str(p))
        fake_youtube.db.all_downloaded = lambda: [row]
        fake_youtube.audio_files[row['id']] = str(p)
        channel = make_text_channel()
        ctx = make_ctx(guild, make_member(guild), channel=channel)
        await Music.mix.callback(music_cog, ctx)
        assert music_cog.players[guild.id].text_channel is channel
        channel.send.assert_awaited_once()

    async def test_stop_resets_announce_state(self, music_cog, guild, connected):
        connected.player.last_announced_id = 'video0000001'
        interaction = make_interaction(guild, make_member(guild))
        await Music.stop.callback(music_cog, interaction)
        assert connected.player.last_announced_id is None

    def test_embed_omits_duration_when_zero(self):
        embed = Music._now_playing_embed(make_track(1, duration=0))
        assert embed.fields == []

    def test_embed_formats_duration(self):
        embed = Music._now_playing_embed(make_track(1, duration=605))
        assert next(f.value for f in embed.fields if f.name == 'Duration') == '10:05'


# ---------- playback controls ----------

class TestSkip:
    async def test_skip_playing(self, music_cog, guild, connected):
        connected.vc._playing = True
        interaction = make_interaction(guild, make_member(guild))
        await Music.skip.callback(music_cog, interaction)
        assert connected.vc.stop_calls == 1
        assert 'Skipped' in sent_text(interaction.response.send_message)

    async def test_skip_paused_song_works(self, music_cog, guild, connected):
        """A paused song is still the current song; skip must skip it, not claim nothing is playing."""
        connected.vc._paused = True
        interaction = make_interaction(guild, make_member(guild))
        await Music.skip.callback(music_cog, interaction)
        assert connected.vc.stop_calls == 1
        assert 'Skipped' in sent_text(interaction.response.send_message)

    async def test_skip_nothing_playing(self, music_cog, guild, connected):
        interaction = make_interaction(guild, make_member(guild))
        await Music.skip.callback(music_cog, interaction)
        assert connected.vc.stop_calls == 0
        assert 'Nothing is playing' in sent_text(interaction.response.send_message)

    async def test_skip_no_voice_client(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        await Music.skip.callback(music_cog, interaction)
        assert 'Nothing is playing' in sent_text(interaction.response.send_message)

    async def test_prefix_skip_paused(self, music_cog, guild, connected):
        connected.vc._paused = True
        ctx = make_ctx(guild, make_member(guild))
        await Music.skip_prefix.callback(music_cog, ctx)
        assert connected.vc.stop_calls == 1


class TestPauseResume:
    async def test_pause_playing(self, music_cog, guild, connected):
        connected.vc._playing = True
        interaction = make_interaction(guild, make_member(guild))
        await Music.pause.callback(music_cog, interaction)
        assert connected.vc.is_paused()
        assert 'Paused' in sent_text(interaction.response.send_message)

    async def test_pause_when_already_paused_says_so(self, music_cog, guild, connected):
        connected.vc._paused = True
        interaction = make_interaction(guild, make_member(guild))
        await Music.pause.callback(music_cog, interaction)
        text = sent_text(interaction.response.send_message)
        assert 'Nothing is playing' not in text
        assert 'paused' in text.lower()

    async def test_pause_nothing_playing(self, music_cog, guild, connected):
        interaction = make_interaction(guild, make_member(guild))
        await Music.pause.callback(music_cog, interaction)
        assert 'Nothing is playing' in sent_text(interaction.response.send_message)

    async def test_resume_paused(self, music_cog, guild, connected):
        connected.vc._paused = True
        interaction = make_interaction(guild, make_member(guild))
        await Music.resume.callback(music_cog, interaction)
        assert connected.vc.is_playing()
        assert 'Resumed' in sent_text(interaction.response.send_message)

    async def test_resume_not_paused(self, music_cog, guild, connected):
        connected.vc._playing = True
        interaction = make_interaction(guild, make_member(guild))
        await Music.resume.callback(music_cog, interaction)
        assert 'not paused' in sent_text(interaction.response.send_message)


class TestStop:
    async def test_stop_clears_and_disconnects(self, music_cog, guild, connected):
        connected.vc._playing = True
        connected.player.queue = [make_track(1), make_track(2)]
        connected.player.current = make_track(3)
        interaction = make_interaction(guild, make_member(guild))
        await Music.stop.callback(music_cog, interaction)
        assert connected.player.queue == []
        assert connected.player.current is None
        assert connected.vc.disconnected

    async def test_stop_preserves_settings(self, music_cog, guild, connected):
        """Loop/autoplay/volume are user prefs that survive a stop (documented behavior)."""
        connected.player.loop_mode = LoopMode.QUEUE
        connected.player.autoplay = True
        connected.player.volume = 0.5
        interaction = make_interaction(guild, make_member(guild))
        await Music.stop.callback(music_cog, interaction)
        assert connected.player.loop_mode is LoopMode.QUEUE
        assert connected.player.autoplay is True
        assert connected.player.volume == 0.5

    async def test_stop_not_connected(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        await Music.stop.callback(music_cog, interaction)
        assert 'Not connected' in sent_text(interaction.response.send_message)


# ---------- queue management ----------

def _sent_embed(send_mock) -> discord.Embed:
    call = send_mock.call_args
    return call.kwargs.get('embed') or call.args[0]


class TestQueueCommand:
    async def test_empty_queue(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        await Music.show_queue.callback(music_cog, interaction)
        embed = _sent_embed(interaction.response.send_message)
        up_next = next(f for f in embed.fields if f.name == '📃 Up Next')
        assert up_next.value == 'Queue is empty'

    async def test_now_playing_and_overflow_footer(self, music_cog, guild, connected):
        connected.player.current = make_track(0)
        connected.player.queue = [make_track(i) for i in range(1, 13)]  # 12 queued
        interaction = make_interaction(guild, make_member(guild))
        await Music.show_queue.callback(music_cog, interaction)
        embed = _sent_embed(interaction.response.send_message)
        assert any(f.name == '🎶 Now Playing' for f in embed.fields)
        up_next = next(f for f in embed.fields if f.name == '📃 Up Next')
        assert up_next.value.count('\n') == 9  # 10 lines shown
        assert '2 more songs' in embed.footer.text

    async def test_shows_loop_and_autoplay_state(self, music_cog, guild, connected):
        connected.player.loop_mode = LoopMode.TRACK
        connected.player.autoplay = True
        interaction = make_interaction(guild, make_member(guild))
        await Music.show_queue.callback(music_cog, interaction)
        embed = _sent_embed(interaction.response.send_message)
        assert next(f for f in embed.fields if f.name == 'Loop').value == 'track'
        assert next(f for f in embed.fields if f.name == 'Autoplay').value == 'on'


class TestNowPlaying:
    async def test_nothing(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        await Music.now_playing_cmd.callback(music_cog, interaction)
        assert 'Nothing is playing' in sent_text(interaction.response.send_message)

    async def test_current(self, music_cog, guild, connected):
        t = make_track(1)
        connected.player.current = t
        interaction = make_interaction(guild, make_member(guild))
        await Music.now_playing_cmd.callback(music_cog, interaction)
        embed = _sent_embed(interaction.response.send_message)
        assert t.title in embed.description


class TestClearRemove:
    async def test_clear_empty(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        await Music.clear.callback(music_cog, interaction)
        assert 'already empty' in sent_text(interaction.response.send_message)

    async def test_clear_counts(self, music_cog, guild, connected):
        connected.player.queue = [make_track(i) for i in range(3)]
        interaction = make_interaction(guild, make_member(guild))
        await Music.clear.callback(music_cog, interaction)
        assert connected.player.queue == []
        assert '3' in sent_text(interaction.response.send_message)

    async def test_clear_keeps_current_song_playing(self, music_cog, guild, connected):
        connected.player.current = make_track(9)
        connected.player.queue = [make_track(1)]
        interaction = make_interaction(guild, make_member(guild))
        await Music.clear.callback(music_cog, interaction)
        assert connected.player.current is not None

    @pytest.mark.parametrize('pos', [0, -1, 99])
    async def test_remove_invalid_positions(self, music_cog, guild, connected, pos):
        connected.player.queue = [make_track(1), make_track(2)]
        ctx = make_ctx(guild, make_member(guild))
        await Music.remove_from_queue.callback(music_cog, ctx, pos)
        assert 'Invalid position' in sent_text(ctx.send)
        assert len(connected.player.queue) == 2

    async def test_remove_valid_position(self, music_cog, guild, connected):
        t1, t2, t3 = make_track(1), make_track(2), make_track(3)
        connected.player.queue = [t1, t2, t3]
        ctx = make_ctx(guild, make_member(guild))
        await Music.remove_from_queue.callback(music_cog, ctx, 2)
        assert [q.id for q in connected.player.queue] == [t1.id, t3.id]
        assert t2.title in sent_text(ctx.send)

    async def test_remove_from_empty_queue(self, music_cog, guild):
        ctx = make_ctx(guild, make_member(guild))
        await Music.remove_from_queue.callback(music_cog, ctx, 1)
        assert 'Invalid position' in sent_text(ctx.send)


class TestShuffleCommand:
    async def test_too_few(self, music_cog, guild, connected):
        connected.player.queue = [make_track(1)]
        interaction = make_interaction(guild, make_member(guild))
        await Music.shuffle.callback(music_cog, interaction)
        assert 'Not enough songs' in sent_text(interaction.response.send_message)

    async def test_shuffles(self, music_cog, guild, connected):
        connected.player.queue = [make_track(i) for i in range(20)]
        interaction = make_interaction(guild, make_member(guild))
        await Music.shuffle.callback(music_cog, interaction)
        assert '20' in sent_text(interaction.response.send_message)
        assert len(connected.player.queue) == 20


# ---------- mix ----------

class TestMix:
    async def test_requires_voice(self, music_cog, guild):
        ctx = make_ctx(guild, make_member(guild, in_voice=False))
        await Music.mix.callback(music_cog, ctx)
        assert 'voice channel' in sent_text(ctx.send)

    async def test_no_cached_songs(self, music_cog, fake_youtube, guild):
        fake_youtube.db.all_downloaded = lambda: []
        ctx = make_ctx(guild, make_member(guild))
        await Music.mix.callback(music_cog, ctx)
        assert 'No cached songs' in sent_text(ctx.send)

    async def test_rows_with_missing_files_filtered(self, music_cog, fake_youtube, guild, tmp_path):
        rows = [dict(track_dict(i), file_path=str(tmp_path / f'{i}.mp3')) for i in range(2)]
        # only file 0 exists on disk
        (tmp_path / '0.mp3').write_bytes(b'x')
        fake_youtube.db.all_downloaded = lambda: rows
        fake_youtube.audio_files[rows[0]['id']] = rows[0]['file_path']
        ctx = make_ctx(guild, make_member(guild))
        await Music.mix.callback(music_cog, ctx)
        assert 'Mixing **1**' in sent_text(ctx.send)

    async def test_all_files_missing_treated_as_empty(self, music_cog, fake_youtube, guild, tmp_path):
        rows = [dict(track_dict(1), file_path=str(tmp_path / 'ghost.mp3'))]
        fake_youtube.db.all_downloaded = lambda: rows
        ctx = make_ctx(guild, make_member(guild))
        await Music.mix.callback(music_cog, ctx)
        assert 'No cached songs' in sent_text(ctx.send)

    async def test_mix_sets_queue_loop_and_plays(self, music_cog, fake_youtube, guild, tmp_path):
        rows = []
        for i in range(3):
            p = tmp_path / f'{i}.mp3'
            p.write_bytes(b'x')
            row = dict(track_dict(i), file_path=str(p))
            rows.append(row)
            fake_youtube.audio_files[row['id']] = str(p)
        fake_youtube.db.all_downloaded = lambda: rows
        ctx = make_ctx(guild, make_member(guild))
        await Music.mix.callback(music_cog, ctx)
        player = music_cog.players[guild.id]
        assert player.loop_mode is LoopMode.QUEUE
        assert player.current is not None
        assert player.voice_client.play_calls  # started playing
        # 3 tracks total: 1 playing + 2 queued
        assert len(player.queue) == 2


# ---------- settings ----------

class TestSettings:
    async def test_loop_cmd_sets_mode(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        choice = app_commands.Choice(name='Queue', value='queue')
        await Music.loop_cmd.callback(music_cog, interaction, choice)
        assert music_cog.players[guild.id].loop_mode is LoopMode.QUEUE

    async def test_autoplay_toggles(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        await Music.autoplay.callback(music_cog, interaction)
        assert music_cog.players[guild.id].autoplay is True
        await Music.autoplay.callback(music_cog, interaction)
        assert music_cog.players[guild.id].autoplay is False

    async def test_volume_updates_player_and_live_source(self, music_cog, guild, connected):
        connected.vc.source = SimpleNamespace(volume=1.0)
        interaction = make_interaction(guild, make_member(guild))
        await Music.volume.callback(music_cog, interaction, 150)
        assert connected.player.volume == 1.5
        assert connected.vc.source.volume == 1.5

    async def test_volume_zero(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        await Music.volume.callback(music_cog, interaction, 0)
        assert music_cog.players[guild.id].volume == 0.0


# ---------- search ----------

class TestSearch:
    async def test_requires_voice(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild, in_voice=False))
        await Music.search.callback(music_cog, interaction, 'query')
        assert 'voice channel' in sent_text(interaction.followup.send)

    async def test_no_results(self, music_cog, fake_youtube, guild):
        fake_youtube.search_results = []
        interaction = make_interaction(guild, make_member(guild))
        await Music.search.callback(music_cog, interaction, 'query')
        assert 'No results' in sent_text(interaction.followup.send)

    async def _run_search(self, music_cog, fake_youtube, guild, n=3):
        fake_youtube.search_results = [track_dict(i) for i in range(n)]
        interaction = make_interaction(guild, make_member(guild))
        await Music.search.callback(music_cog, interaction, 'query')
        view = interaction.followup.send.call_args.kwargs['view']
        return interaction, view

    async def test_sends_view_with_options(self, music_cog, fake_youtube, guild):
        _, view = await self._run_search(music_cog, fake_youtube, guild, n=5)
        assert len(view.children[0].options) == 5

    async def test_choose_queues_and_plays(self, music_cog, fake_youtube, guild):
        _, view = await self._run_search(music_cog, fake_youtube, guild)
        chosen = track_dict(0)
        fake_youtube.audio_files[chosen['id']] = '/audio/chosen.mp3'
        select_interaction = make_interaction(guild, make_member(guild))
        await view.children[0]._on_choose(select_interaction, chosen)
        assert music_cog.players[guild.id].current.id == chosen['id']

    async def test_choose_after_leaving_voice_is_friendly(self, music_cog, fake_youtube, guild):
        """User picks a result after disconnecting from voice: must get an error, not a crash."""
        _, view = await self._run_search(music_cog, fake_youtube, guild)
        select_interaction = make_interaction(guild, make_member(guild, in_voice=False))
        await view.children[0]._on_choose(select_interaction, track_dict(0))
        assert 'voice channel' in sent_text(select_interaction.followup.send)


# ---------- guild-only guards ----------

class TestDMGuards:
    async def test_slash_commands_blocked_in_dm(self, music_cog):
        interaction = make_interaction(None, make_member(None, in_voice=False))
        interaction.guild = None
        allowed = await music_cog.interaction_check(interaction)
        assert allowed is False
        assert 'server' in sent_text(interaction.response.send_message).lower()

    async def test_slash_commands_allowed_in_guild(self, music_cog, guild):
        interaction = make_interaction(guild, make_member(guild))
        assert await music_cog.interaction_check(interaction) is True

    async def test_prefix_commands_blocked_in_dm(self, music_cog):
        ctx = make_ctx(None, make_member(None, in_voice=False))
        with pytest.raises(commands.NoPrivateMessage):
            await music_cog.cog_check(ctx)

    async def test_prefix_commands_allowed_in_guild(self, music_cog, guild):
        ctx = make_ctx(guild, make_member(guild))
        assert await music_cog.cog_check(ctx) is True


# ---------- embeds ----------

class TestQueueEmbed:
    def test_single_track(self):
        t = make_track(1, duration=125)
        embed = Music._queue_embed([t])
        assert embed.title == '🎵 Added to Queue'
        assert next(f.value for f in embed.fields if f.name == 'Duration') == '2:05'

    def test_duration_zero(self):
        embed = Music._queue_embed([make_track(1, duration=0)])
        assert next(f.value for f in embed.fields if f.name == 'Duration') == '0:00'

    def test_playlist_preview_truncates_titles(self):
        long_title = 'x' * 80
        tracks = [make_track(i, title=long_title) for i in range(7)]
        embed = Music._queue_embed(tracks)
        assert '7' in embed.description
        preview = next(f.value for f in embed.fields if f.name == 'First Songs')
        assert preview.count('\n') == 4  # 5 lines
        assert 'x' * 51 not in preview  # each title cut at 50 chars
        assert '2 more songs' in embed.footer.text
