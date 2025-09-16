"""
Greetings cog for the Legion Discord Bot
Handles all greeting-related commands and functionality.
"""

import discord
from discord.ext import commands
import random
from constants import GREETINGS, HELP_MESSAGES, GREETING_WORDS

class Greetings(commands.Cog):
    """Cog for handling greetings and basic interactions"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle greeting messages"""
        # Don't respond to the bot's own messages
        if message.author == self.bot.user:
            return
        
        # Check if bot is mentioned without any other content
        if self.bot.user.mentioned_in(message):
            clean_content = message.content.strip()
            clean_content = clean_content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()
            
            if len(clean_content) == 0:
                # Bot was mentioned with no other text
                help_msg = random.choice(HELP_MESSAGES)
                await message.channel.send(f"{help_msg} {message.author.mention}!")
                return
        
        # Check if the message content is a greeting (case insensitive)
        if message.content.lower().strip() in GREETING_WORDS:
            # Select a random greeting
            greeting = random.choice(GREETINGS)
            await message.channel.send(f"{greeting} {message.author.mention}!")
    
    @commands.command(name='greet')
    async def greet_command(self, ctx):
        """Command to get a random greeting"""
        greeting = random.choice(GREETINGS)
        await ctx.send(f"{greeting} {ctx.author.mention}")
    
    @commands.command(name='greetings')
    async def list_greetings(self, ctx):
        """Command to see all available greetings"""
        greetings_text = "Here are all the greetings I know:\n" + "\n".join(GREETINGS)
        
        # If the message is too long, split it into multiple messages
        if len(greetings_text) > 2000:
            # Split into chunks
            chunks = []
            current_chunk = "Here are all the greetings I know:\n"
            
            for greeting in GREETINGS:
                if len(current_chunk + greeting + "\n") > 1900:  # Leave some buffer
                    chunks.append(current_chunk)
                    current_chunk = greeting + "\n"
                else:
                    current_chunk += greeting + "\n"
            
            if current_chunk:
                chunks.append(current_chunk)
            
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(greetings_text)

async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(Greetings(bot))