"""
Error handling cog for the Legion Discord Bot
Handles bot errors and provides user-friendly error messages.
"""

import discord
from discord.ext import commands
import traceback


class ErrorHandler(commands.Cog):
    """Cog for handling bot errors gracefully"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Handle cooldown errors
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
            return
        
        # Handle missing permissions
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have the required permissions to use this command.")
            return
        
        # Handle bot missing permissions
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have the required permissions to execute this command.")
            return
        
        # Handle missing required arguments
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
            return
        
        # Handle bad arguments
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided. Please check your input.")
            return
        
        # Handle user not found
        if isinstance(error, commands.UserNotFound):
            await ctx.send("❌ User not found.")
            return
        
        # Handle generic errors
        self.bot.logger.error(f"Command error in {ctx.command}: {error}")
        self.bot.logger.error(traceback.format_exception(type(error), error, error.__traceback__))
        
        await ctx.send("❌ An unexpected error occurred. Please try again later.")
    
    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """Handle general bot errors"""
        self.bot.logger.error(f"Bot error in event {event}: {args} {kwargs}")


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ErrorHandler(bot))