"""
Utility cog for the Legion Discord Bot
Contains utility commands for bot management and information.
"""

import discord
from discord.ext import commands
import time
import psutil
import os
from datetime import timedelta


class EmbedUtils:
    """Utility class for creating consistent embed messages"""
    
    @staticmethod
    def create_standard_embed(title: str, description: str = None, color: int = 0x00ff00, 
                            author_user=None, footer_text: str = None):
        """
        Create a standard embed with consistent formatting
        
        Args:
            title: The embed title
            description: Optional description
            color: Embed color (default: green)
            author_user: Optional discord.User/Member object for mention in footer
            footer_text: Optional custom footer text
        
        Returns:
            discord.Embed: Formatted embed object
        """
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        if footer_text:
            embed.set_footer(text=footer_text)
        elif author_user:
            embed.set_footer(text=f"Requested by {author_user.mention}")
            
        return embed
    
    @staticmethod
    def create_success_embed(title: str, description: str = None, author_user=None):
        """Create a success embed with green color"""
        return EmbedUtils.create_standard_embed(
            title=title, 
            description=description, 
            color=0x00ff00,  # Green
            author_user=author_user
        )
    
    @staticmethod
    def create_error_embed(title: str, description: str = None, author_user=None):
        """Create an error embed with red color"""
        return EmbedUtils.create_standard_embed(
            title=title, 
            description=description, 
            color=0xff0000,  # Red
            author_user=author_user
        )
    
    @staticmethod
    def create_info_embed(title: str, description: str = None, author_user=None):
        """Create an info embed with blue color"""
        return EmbedUtils.create_standard_embed(
            title=title, 
            description=description, 
            color=0x0099ff,  # Blue
            author_user=author_user
        )


class Utilities(commands.Cog):
    """Cog for utility commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
    
    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! Latency: {latency}ms")
    
    @commands.command(name='uptime')
    async def uptime(self, ctx):
        """Check bot uptime"""
        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))
        await ctx.send(f"⏰ Bot uptime: {uptime_string}")
    
    @commands.command(name='info')
    async def info_command(self, ctx):
        """Display bot information"""
        embed = EmbedUtils.create_info_embed(
            title="Legion Discord Bot",
            description="A multilingual greeting bot with modular architecture",
            author_user=ctx.author
        )
        
        embed.add_field(
            name="Bot Stats",
            value=f"Servers: {len(self.bot.guilds)}\nUsers: {len(self.bot.users)}\nLatency: {round(self.bot.latency * 1000)}ms",
            inline=True
        )
        
        embed.add_field(
            name="System Info",
            value=f"Python: {discord.__version__}\nCPU: {psutil.cpu_percent()}%\nMemory: {psutil.virtual_memory().percent}%",
            inline=True
        )
        
        embed.set_footer(text=f"Bot ID: {self.bot.user.id}")
        await ctx.send(embed=embed)
    
    @commands.command(name='reload')
    @commands.is_owner()
    async def reload_cog(self, ctx, cog_name: str = None):
        """Reload a specific cog (Owner only)"""
        if not cog_name:
            await ctx.send("Please specify a cog to reload.")
            return
        
        try:
            await self.bot.reload_extension(f'cogs.{cog_name}')
            await ctx.send(f"✅ Successfully reloaded `{cog_name}` cog.")
            self.bot.logger.info(f"Reloaded cog: {cog_name}")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload `{cog_name}`: {e}")
            self.bot.logger.error(f"Failed to reload cog {cog_name}: {e}")


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(Utilities(bot))