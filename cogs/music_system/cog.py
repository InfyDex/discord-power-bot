"""Music cog: slash + prefix commands for YouTube playback, queueing, and playback controls."""
import asyncio
import logging
import os
import random

import discord
from discord import app_commands
from discord.ext import commands

from .player import GuildPlayer, LoopMode, Track
from .views import SearchView
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


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.youtube = YTDLPClient()
        self.players: dict[int, GuildPlayer] = {}
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


async def setup(bot):
    await bot.add_cog(Music(bot))
