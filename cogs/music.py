import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from typing import Optional
from collections import OrderedDict
import base64
import os
import logging
import tempfile

# Setup logger
logger = logging.getLogger('discord.music')

def _resolve_cookies() -> str | None:
    """Return a path to a usable cookies file, or None.

    Priority:
    1. YOUTUBE_COOKIES_B64 env var  (base64-encoded cookies.txt content)
    2. YOUTUBE_COOKIES_FILE env var (explicit path to cookies.txt)
    3. cookies.txt next to bot root
    """
    # 1. Base64 env var — decode into a temp file each startup
    b64 = os.environ.get('YOUTUBE_COOKIES_B64')
    if b64:
        try:
            data = base64.b64decode(b64)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='wb')
            tmp.write(data)
            tmp.flush()
            tmp.close()
            logger.info(f"YouTube cookies loaded from YOUTUBE_COOKIES_B64 → {tmp.name}")
            return tmp.name
        except Exception as e:
            logger.warning(f"Failed to decode YOUTUBE_COOKIES_B64: {e}")

    # 2. Explicit file path env var
    env_path = os.environ.get('YOUTUBE_COOKIES_FILE')
    if env_path and os.path.exists(env_path):
        logger.info(f"YouTube cookies loaded from YOUTUBE_COOKIES_FILE → {env_path}")
        return env_path

    # 3. Default location
    default = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies.txt')
    if os.path.exists(default):
        logger.info(f"YouTube cookies loaded from {default}")
        return default

    logger.warning(
        "No YouTube cookies found. Downloads may fail with 403 on server IPs. "
        "Set YOUTUBE_COOKIES_B64 in your .env (see README) or place cookies.txt in the bot root."
    )
    return None


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}  # Guild-specific queues
        self.now_playing = {}  # Current song per guild
        logger.info("Music cog initialized")

        self._cookies_file = _resolve_cookies()

        # yt-dlp options for metadata/search only (no download)
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': False,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'logtostderr': False,
            'quiet': False,
            'no_warnings': False,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
            'playlistend': 50,
        }

        self.ffmpeg_options = {
            'options': '-vn'
        }

        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_options)
        # Downloads are handled via yt-dlp CLI subprocess (more reliable on server IPs)

        # LRU audio cache: OrderedDict keyed by video ID → local file path
        # Keeps the last AUDIO_CACHE_LIMIT songs on disk; oldest evicted when full
        self.AUDIO_CACHE_LIMIT = 100
        self.audio_cache: OrderedDict[str, str] = OrderedDict()

        # Create downloads folder
        os.makedirs('downloads', exist_ok=True)
        logger.info("Music cog setup completed - downloads folder ready")

    def get_queue(self, guild_id):
        """Get or create queue for a guild"""
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        return self.queue[guild_id]

    async def search_youtube(self, query: str):
        """Search YouTube and return first result"""
        try:
            logger.info(f"Searching YouTube for: {query}")
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, 
                lambda: self.ytdl.extract_info(f"ytsearch5:{query}", download=False)
            )

            if not data:
                logger.error("yt-dlp returned no data")
                return None

            if 'entries' in data:
                # Find first non-None entry (some entries are None for unavailable videos)
                entry = next((e for e in data['entries'] if e), None)
                if not entry:
                    logger.error(f"No valid entries found for query: {query}")
                    return None
                data = entry

            result = {
                'id': data['id'],
                'title': data['title'],
                'url': data['url'],
                'duration': data['duration'],
                'thumbnail': data['thumbnail'],
                'webpage_url': data['webpage_url']
            }
            logger.info(f"Found: {result['title']}")
            return result
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}", exc_info=True)
            return None

    async def get_playlist_info(self, url: str):
        """Extract playlist information from URL"""
        try:
            logger.info(f"Extracting playlist info from: {url}")
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self.ytdl.extract_info(url, download=False)
            )

            if not data:
                logger.error("yt-dlp returned no data for URL")
                return None

            if 'entries' not in data:
                # Not a playlist, return single video
                return [{
                    'id': data['id'],
                    'title': data['title'],
                    'url': data['url'],
                    'duration': data['duration'],
                    'thumbnail': data['thumbnail'],
                    'webpage_url': data['webpage_url']
                }]
            
            # Extract all videos from playlist
            songs = []
            for entry in data['entries']:
                if entry:  # Skip None entries (unavailable videos)
                    songs.append({
                        'id': entry['id'],
                        'title': entry['title'],
                        'url': entry['url'],
                        'duration': entry['duration'],
                        'thumbnail': entry.get('thumbnail', data.get('thumbnail')),
                        'webpage_url': entry['webpage_url']
                    })
            
            logger.info(f"Extracted {len(songs)} songs from playlist: {data.get('title', 'Unknown')}")
            return songs
        except Exception as e:
            logger.error(f"Error extracting playlist: {e}", exc_info=True)
            return None

    async def _download_via_subprocess(self, song: dict) -> str | None:
        """Download audio using yt-dlp CLI subprocess.

        The CLI is more reliable than the Python API on server IPs:
        it handles PO tokens, retries, and format negotiation better.
        Cookies are passed directly if available.
        """
        video_id = song.get('id') or song['webpage_url'].split('v=')[-1].split('&')[0]
        mp3_path = os.path.join('downloads', f"{video_id}.mp3")

        cmd = [
            'yt-dlp',
            '--no-playlist',
            '-f', 'bestaudio/best',
            '-x', '--audio-format', 'mp3', '--audio-quality', '192K',
            '--no-check-certificates',
            '-o', os.path.join('downloads', '%(id)s.%(ext)s'),
            '--quiet', '--no-warnings',
        ]
        if self._cookies_file and os.path.exists(self._cookies_file):
            cmd += ['--cookies', self._cookies_file]
        cmd.append(song['webpage_url'])

        logger.info(f"Running yt-dlp CLI: {' '.join(cmd[-3:])}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"yt-dlp exited {proc.returncode}: {stderr.decode(errors='replace').strip()}")
                return None
        except Exception as e:
            logger.error(f"yt-dlp subprocess error: {e}", exc_info=True)
            return None

        if not os.path.exists(mp3_path):
            logger.error(f"Expected output not found: {mp3_path}")
            return None

        return mp3_path

    async def get_audio_file(self, song: dict) -> str | None:
        """Return a local audio file path for the song, using cache when available.

        Cache behaviour:
        - Hit  → move to end (most recently used), return immediately, no download
        - Miss → download via yt-dlp CLI, add to cache
        - Evict → oldest file deleted from disk when cache exceeds AUDIO_CACHE_LIMIT
        """
        video_id = song.get('id')
        if not video_id:
            video_id = song['webpage_url'].split('v=')[-1].split('&')[0]

        # Cache hit
        if video_id in self.audio_cache:
            file_path = self.audio_cache[video_id]
            if os.path.exists(file_path):
                self.audio_cache.move_to_end(video_id)
                logger.info(f"Cache hit for '{song['title']}' — {file_path}")
                return file_path
            del self.audio_cache[video_id]

        # Cache miss — download via CLI
        logger.info(f"Cache miss for '{song['title']}' — downloading...")
        file_path = await self._download_via_subprocess(song)
        if not file_path:
            return None

        # Add to cache, evict oldest if over limit
        self.audio_cache[video_id] = file_path
        if len(self.audio_cache) > self.AUDIO_CACHE_LIMIT:
            oldest_id, oldest_path = self.audio_cache.popitem(last=False)
            try:
                if os.path.exists(oldest_path):
                    os.remove(oldest_path)
                    logger.info(f"Cache evicted (limit {self.AUDIO_CACHE_LIMIT}): {oldest_path}")
            except Exception as e:
                logger.warning(f"Could not delete evicted file {oldest_path}: {e}")

        logger.info(f"Downloaded and cached: {file_path} (cache size: {len(self.audio_cache)})")
        return file_path

    async def play_next(self, guild):
        """Play next song in queue, using the audio cache"""
        guild_id = guild.id
        queue = self.get_queue(guild_id)
        
        logger.info(f"play_next called for guild {guild_id}, queue length: {len(queue)}")
        
        if len(queue) > 0:
            song = queue.pop(0)
            self.now_playing[guild_id] = song
            
            voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
            if voice_client and voice_client.is_connected():
                try:
                    file_path = await self.get_audio_file(song)
                    if not file_path:
                        logger.error(f"Could not get audio for '{song['title']}', skipping")
                        await self.play_next(guild)
                        return

                    def after_playback(error):
                        if error:
                            logger.error(f"Playback error: {error}")
                        asyncio.run_coroutine_threadsafe(
                            self.play_next(guild), self.bot.loop
                        )

                    voice_client.play(
                        discord.FFmpegPCMAudio(file_path, **self.ffmpeg_options),
                        after=after_playback
                    )
                    logger.info(f"Playing: '{song['title']}' from {file_path}")
                except Exception as e:
                    logger.error(f"Error during playback: {e}", exc_info=True)
            else:
                logger.error("Voice client not connected!")
        else:
            self.now_playing.pop(guild_id, None)
            logger.info(f"Queue empty for guild {guild_id}")

    @app_commands.command(name="play", description="Play a song from YouTube")
    @app_commands.describe(query="Song name or YouTube URL (supports playlists)")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play a song"""
        logger.info(f"Play command received from {interaction.user} with query: {query}")
        await interaction.response.defer()
        
        # Check if user is in voice channel
        if not interaction.user.voice:
            logger.warning(f"User {interaction.user} not in voice channel")
            await interaction.followup.send("❌ You need to be in a voice channel!")
            return
        
        voice_channel = interaction.user.voice.channel
        logger.info(f"User is in voice channel: {voice_channel.name}")
        
        # Connect to voice channel if not connected
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if not voice_client:
            logger.info(f"Connecting to voice channel: {voice_channel.name}")
            try:
                voice_client = await voice_channel.connect()
                logger.info("Successfully connected to voice channel")
            except Exception as e:
                logger.error(f"Failed to connect to voice: {e}", exc_info=True)
                await interaction.followup.send(f"❌ Failed to connect to voice channel: {e}")
                return
        elif voice_client.channel != voice_channel:
            logger.info(f"Moving to voice channel: {voice_channel.name}")
            await voice_client.move_to(voice_channel)
        
        # Check if it's a playlist or single video
        is_url = query.startswith('http://') or query.startswith('https://')
        is_playlist = 'playlist' in query or 'list=' in query
        
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        
        if is_url and is_playlist:
            # Handle playlist
            await interaction.followup.send(f"🔍 Loading playlist from URL...")
            songs = await self.get_playlist_info(query)
            
            if not songs:
                await interaction.edit_original_response(content="❌ Could not load playlist!")
                return
            
            # Add all songs to queue
            for song in songs:
                queue.append(song)
            
            logger.info(f"Added {len(songs)} songs from playlist to queue")
            
            # Create embed
            embed = discord.Embed(
                title="📃 Playlist Added to Queue",
                description=f"Added **{len(songs)}** songs to the queue!",
                color=discord.Color.green()
            )
            
            # Show first 5 songs
            if len(songs) > 0:
                song_list = "\n".join([
                    f"{i+1}. {song['title'][:50]}{'...' if len(song['title']) > 50 else ''}"
                    for i, song in enumerate(songs[:5])
                ])
                embed.add_field(name="First Songs", value=song_list, inline=False)
                
                if len(songs) > 5:
                    embed.set_footer(text=f"... and {len(songs) - 5} more songs")
            
            await interaction.edit_original_response(content=None, embed=embed)
            
        else:
            # Handle single song (URL or search)
            await interaction.followup.send(f"🔍 Searching for: **{query}**...")
            
            if is_url:
                # Direct URL
                songs = await self.get_playlist_info(query)
                if not songs or len(songs) == 0:
                    await interaction.edit_original_response(content="❌ Could not find the song!")
                    return
                song = songs[0]
            else:
                # Search query
                song = await self.search_youtube(query)
            
            if not song:
                logger.error(f"Could not find song for query: {query}")
                await interaction.edit_original_response(content="❌ Could not find the song!")
                return
            
            # Add to queue
            queue.append(song)
            logger.info(f"Added to queue: {song['title']}, queue length: {len(queue)}")
            
            # Create embed
            embed = discord.Embed(
                title="🎵 Added to Queue",
                description=f"[{song['title']}]({song['webpage_url']})",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=song['thumbnail'])
            embed.add_field(
                name="Duration", 
                value=f"{song['duration'] // 60}:{song['duration'] % 60:02d}"
            )
            embed.add_field(name="Position in Queue", value=len(queue))
            
            await interaction.edit_original_response(content=None, embed=embed)
        
        # If nothing is playing, start playing
        is_playing = voice_client.is_playing()
        logger.info(f"Voice client is_playing: {is_playing}")
        if not is_playing:
            logger.info("Starting playback...")
            await self.play_next(interaction.guild)
        else:
            logger.info("Already playing, song(s) added to queue")

    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx, *, query: str):
        """Play a song (prefix command version)"""
        logger.info(f"Prefix play command received from {ctx.author} with query: {query}")
        
        # Check if user is in voice channel
        if not ctx.author.voice:
            logger.warning(f"User {ctx.author} not in voice channel")
            await ctx.send("❌ You need to be in a voice channel!")
            return
        
        voice_channel = ctx.author.voice.channel
        logger.info(f"User is in voice channel: {voice_channel.name}")
        
        # Connect to voice channel if not connected
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if not voice_client:
            logger.info(f"Connecting to voice channel: {voice_channel.name}")
            try:
                voice_client = await voice_channel.connect()
                logger.info("Successfully connected to voice channel")
            except Exception as e:
                logger.error(f"Failed to connect to voice: {e}", exc_info=True)
                await ctx.send(f"❌ Failed to connect to voice channel: {e}")
                return
        elif voice_client.channel != voice_channel:
            logger.info(f"Moving to voice channel: {voice_channel.name}")
            await voice_client.move_to(voice_channel)
        
        # Check if it's a playlist or single video
        is_url = query.startswith('http://') or query.startswith('https://')
        is_playlist = 'playlist' in query or 'list=' in query
        
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if is_url and is_playlist:
            # Handle playlist
            search_msg = await ctx.send(f"🔍 Loading playlist from URL...")
            songs = await self.get_playlist_info(query)
            
            if not songs:
                await search_msg.edit(content="❌ Could not load playlist!")
                return
            
            # Add all songs to queue
            for song in songs:
                queue.append(song)
            
            logger.info(f"Added {len(songs)} songs from playlist to queue")
            
            # Create embed
            embed = discord.Embed(
                title="📃 Playlist Added to Queue",
                description=f"Added **{len(songs)}** songs to the queue!",
                color=discord.Color.green()
            )
            
            # Show first 5 songs
            if len(songs) > 0:
                song_list = "\n".join([
                    f"{i+1}. {song['title'][:50]}{'...' if len(song['title']) > 50 else ''}"
                    for i, song in enumerate(songs[:5])
                ])
                embed.add_field(name="First Songs", value=song_list, inline=False)
                
                if len(songs) > 5:
                    embed.set_footer(text=f"... and {len(songs) - 5} more songs")
            
            await search_msg.edit(content=None, embed=embed)
            
        else:
            # Handle single song (URL or search)
            search_msg = await ctx.send(f"🔍 Searching for: **{query}**...")
            
            if is_url:
                # Direct URL
                songs = await self.get_playlist_info(query)
                if not songs or len(songs) == 0:
                    await search_msg.edit(content="❌ Could not find the song!")
                    return
                song = songs[0]
            else:
                # Search query
                song = await self.search_youtube(query)
            
            if not song:
                logger.error(f"Could not find song for query: {query}")
                await search_msg.edit(content="❌ Could not find the song!")
                return
            
            # Add to queue
            queue.append(song)
            logger.info(f"Added to queue: {song['title']}, queue length: {len(queue)}")
            
            # Create embed
            embed = discord.Embed(
                title="🎵 Added to Queue",
                description=f"[{song['title']}]({song['webpage_url']})",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=song['thumbnail'])
            embed.add_field(
                name="Duration", 
                value=f"{song['duration'] // 60}:{song['duration'] % 60:02d}"
            )
            embed.add_field(name="Position in Queue", value=len(queue))
            
            await search_msg.edit(content=None, embed=embed)
        
        # If nothing is playing, start playing
        is_playing = voice_client.is_playing()
        logger.info(f"Voice client is_playing: {is_playing}")
        if not is_playing:
            logger.info("Starting playback...")
            await self.play_next(ctx.guild)
        else:
            logger.info("Already playing, song(s) added to queue")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip current song"""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            logger.info(f"Skipped song in guild {interaction.guild.id}")
            await interaction.response.send_message("⏭️ Skipped!")
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

    @commands.command(name="skip", aliases=["s"])
    async def skip_prefix(self, ctx):
        """Skip current song (prefix command)"""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            logger.info(f"Skipped song in guild {ctx.guild.id}")
            await ctx.send("⏭️ Skipped!")
        else:
            await ctx.send("❌ Nothing is playing!")

    @commands.command(name="clear", aliases=["c"])
    async def clear_queue(self, ctx):
        """Clear the entire queue"""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if len(queue) == 0:
            await ctx.send("❌ Queue is already empty!")
            return
        
        cleared_count = len(queue)
        queue.clear()
        logger.info(f"Cleared {cleared_count} songs from queue in guild {guild_id}")
        await ctx.send(f"🗑️ Cleared **{cleared_count}** song(s) from the queue!")

    @commands.command(name="remove", aliases=["rm"])
    async def remove_from_queue(self, ctx, position: int):
        """Remove a specific song from queue by position"""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if position < 1 or position > len(queue):
            await ctx.send(f"❌ Invalid position! Queue has {len(queue)} song(s).")
            return
        
        removed_song = queue.pop(position - 1)
        logger.info(f"Removed song from position {position}: {removed_song['title']}")
        await ctx.send(f"🗑️ Removed: **{removed_song['title']}**")

    @commands.command(name="testmusic")
    async def test_music(self, ctx):
        """Test if music dependencies are working"""
        logger.info("Running music system test...")
        
        # Test 1: Check voice connection capability
        test_results = []
        
        # Test PyNaCl
        try:
            import nacl
            test_results.append("✅ PyNaCl installed")
        except ImportError:
            test_results.append("❌ PyNaCl not installed")
        
        # Test yt-dlp
        try:
            import yt_dlp
            test_results.append("✅ yt-dlp installed")
        except ImportError:
            test_results.append("❌ yt-dlp not installed")
        
        # Test FFmpeg
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                test_results.append("✅ FFmpeg installed and accessible")
            else:
                test_results.append("❌ FFmpeg found but not working")
        except FileNotFoundError:
            test_results.append("❌ FFmpeg NOT installed or not in PATH")
        except Exception as e:
            test_results.append(f"❌ FFmpeg error: {e}")
        
        # Test voice connection
        if ctx.author.voice:
            test_results.append(f"✅ You are in voice channel: {ctx.author.voice.channel.name}")
        else:
            test_results.append("⚠️ You are not in a voice channel")
        
        embed = discord.Embed(
            title="🎵 Music System Test",
            description="\n".join(test_results),
            color=discord.Color.blue()
        )
        
        await ctx.send(embed=embed)
        logger.info(f"Test results: {test_results}")

    @app_commands.command(name="clear", description="Clear the entire queue")
    async def clear(self, interaction: discord.Interaction):
        """Clear the entire queue"""
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        
        if len(queue) == 0:
            await interaction.response.send_message("❌ Queue is already empty!")
            return
        
        cleared_count = len(queue)
        queue.clear()
        logger.info(f"Cleared {cleared_count} songs from queue in guild {guild_id}")
        await interaction.response.send_message(f"🗑️ Cleared **{cleared_count}** song(s) from the queue!")

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        """Stop music and disconnect"""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        
        if voice_client:
            guild_id = interaction.guild.id
            self.queue[guild_id] = []
            self.now_playing.pop(guild_id, None)
            
            await voice_client.disconnect()
            await interaction.response.send_message("⏹️ Stopped and disconnected!")
        else:
            await interaction.response.send_message("❌ Not connected to voice!")

    @app_commands.command(name="queue", description="Show current queue")
    async def show_queue(self, interaction: discord.Interaction):
        """Display queue"""
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        
        embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.blue())
        
        # Now playing
        if guild_id in self.now_playing:
            np = self.now_playing[guild_id]
            embed.add_field(
                name="🎶 Now Playing",
                value=f"[{np['title']}]({np['webpage_url']})",
                inline=False
            )
        
        # Queue
        if len(queue) > 0:
            queue_text = "\n".join([
                f"{i+1}. [{song['title']}]({song['webpage_url']})"
                for i, song in enumerate(queue[:10])
            ])
            embed.add_field(name="📃 Up Next", value=queue_text, inline=False)
            
            if len(queue) > 10:
                embed.set_footer(text=f"... and {len(queue) - 10} more songs")
        else:
            embed.add_field(name="📃 Up Next", value="Queue is empty", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show current song")
    async def now_playing_cmd(self, interaction: discord.Interaction):
        """Show currently playing song"""
        guild_id = interaction.guild.id
        
        if guild_id in self.now_playing:
            song = self.now_playing[guild_id]
            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"[{song['title']}]({song['webpage_url']})",
                color=discord.Color.purple()
            )
            embed.set_thumbnail(url=song['thumbnail'])
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

    @app_commands.command(name="pause", description="Pause the music")
    async def pause(self, interaction: discord.Interaction):
        """Pause playback"""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused!")
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

    @app_commands.command(name="resume", description="Resume the music")
    async def resume(self, interaction: discord.Interaction):
        """Resume playback"""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Resumed!")
        else:
            await interaction.response.send_message("❌ Music is not paused!")

async def setup(bot):
    await bot.add_cog(Music(bot))
