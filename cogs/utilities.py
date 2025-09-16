"""
Utility cog for the Legion Discord Bot
Contains utility commands for bot management and information.
"""

import discord
from discord.ext import commands
import time
import psutil
import os


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
        uptime_string = str(discord.utils.time.timedelta(seconds=uptime_seconds))
        await ctx.send(f"⏰ Bot uptime: {uptime_string}")
    
    @commands.command(name='info')
    async def info_command(self, ctx):
        """Display bot information"""
        embed = discord.Embed(
            title="Legion Discord Bot",
            description="A multilingual greeting bot with modular architecture",
            color=discord.Color.blue()
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