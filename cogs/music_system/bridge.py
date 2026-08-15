"""Bridge between the music API and this bot.

The API cannot join a voice channel, so it writes commands into the shared
database and the bot executes them here. In return the bot mirrors its live
player state and queue back, so the API can report what is actually playing —
including tracks queued from Discord with `!play`.

Both halves are optional: with the API stopped the bot behaves exactly as
before, and with the bot stopped API commands simply stay pending.
"""
import logging

import discord
from discord.ext import tasks

from .player import LoopMode, Track
from .shared_db import get_shared_db

logger = logging.getLogger('discord.music')

BRIDGE_VERSION = '1.0.0'


class MusicBridge:
    """Executes API commands and mirrors player state into the shared database."""

    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.db = get_shared_db()

    def start(self):
        if not self.command_loop.is_running():
            self.command_loop.start()
        if not self.sync_loop.is_running():
            self.sync_loop.start()
        if not self.heartbeat_loop.is_running():
            self.heartbeat_loop.start()
        logger.info("Music bridge started (shared database control plane)")

    def stop(self):
        for loop in (self.command_loop, self.sync_loop, self.heartbeat_loop):
            if loop.is_running():
                loop.cancel()

    # ---------- background loops ----------

    @tasks.loop(seconds=10)
    async def heartbeat_loop(self):
        """Tell the API the bot is alive; it refuses to promise execution otherwise."""
        try:
            self.db.heartbeat(guilds=len(self.bot.guilds), version=BRIDGE_VERSION)
        except Exception as e:
            logger.warning(f"Bridge heartbeat failed: {e}")

    @tasks.loop(seconds=1)
    async def command_loop(self):
        """Claim and run whatever the API has queued."""
        try:
            commands = self.db.claim_commands()
        except Exception as e:
            logger.warning(f"Could not claim API commands: {e}")
            return

        for command in commands:
            await self._run_command(command)

    @tasks.loop(seconds=5)
    async def sync_loop(self):
        """Keep the mirror fresh, including the playback position."""
        for guild_id in list(self.cog.players.keys()):
            self.sync(guild_id)

    @command_loop.before_loop
    @sync_loop.before_loop
    @heartbeat_loop.before_loop
    async def _before_loops(self):
        await self.bot.wait_until_ready()

    # ---------- mirror ----------

    def sync(self, guild_id: int):
        """Publish one guild's live player state for the API to read.

        Mirroring is best-effort: a database hiccup must never interrupt what is
        playing in Discord.
        """
        player = self.cog.players.get(guild_id)
        if not player:
            return

        try:
            voice_client = player.voice_client
            voice_channel = getattr(voice_client, 'channel', None)

            status = 'idle'
            if voice_client and voice_client.is_playing():
                status = 'playing'
            elif voice_client and voice_client.is_paused():
                status = 'paused'
            elif player.current:
                status = 'loading'

            state = {
                'status': status,
                'current': _track_dict(player.current),
                'position_seconds': int(player.position()),
                'loop_mode': player.loop_mode.value,
                'autoplay': player.autoplay,
                'volume': int(player.volume * 100),
                'voice_channel_id': _id_of(voice_channel),
                'voice_channel_name': getattr(voice_channel, 'name', '') or '',
                'text_channel_id': _id_of(player.text_channel),
            }
            queue = [_track_dict(track) for track in player.queue]

            self.db.mirror_guild(str(guild_id), state, queue)
        except Exception as e:
            logger.warning(f"Could not mirror guild {guild_id}: {e}")

    # ---------- command execution ----------

    async def _run_command(self, command: dict):
        action = command['action']
        handler = getattr(self, f"_do_{action}", None)
        if handler is None:
            self.db.fail_command(command['id'], f"unknown action: {action}")
            return

        guild = self.bot.get_guild(int(command['guild_id'])) if command['guild_id'].isdigit() else None
        if guild is None:
            self.db.fail_command(command['id'], f"bot is not in guild {command['guild_id']}")
            return

        try:
            result = await handler(guild, command['payload'])
            self.db.complete_command(command['id'], result or 'ok')
            logger.info(f"API command '{action}' completed for guild {guild.id}: {result}")
        except Exception as e:
            logger.error(f"API command '{action}' failed for guild {guild.id}: {e}", exc_info=True)
            self.db.fail_command(command['id'], str(e))
        finally:
            self.sync(guild.id)

    async def _ensure_voice(self, guild: discord.Guild, voice_channel_id) -> discord.VoiceClient:
        """Use the existing connection, or join the channel the API named."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        if voice_client and voice_client.is_connected():
            return voice_client

        if not voice_channel_id:
            raise RuntimeError("bot is not in a voice channel; pass voice_channel_id")

        channel = guild.get_channel(int(voice_channel_id))
        # Duck-typed rather than isinstance: any connectable channel will do,
        # and a text channel has no connect().
        if channel is None or not hasattr(channel, 'connect'):
            raise RuntimeError(f"voice channel {voice_channel_id} not found in this guild")

        return await self.cog._connect(guild, channel)

    async def _do_play(self, guild, payload):
        tracks = [Track.from_dict(data) for data in payload.get('tracks', [])]
        if not tracks:
            # No pre-resolved tracks: fall back to resolving the raw query here.
            query = payload.get('query')
            if not query:
                raise RuntimeError("play needs either tracks or a query")
            tracks = await self.cog._resolve_query(query)
        if not tracks:
            raise RuntimeError("could not resolve any track")

        voice_client = await self._ensure_voice(guild, payload.get('voice_channel_id'))
        player = self.cog._get_player(guild.id, voice_client)

        text_channel_id = payload.get('text_channel_id')
        if text_channel_id:
            channel = guild.get_channel(int(text_channel_id))
            if channel:
                player.text_channel = channel

        for track in tracks:
            player.add(track)

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self.cog._advance(guild)

        return f"queued {len(tracks)} track(s)"

    async def _do_skip(self, guild, payload):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        if not voice_client or not (voice_client.is_playing() or voice_client.is_paused()):
            raise RuntimeError("nothing is playing")

        # stop() fires the after-callback, which advances the queue.
        voice_client.stop()
        return "skipped"

    async def _do_pause(self, guild, payload):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        if not voice_client or not voice_client.is_playing():
            raise RuntimeError("nothing is playing")

        voice_client.pause()
        player = self.cog.players.get(guild.id)
        if player:
            player.mark_paused()
        return "paused"

    async def _do_resume(self, guild, payload):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        if not voice_client or not voice_client.is_paused():
            raise RuntimeError("playback is not paused")

        voice_client.resume()
        player = self.cog.players.get(guild.id)
        if player:
            player.mark_resumed()
        return "resumed"

    async def _do_stop(self, guild, payload):
        player = self.cog.players.get(guild.id)
        if player:
            player.queue.clear()
            player.current = None
            player.last_announced_id = None
            player.mark_stopped()

        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        if voice_client:
            await voice_client.disconnect()
        return "stopped"

    async def _do_clear(self, guild, payload):
        player = self.cog._get_player(guild.id)
        cleared = len(player.queue)
        player.queue.clear()
        return f"cleared {cleared} track(s)"

    async def _do_remove(self, guild, payload):
        player = self.cog._get_player(guild.id)
        position = int(payload.get('position', 0))
        if position < 1 or position > len(player.queue):
            raise RuntimeError(f"invalid position {position}; queue has {len(player.queue)} track(s)")

        removed = player.queue.pop(position - 1)
        return f"removed {removed.title}"

    async def _do_shuffle(self, guild, payload):
        player = self.cog._get_player(guild.id)
        if len(player.queue) < 2:
            raise RuntimeError("not enough tracks in queue to shuffle")

        player.shuffle()
        return f"shuffled {len(player.queue)} track(s)"

    async def _do_mix(self, guild, payload):
        import os
        import random

        rows = self.cog.youtube.db.all_downloaded()
        tracks = [Track.from_dict(row) for row in rows if os.path.exists(row['file_path'])]
        if not tracks:
            raise RuntimeError("no cached songs yet")
        random.shuffle(tracks)

        voice_client = await self._ensure_voice(guild, payload.get('voice_channel_id'))
        player = self.cog._get_player(guild.id, voice_client)
        player.queue = tracks
        player.current = None
        player.loop_mode = LoopMode.QUEUE

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self.cog._advance(guild)

        return f"mixing {len(tracks)} cached track(s)"

    async def _do_loop(self, guild, payload):
        mode = payload.get('mode', 'off')
        player = self.cog._get_player(guild.id)
        player.loop_mode = LoopMode(mode)
        return f"loop {mode}"

    async def _do_volume(self, guild, payload):
        percent = int(payload.get('percent', 100))
        percent = max(0, min(percent, 200))

        player = self.cog._get_player(guild.id)
        player.volume = percent / 100
        if player.voice_client and player.voice_client.source:
            player.voice_client.source.volume = player.volume
        return f"volume {percent}%"

    async def _do_autoplay(self, guild, payload):
        player = self.cog._get_player(guild.id)
        if payload.get('toggle'):
            player.autoplay = not player.autoplay
        else:
            player.autoplay = bool(payload.get('enabled'))
        return f"autoplay {'on' if player.autoplay else 'off'}"


def _id_of(channel) -> str:
    channel_id = getattr(channel, 'id', None)
    return str(channel_id) if channel_id is not None else ''


def _track_dict(track):
    if not track:
        return None
    return {
        'id': track.id,
        'title': track.title,
        'duration': track.duration,
        'thumbnail': track.thumbnail,
        'webpage_url': track.webpage_url,
    }
