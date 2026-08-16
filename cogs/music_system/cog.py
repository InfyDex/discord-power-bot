"""Music cog: slash + prefix commands for YouTube playback, queueing, and playback controls."""
import asyncio
import logging
import os
import random
import re

import discord
from discord import app_commands
from discord.ext import commands

from .nlp import has_wake_word, parse_command
from .player import GuildPlayer, LoopMode, Track
from .stt import STTBackend, create_stt_backend
from .views import SearchView
from .voice_listener import MusicCommandSink
from .youtube import YTDLPClient

logger = logging.getLogger('discord.music')

FFMPEG_OPTIONS = {'options': '-vn'}


class _Responder:
    """Unifies slash Interactions and prefix ctx so command bodies aren't duplicated per command style."""

    def __init__(self, obj):
        self._obj = obj
        self._message = None

    async def send(self, content=None, embed=None):
        if isinstance(self._obj, discord.Interaction):
            self._message = await self._obj.followup.send(content=content, embed=embed)
        else:
            self._message = await self._obj.send(content=content, embed=embed)

    async def edit(self, content=None, embed=None):
        if isinstance(self._obj, discord.Interaction):
            await self._obj.edit_original_response(content=content, embed=embed)
        elif self._message:
            await self._message.edit(content=content, embed=embed)
        else:
            await self.send(content=content, embed=embed)

    @property
    def author(self):
        return self._obj.user if isinstance(self._obj, discord.Interaction) else self._obj.author

    @property
    def guild(self):
        return self._obj.guild

    @property
    def channel(self):
        return self._obj.channel


class _ChannelResponder:
    """Responder backed by an explicit TextChannel + Member pair.

    Used for NLP (natural-language text) and voice commands where there is no
    real ``commands.Context`` or ``discord.Interaction`` available.
    """

    def __init__(self, channel: discord.TextChannel, member: discord.Member) -> None:
        self._channel = channel
        self._member = member
        self._message = None

    async def send(self, content=None, embed=None):
        self._message = await self._channel.send(content=content, embed=embed)

    async def edit(self, content=None, embed=None):
        if self._message:
            await self._message.edit(content=content, embed=embed)
        else:
            await self.send(content=content, embed=embed)

    @property
    def author(self):
        return self._member

    @property
    def guild(self):
        return self._member.guild

    @property
    def channel(self):
        return self._channel


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.youtube = YTDLPClient()
        self.players: dict[int, GuildPlayer] = {}
        # STT backend — model loads lazily on first voice transcription.
        self.stt: STTBackend = create_stt_backend()
        # Active voice-command sinks, keyed by guild_id.
        self.sinks: dict[int, MusicCommandSink] = {}
        logger.info("Music cog initialized")

    # ---------- shared helpers ----------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Cog-wide gate for slash commands: music needs a guild (voice channels don't exist in DMs)."""
        if interaction.guild is None:
            await interaction.response.send_message("❌ Music commands only work in a server!")
            return False
        return True

    async def cog_check(self, ctx) -> bool:
        """Cog-wide gate for prefix commands: same guild-only rule as interaction_check."""
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    def _get_player(self, guild_id: int, voice_client=None) -> GuildPlayer:
        player = self.players.get(guild_id)
        if not player:
            player = GuildPlayer(guild_id=guild_id)
            self.players[guild_id] = player
        if voice_client:
            player.voice_client = voice_client
        return player

    async def _connect(self, guild: discord.Guild, channel: discord.VoiceChannel) -> discord.VoiceClient:
        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        if not voice_client:
            voice_client = await channel.connect()
            logger.info(f"Connected to voice channel: {channel.name}")
        elif voice_client.channel != channel:
            await voice_client.move_to(channel)
            logger.info(f"Moved to voice channel: {channel.name}")
        return voice_client

    async def _resolve_query(self, query: str) -> list[Track]:
        is_url = query.startswith('http://') or query.startswith('https://')
        if is_url:
            cached = self.youtube.lookup_cached_url(query)
            if cached:
                logger.info(f"URL already downloaded, skipping extraction: {query}")
                return [Track.from_dict(cached)]
            data = await self.youtube.extract(query)
        else:
            data = await self.youtube.search(query, limit=1)
        return [Track.from_dict(d) for d in data]

    @staticmethod
    def _queue_embed(tracks: list[Track]) -> discord.Embed:
        if len(tracks) == 1:
            t = tracks[0]
            embed = discord.Embed(
                title="🎵 Added to Queue",
                description=f"[{t.title}]({t.webpage_url})",
                color=discord.Color.green(),
            )
            embed.set_thumbnail(url=t.thumbnail)
            embed.add_field(name="Duration", value=f"{t.duration // 60}:{t.duration % 60:02d}")
            return embed

        embed = discord.Embed(
            title="📃 Playlist Added to Queue",
            description=f"Added **{len(tracks)}** songs to the queue!",
            color=discord.Color.green(),
        )
        preview = "\n".join(
            f"{i + 1}. {t.title[:50]}{'...' if len(t.title) > 50 else ''}" for i, t in enumerate(tracks[:5])
        )
        embed.add_field(name="First Songs", value=preview, inline=False)
        if len(tracks) > 5:
            embed.set_footer(text=f"... and {len(tracks) - 5} more songs")
        return embed

    @staticmethod
    def _now_playing_embed(track: Track) -> discord.Embed:
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.purple(),
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        if track.duration:
            embed.add_field(name="Duration", value=f"{track.duration // 60}:{track.duration % 60:02d}")
        return embed

    async def _announce_now_playing(self, player: GuildPlayer, track: Track):
        """Post the track that just started. Skipped when the same track repeats (loop track)."""
        if not player.text_channel or player.last_announced_id == track.id:
            return
        player.last_announced_id = track.id
        try:
            await player.text_channel.send(embed=self._now_playing_embed(track))
        except discord.HTTPException as e:
            logger.warning(f"Could not announce now playing in guild {player.guild_id}: {e}")

    async def _advance(self, guild: discord.Guild):
        """Play the next track for a guild. Wired as the `after` callback so playback self-continues."""
        player = self.players.get(guild.id)
        if not player or not player.voice_client or not player.voice_client.is_connected():
            return

        while True:
            track = player.next_track()
            if not track and player.autoplay and player.current:
                data = await self.youtube.related(player.current.id, set(player.history))
                if data:
                    track = Track.from_dict(data)

            if not track:
                player.current = None
                logger.info(f"Queue empty for guild {guild.id}")
                return

            player.record_played(track)
            file_path = await self.youtube.get_audio_file({
                'id': track.id, 'title': track.title, 'webpage_url': track.webpage_url,
                'duration': track.duration, 'thumbnail': track.thumbnail,
            })
            if file_path:
                break
            logger.error(f"Could not get audio for '{track.title}', skipping")
            # Drop the broken track so track/queue loop modes don't retry it forever.
            player.current = None

        def after_playback(error):
            if error:
                logger.error(f"Playback error: {error}")
            asyncio.run_coroutine_threadsafe(self._advance(guild), self.bot.loop)

        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(file_path, **FFMPEG_OPTIONS), volume=player.volume)
        player.voice_client.play(source, after=after_playback)
        logger.info(f"Playing: '{track.title}' from {file_path}")
        await self._announce_now_playing(player, track)

    async def _ensure_listening(self, voice_client: discord.VoiceClient, guild_id: int) -> None:
        """Auto-start voice-command recording whenever the bot joins a voice channel.

        Called every time the bot connects or plays something — is a no-op if
        recording is already active for this guild.
        """
        if guild_id in self.sinks:
            return  # already recording

        sink = MusicCommandSink(
            stt=self.stt,
            on_command=lambda uid, cmd: self._voice_command_handler(guild_id, uid, cmd),
            loop=self.bot.loop,
        )
        self.sinks[guild_id] = sink

        async def _done(snk, *_args):
            self.sinks.pop(guild_id, None)
            logger.info('Auto-recording finished for guild %d.', guild_id)

        voice_client.start_recording(sink, _done)
        sink.start()
        logger.info('Auto-started voice listening in guild %d.', guild_id)

    async def _handle_play(self, responder: _Responder, query: str):
        if not responder.author.voice:
            await responder.send("❌ You need to be in a voice channel!")
            return

        voice_channel = responder.author.voice.channel
        try:
            voice_client = await self._connect(responder.guild, voice_channel)
        except Exception as e:
            logger.error(f"Failed to connect to voice: {e}", exc_info=True)
            await responder.send(f"❌ Failed to connect to voice channel: {e}")
            return

        player = self._get_player(responder.guild.id, voice_client)
        player.text_channel = responder.channel

        # Auto-start voice listening whenever bot joins voice.
        await self._ensure_listening(voice_client, responder.guild.id)

        await responder.send(f"🔍 Searching for: **{query}**...")
        tracks = await self._resolve_query(query)
        if not tracks:
            await responder.edit(content="❌ Could not find the song!")
            return

        for t in tracks:
            player.add(t)
        logger.info(f"Added {len(tracks)} track(s) to queue for guild {responder.guild.id}")

        await responder.edit(content=None, embed=self._queue_embed(tracks))

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self._advance(responder.guild)

    # ---------- play ----------

    @app_commands.command(name="play", description="Play a song or playlist from YouTube")
    @app_commands.describe(query="Song name or YouTube URL (supports playlists)")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await self._handle_play(_Responder(interaction), query)

    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx, *, query: str):
        await self._handle_play(_Responder(ctx), query)

    # ---------- search ----------

    @app_commands.command(name="search", description="Search YouTube and pick a track to queue")
    @app_commands.describe(query="Search terms")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        if not interaction.user.voice:
            await interaction.followup.send("❌ You need to be in a voice channel!")
            return

        results = await self.youtube.search(query, limit=5)
        if not results:
            await interaction.followup.send("❌ No results found!")
            return

        async def on_choose(select_interaction: discord.Interaction, data: dict):
            await select_interaction.response.defer()
            if not select_interaction.user.voice:
                await select_interaction.followup.send("❌ You need to be in a voice channel!")
                return
            voice_channel = select_interaction.user.voice.channel
            voice_client = await self._connect(select_interaction.guild, voice_channel)
            player = self._get_player(select_interaction.guild.id, voice_client)
            player.text_channel = select_interaction.channel

            # Auto-start voice listening.
            await self._ensure_listening(voice_client, select_interaction.guild.id)

            track = Track.from_dict(data)
            player.add(track)
            await select_interaction.followup.send(embed=self._queue_embed([track]))

            if not voice_client.is_playing() and not voice_client.is_paused():
                await self._advance(select_interaction.guild)

        embed = discord.Embed(
            title="🔎 Search Results",
            description="\n".join(
                f"{i + 1}. {t['title'][:60]} — {t['duration'] // 60}:{t['duration'] % 60:02d}"
                for i, t in enumerate(results)
            ),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed, view=SearchView(results, on_choose))

    # ---------- playback controls ----------

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            logger.info(f"Skipped song in guild {interaction.guild.id}")
            await interaction.response.send_message("⏭️ Skipped!")
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

    @commands.command(name="skip", aliases=["s"])
    async def skip_prefix(self, ctx):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            logger.info(f"Skipped song in guild {ctx.guild.id}")
            await ctx.send("⏭️ Skipped!")
        else:
            await ctx.send("❌ Nothing is playing!")

    @app_commands.command(name="pause", description="Pause the music")
    async def pause(self, interaction: discord.Interaction):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused!")
        elif voice_client and voice_client.is_paused():
            await interaction.response.send_message("⏸️ Already paused!")
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

    @app_commands.command(name="resume", description="Resume the music")
    async def resume(self, interaction: discord.Interaction):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Resumed!")
        else:
            await interaction.response.send_message("❌ Music is not paused!")

    @app_commands.command(name="stop", description="Stop music, clear queue, and disconnect")
    async def stop(self, interaction: discord.Interaction):
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice_client:
            player = self.players.get(interaction.guild.id)
            if player:
                player.queue.clear()
                player.current = None
                player.last_announced_id = None
            await voice_client.disconnect()
            await interaction.response.send_message("⏹️ Stopped and disconnected!")
        else:
            await interaction.response.send_message("❌ Not connected to voice!")

    # ---------- queue management ----------

    @app_commands.command(name="queue", description="Show current queue")
    async def show_queue(self, interaction: discord.Interaction):
        player = self._get_player(interaction.guild.id)
        embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.blue())

        if player.current:
            embed.add_field(
                name="🎶 Now Playing",
                value=f"[{player.current.title}]({player.current.webpage_url})",
                inline=False,
            )

        if player.queue:
            queue_text = "\n".join(
                f"{i + 1}. [{t.title}]({t.webpage_url})" for i, t in enumerate(player.queue[:10])
            )
            embed.add_field(name="📃 Up Next", value=queue_text, inline=False)
            if len(player.queue) > 10:
                embed.set_footer(text=f"... and {len(player.queue) - 10} more songs")
        else:
            embed.add_field(name="📃 Up Next", value="Queue is empty", inline=False)

        embed.add_field(name="Loop", value=player.loop_mode.value, inline=True)
        embed.add_field(name="Autoplay", value="on" if player.autoplay else "off", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show current song")
    async def now_playing_cmd(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id)
        if player and player.current:
            await interaction.response.send_message(embed=self._now_playing_embed(player.current))
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

    @app_commands.command(name="clear", description="Clear the entire queue")
    async def clear(self, interaction: discord.Interaction):
        player = self._get_player(interaction.guild.id)
        if not player.queue:
            await interaction.response.send_message("❌ Queue is already empty!")
            return
        cleared_count = len(player.queue)
        player.queue.clear()
        logger.info(f"Cleared {cleared_count} songs from queue in guild {interaction.guild.id}")
        await interaction.response.send_message(f"🗑️ Cleared **{cleared_count}** song(s) from the queue!")

    @commands.command(name="clear", aliases=["c"])
    async def clear_prefix(self, ctx):
        player = self._get_player(ctx.guild.id)
        if not player.queue:
            await ctx.send("❌ Queue is already empty!")
            return
        cleared_count = len(player.queue)
        player.queue.clear()
        logger.info(f"Cleared {cleared_count} songs from queue in guild {ctx.guild.id}")
        await ctx.send(f"🗑️ Cleared **{cleared_count}** song(s) from the queue!")

    @commands.command(name="remove", aliases=["rm"])
    async def remove_from_queue(self, ctx, position: int):
        player = self._get_player(ctx.guild.id)
        if position < 1 or position > len(player.queue):
            await ctx.send(f"❌ Invalid position! Queue has {len(player.queue)} song(s).")
            return
        removed = player.queue.pop(position - 1)
        logger.info(f"Removed song from position {position}: {removed.title}")
        await ctx.send(f"🗑️ Removed: **{removed.title}**")

    @commands.command(name="mix")
    async def mix(self, ctx):
        """Shuffle every cached (already-downloaded) song and loop through them, each once per lap."""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return

        rows = self.youtube.db.all_downloaded()
        tracks = [Track.from_dict(r) for r in rows if os.path.exists(r['file_path'])]
        if not tracks:
            await ctx.send("❌ No cached songs yet — play something first!")
            return

        random.shuffle(tracks)

        try:
            voice_client = await self._connect(ctx.guild, ctx.author.voice.channel)
        except Exception as e:
            logger.error(f"Failed to connect to voice: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to connect to voice channel: {e}")
            return

        player = self._get_player(ctx.guild.id, voice_client)
        player.text_channel = ctx.channel
        player.queue = tracks
        player.current = None
        player.loop_mode = LoopMode.QUEUE
        logger.info(f"Mix started for guild {ctx.guild.id}: {len(tracks)} cached song(s)")

        # Auto-start voice listening.
        await self._ensure_listening(voice_client, ctx.guild.id)

        await ctx.send(f"🔀 Mixing **{len(tracks)}** cached song(s) on shuffle-loop!")

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self._advance(ctx.guild)

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        player = self._get_player(interaction.guild.id)
        if len(player.queue) < 2:
            await interaction.response.send_message("❌ Not enough songs in queue to shuffle!")
            return
        player.shuffle()
        await interaction.response.send_message(f"🔀 Shuffled **{len(player.queue)}** songs!")

    # ---------- playback settings ----------

    @app_commands.command(name="loop", description="Set loop mode: off, track, or queue")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Track", value="track"),
        app_commands.Choice(name="Queue", value="queue"),
    ])
    async def loop_cmd(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        player = self._get_player(interaction.guild.id)
        player.loop_mode = LoopMode(mode.value)
        await interaction.response.send_message(f"🔁 Loop mode: **{mode.value}**")

    @app_commands.command(name="autoplay", description="Toggle autoplay of related songs when the queue is empty")
    async def autoplay(self, interaction: discord.Interaction):
        player = self._get_player(interaction.guild.id)
        player.autoplay = not player.autoplay
        await interaction.response.send_message(f"♾️ Autoplay: **{'ON' if player.autoplay else 'OFF'}**")

    @app_commands.command(name="volume", description="Set playback volume (0-200%)")
    @app_commands.describe(percent="Volume percentage, 0-200")
    async def volume(self, interaction: discord.Interaction, percent: app_commands.Range[int, 0, 200]):
        player = self._get_player(interaction.guild.id)
        player.volume = percent / 100
        if player.voice_client and player.voice_client.source:
            player.voice_client.source.volume = player.volume
        await interaction.response.send_message(f"🔊 Volume set to **{percent}%**")

    # ---------- diagnostics ----------

    @commands.command(name="testmusic")
    async def test_music(self, ctx):
        """Test if music dependencies are working"""
        results = []

        try:
            import nacl  # noqa: F401
            results.append("✅ PyNaCl installed")
        except ImportError:
            results.append("❌ PyNaCl not installed")

        try:
            import yt_dlp  # noqa: F401
            results.append("✅ yt-dlp installed")
        except ImportError:
            results.append("❌ yt-dlp not installed")

        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            results.append("✅ FFmpeg installed and accessible" if result.returncode == 0 else "❌ FFmpeg found but not working")
        except FileNotFoundError:
            results.append("❌ FFmpeg NOT installed or not in PATH")
        except Exception as e:
            results.append(f"❌ FFmpeg error: {e}")

        if ctx.author.voice:
            results.append(f"✅ You are in voice channel: {ctx.author.voice.channel.name}")
        else:
            results.append("⚠️ You are not in a voice channel")

        cookie_status = "✅ Configured" if self.youtube.cookiefile or self.youtube.cookies_from_browser else "⚠️ Not configured"
        results.append(f"🍪 YouTube cookies: {cookie_status}")

        embed = discord.Embed(title="🎵 Music System Test", description="\n".join(results), color=discord.Color.blue())
        await ctx.send(embed=embed)
        logger.info(f"Test results: {results}")


    async def cog_unload(self) -> None:
        """Stop all active voice sinks when the cog is unloaded."""
        for guild_id, sink in list(self.sinks.items()):
            guild = self.bot.get_guild(guild_id)
            if guild:
                vc = discord.utils.get(self.bot.voice_clients, guild=guild)
                if vc and hasattr(vc, 'stop_recording'):
                    try:
                        vc.stop_recording()
                    except Exception:
                        pass
            sink.cleanup()
        self.sinks.clear()
        logger.info("Music cog unloaded — all voice sinks stopped.")

    # ---------- NLP / voice command dispatcher ----------

    async def _dispatch_nlp_command(
        self,
        guild: discord.Guild,
        member: discord.Member,
        text_channel,
        cmd,
        source: str = 'text',
    ) -> None:
        """Execute a parsed NLP command on behalf of *member* in *guild*."""
        tag = '🎙️ *(voice)*' if source == 'voice' else '💬 *(chat)*'
        player = self.players.get(guild.id)
        vc = discord.utils.get(self.bot.voice_clients, guild=guild)

        async def say(content=None, embed=None):
            try:
                await text_channel.send(content=content, embed=embed)
            except discord.HTTPException as exc:
                logger.warning('Could not send NLP response: %s', exc)

        if cmd.name == 'skip':
            if vc and (vc.is_playing() or vc.is_paused()):
                vc.stop()
                logger.info('NLP skip in guild %d (%s)', guild.id, source)
                await say(f'⏭️ Skipped! {tag}')
            else:
                await say(f'❌ Nothing is playing! {tag}')

        elif cmd.name == 'pause':
            if vc and vc.is_playing():
                vc.pause()
                await say(f'⏸️ Paused! {tag}')
            elif vc and vc.is_paused():
                await say(f'⏸️ Already paused! {tag}')
            else:
                await say(f'❌ Nothing is playing! {tag}')

        elif cmd.name == 'resume':
            if vc and vc.is_paused():
                vc.resume()
                await say(f'▶️ Resumed! {tag}')
            else:
                await say(f'❌ Music is not paused! {tag}')

        elif cmd.name == 'stop':
            if vc:
                if player:
                    player.queue.clear()
                    player.current = None
                    player.last_announced_id = None
                if guild.id in self.sinks:
                    try:
                        vc.stop_recording()
                    except Exception:
                        pass
                    self.sinks.pop(guild.id, None)
                await vc.disconnect()
                await say(f'⏹️ Stopped and disconnected! {tag}')
            else:
                await say(f'❌ Not connected to voice! {tag}')

        elif cmd.name == 'nowplaying':
            if player and player.current:
                await say(embed=self._now_playing_embed(player.current))
            else:
                await say(f'❌ Nothing is playing right now! {tag}')

        elif cmd.name == 'volume':
            try:
                pct = max(0, min(200, int(cmd.args)))
                if player:
                    player.volume = pct / 100
                    if vc and vc.source:
                        vc.source.volume = player.volume
                await say(f'🔊 Volume set to **{pct}%** {tag}')
            except (ValueError, AttributeError):
                wake = os.getenv('VOICE_WAKE_WORD', 'friday')
                await say(f'❌ Say something like **{wake} volume 80** for 80%. {tag}')

        elif cmd.name == 'shuffle':
            if player and len(player.queue) >= 2:
                player.shuffle()
                await say(f'🔀 Shuffled **{len(player.queue)}** songs! {tag}')
            else:
                await say(f'❌ Not enough songs in queue to shuffle! {tag}')

        elif cmd.name == 'loop':
            if player:
                modes = [LoopMode.OFF, LoopMode.TRACK, LoopMode.QUEUE]
                idx = (modes.index(player.loop_mode) + 1) % len(modes)
                player.loop_mode = modes[idx]
                await say(f'🔁 Loop mode: **{player.loop_mode.value}** {tag}')
            else:
                await say(f'❌ No active player! {tag}')

        elif cmd.name == 'play':
            wake = os.getenv('VOICE_WAKE_WORD', 'friday')
            if not cmd.args:
                await say(f'❌ What should I play? Try: **{wake} play lofi music** {tag}')
                return
            if not member.voice:
                await say(f'❌ You need to be in a voice channel to play music! {tag}')
                return
            responder = _ChannelResponder(text_channel, member)
            await self._handle_play(responder, cmd.args)

    async def _voice_command_handler(
        self,
        guild_id: int,
        user_id: int,
        cmd,
    ) -> None:
        """Callback wired into MusicCommandSink — resolves objects and dispatches."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        member = guild.get_member(user_id)
        if not member:
            return
        player = self.players.get(guild_id)
        text_channel = player.text_channel if player else None
        if not text_channel:
            logger.warning(
                'No text channel set for guild %d — cannot respond to voice command.',
                guild_id,
            )
            return
        await self._dispatch_nlp_command(guild, member, text_channel, cmd, source='voice')

    # ---------- listen / stoplisten / vcmds ----------

    @commands.command(name='listen', aliases=['startlisten'])
    async def listen_cmd(self, ctx):
        """Show voice command help. Listening starts automatically when the bot joins voice."""
        wake = os.getenv('VOICE_WAKE_WORD', 'friday')
        listening = ctx.guild.id in self.sinks
        status_line = (
            '🟢 **Active** — I\'m already listening in this server.'
            if listening else
            '🟡 **Not yet active** — queue a song first and I\'ll start listening automatically.'
        )
        embed = discord.Embed(
            title='🎙️ Voice Commands',
            description=(
                f'{status_line}\n\n'
                f'Voice listening starts **automatically** the moment I join a voice channel.\n'
                f'No command needed — just say the wake word **"{wake}"** and a command!\n\n'
                f'**Examples:**\n'
                f'• `{wake} skip` — skip current song\n'
                f'• `{wake} pause` / `{wake} resume`\n'
                f'• `{wake} play lofi music` — queue a song\n'
                f'• `{wake} stop` — stop & disconnect\n'
                f'• `{wake} volume 80` — set volume to 80%\n'
                f'• `{wake} shuffle` / `{wake} loop`\n'
                f'• `{wake} what\'s playing` — show current song\n\n'
                f'You can also **type** these in chat — no prefix needed!\n'
                f'Run `!stoplisten` to temporarily disable voice commands.'
            ),
            color=discord.Color.green() if listening else discord.Color.orange(),
        )
        await ctx.send(embed=embed)

    @commands.command(name='stoplisten', aliases=['sl'])
    async def stoplisten_cmd(self, ctx):
        """Stop listening for voice commands in this server."""
        if ctx.guild.id not in self.sinks:
            await ctx.send('❌ I\'m not currently listening for voice commands here.')
            return
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client and hasattr(voice_client, 'stop_recording'):
            try:
                voice_client.stop_recording()
            except Exception:
                pass
        self.sinks.pop(ctx.guild.id, None)
        await ctx.send('🔇 Voice commands disabled.')
        logger.info('Voice command listening stopped in guild %d.', ctx.guild.id)

    @commands.command(name='vcmds')
    async def voice_commands_list(self, ctx):
        """Show all available voice and natural-language text commands."""
        wake = os.getenv('VOICE_WAKE_WORD', 'friday')
        listening = ctx.guild.id in self.sinks
        status = '🟢 Active' if listening else '🟡 Starts automatically when bot joins voice'
        embed = discord.Embed(
            title='🎙️ Voice & Natural-Language Commands',
            color=discord.Color.blurple(),
        )
        embed.add_field(name='Status', value=status, inline=False)
        embed.add_field(
            name=f'Say or type (wake word: **"{wake}"**)',
            value=(
                f'`{wake} skip` — skip current song\n'
                f'`{wake} pause` — pause playback\n'
                f'`{wake} resume` — resume playback\n'
                f'`{wake} stop` — stop & disconnect\n'
                f'`{wake} play <song>` — queue a song\n'
                f'`{wake} volume <0-200>` — set volume\n'
                f'`{wake} shuffle` — shuffle the queue\n'
                f'`{wake} loop` — cycle loop mode\n'
                f'`{wake} what\'s playing` — show current song\n'
            ),
            inline=False,
        )
        embed.set_footer(text='Typing commands works even without !listen active.')
        await ctx.send(embed=embed)

    # ---------- Event listeners ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Intercept natural-language music commands typed in chat.

        Triggers when a message starts with the wake word (e.g. "friday skip")
        or when the bot is @mentioned (e.g. "@Bot skip the song").
        Regular prefix commands (!skip, /skip) are unaffected.
        """
        if message.author.bot or message.guild is None:
            return

        content = message.content.strip()
        if not content:
            return

        # Don't intercept messages that already begin with the command prefix.
        prefix = self.bot.command_prefix
        if isinstance(prefix, str) and content.startswith(prefix):
            return

        wake = os.getenv('VOICE_WAKE_WORD', 'friday').lower()
        bot_mentioned = self.bot.user in message.mentions
        starts_with_wake = (
            content.lower().startswith(wake + ' ')
            or content.lower() == wake
        )

        if not (bot_mentioned or starts_with_wake):
            return

        # Strip @mention so the NLP parser sees clean text.
        if bot_mentioned:
            content = re.sub(r'<@!?\d+>', '', content).strip()

        cmd = parse_command(content)
        if not cmd:
            return

        logger.info(
            '[NLP Text] %s: %r → %s(args=%r)',
            message.author, content, cmd.name, cmd.args,
        )
        await self._dispatch_nlp_command(
            guild=message.guild,
            member=message.author,
            text_channel=message.channel,
            cmd=cmd,
            source='text',
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Clean up the voice sink when the bot itself leaves a voice channel."""
        if member.id != self.bot.user.id:
            return
        # Bot moved from a channel to None (fully disconnected).
        if before.channel is not None and after.channel is None:
            guild_id = member.guild.id
            if guild_id in self.sinks:
                self.sinks.pop(guild_id, None)
                logger.info('Bot left voice in guild %d — sink removed.', guild_id)


async def setup(bot):
    await bot.add_cog(Music(bot))
