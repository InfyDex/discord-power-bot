"""
Error handling cog for the Legion Discord Bot
Handles bot errors and provides user-friendly error messages.
"""

import discord
from discord.ext import commands
import traceback
from .utilities import EmbedUtils


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
            embed = EmbedUtils.create_error_embed(
                title="⏰ Command on Cooldown",
                description=f"Please wait {error.retry_after:.2f} seconds before using this command again.",
                author_user=ctx.author
            )
            await ctx.send(embed=embed)
            return
        
        # Handle missing permissions
        if isinstance(error, commands.MissingPermissions):
            embed = EmbedUtils.create_error_embed(
                title="❌ Missing Permissions",
                description="You don't have the required permissions to use this command.",
                author_user=ctx.author
            )
            await ctx.send(embed=embed)
            return
        
        # Handle bot missing permissions
        if isinstance(error, commands.BotMissingPermissions):
            embed = EmbedUtils.create_error_embed(
                title="❌ Bot Missing Permissions",
                description="I don't have the required permissions to execute this command.",
                author_user=ctx.author
            )
            await ctx.send(embed=embed)
            return
        
        # Handle missing required arguments
        if isinstance(error, commands.MissingRequiredArgument):
            embed = EmbedUtils.create_error_embed(
                title="❌ Missing Argument",
                description=f"Missing required argument: `{error.param.name}`",
                author_user=ctx.author
            )
            await ctx.send(embed=embed)
            return
        
        # Handle bad arguments
        if isinstance(error, commands.BadArgument):
            embed = EmbedUtils.create_error_embed(
                title="❌ Invalid Argument",
                description="Invalid argument provided. Please check your input.",
                author_user=ctx.author
            )
            await ctx.send(embed=embed)
            return
        
        # Handle user not found
        if isinstance(error, commands.UserNotFound):
            embed = EmbedUtils.create_error_embed(
                title="❌ User Not Found",
                description="The specified user could not be found.",
                author_user=ctx.author
            )
            await ctx.send(embed=embed)
            return
        
        # Handle generic errors
        self.bot.logger.error(f"Command error in {ctx.command}: {error}")
        self.bot.logger.error(traceback.format_exception(type(error), error, error.__traceback__))
        
        embed = EmbedUtils.create_error_embed(
            title="❌ Unexpected Error",
            description="An unexpected error occurred. Please try again later.",
            author_user=ctx.author
        )
        await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """Handle general bot errors"""
        self.bot.logger.error(f"Bot error in event {event}: {args} {kwargs}")


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ErrorHandler(bot))