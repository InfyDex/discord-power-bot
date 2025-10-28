import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from typing import Optional
import os

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}  # Guild-specific queues
        self.now_playing = {}  # Current song per guild
        
        # yt-dlp options
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0'
        }
        
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        
        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_options)
        
        # Create downloads folder
        os.makedirs('downloads', exist_ok=True)

    def get_queue(self, guild_id):
        """Get or create queue for a guild"""
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        return self.queue[guild_id]

    async def search_youtube(self, query: str):
        """Search YouTube and return first result"""
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, 
                lambda: self.ytdl.extract_info(f"ytsearch:{query}", download=False)
            )
            
            if 'entries' in data:
                data = data['entries'][0]
            
            return {
                'title': data['title'],
                'url': data['url'],
                'duration': data['duration'],
                'thumbnail': data['thumbnail'],
                'webpage_url': data['webpage_url']
            }
        except Exception as e:
            print(f"Error searching YouTube: {e}")
            return None

    async def play_next(self, guild):
        """Play next song in queue"""
        guild_id = guild.id
        queue = self.get_queue(guild_id)
        
        if len(queue) > 0:
            song = queue.pop(0)
            self.now_playing[guild_id] = song
            
            voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
            if voice_client and voice_client.is_connected():
                voice_client.play(
                    discord.FFmpegPCMAudio(song['url'], **self.ffmpeg_options),
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self.play_next(guild), self.bot.loop
                    )
                )
        else:
            self.now_playing.pop(guild_id, None)

    @app_commands.command(name="play", description="Play a song from YouTube")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play a song"""
        await interaction.response.defer()
        
        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.followup.send("❌ You need to be in a voice channel!")
            return
        
        voice_channel = interaction.user.voice.channel
        
        # Connect to voice channel if not connected
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
        
        # Search for song
        await interaction.followup.send(f"🔍 Searching for: **{query}**...")
        song = await self.search_youtube(query)
        
        if not song:
            await interaction.edit_original_response(content="❌ Could not find the song!")
            return
        
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        
        # Add to queue
        queue.append(song)
        
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
        if not voice_client.is_playing():
            await self.play_next(interaction.guild)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip current song"""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped!")
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

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
