"""
Fun Commands cog for the Legion Discord Bot
Contains entertainment commands like coin flip and dice rolling.
"""

import discord
from discord.ext import commands
import random
import re


class FunCommands(commands.Cog):
    """Cog for fun and entertainment commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='flip', aliases=['coin', 'coinflip'])
    async def flip_coin(self, ctx):
        """Flip a coin and get heads or tails"""
        result = random.choice(['heads', 'tails'])
        
        # Create an embed for better presentation
        embed = discord.Embed(
            title=":coin: Coin Flip",
            color=0xFFD700 if result == 'heads' else 0xC0C0C0
        )
        
        if result == 'heads':
            embed.add_field(
                name="Result", 
                value=":coin: **HEADS!**", 
                inline=False
            )
        else:
            embed.add_field(
                name="Result", 
                value=":coin: **TAILS!**", 
                inline=False
            )
        
        embed.set_footer(text=f"Flipped by {ctx.author.mention}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='roll', aliases=['dice', 'r'])
    async def roll_dice(self, ctx, dice_notation: str = "1d6"):
        """
        Roll dice with standard notation (e.g., 1d6, 2d20, 3d8)
        
        Examples:
        !roll        - Roll a single 6-sided die
        !roll 2d20   - Roll two 20-sided dice
        !roll 3d8    - Roll three 8-sided dice
        !roll d100   - Roll a 100-sided die
        """
        
        # Parse dice notation (e.g., "2d6", "d20", "3d8")
        dice_pattern = r'^(\d*)d(\d+)$'
        match = re.match(dice_pattern, dice_notation.lower())
        
        if not match:
            await ctx.send(":x: Invalid dice notation! Use format like `1d6`, `2d20`, or `d100`")
            return
        
        num_dice = int(match.group(1)) if match.group(1) else 1
        dice_sides = int(match.group(2))
        
        # Validate input
        if num_dice < 1 or num_dice > 20:
            await ctx.send(":x: Number of dice must be between 1 and 20!")
            return
        
        if dice_sides < 2 or dice_sides > 1000:
            await ctx.send(":x: Dice sides must be between 2 and 1000!")
            return
        
        # Roll the dice
        rolls = [random.randint(1, dice_sides) for _ in range(num_dice)]
        total = sum(rolls)
        
        # Create embed
        embed = discord.Embed(
            title=":game_die: Dice Roll",
            color=0xFF6B6B
        )
        
        # Add dice emoji based on common dice types
        dice_emoji = {
            4: ":small_red_triangle:", 6: ":game_die:", 8: ":large_orange_diamond:", 10: ":keycap_ten:", 
            12: ":large_blue_diamond:", 20: ":dart:", 100: ":100:"
        }
        
        emoji = dice_emoji.get(dice_sides, ":game_die:")
        
        embed.add_field(
            name=f"{emoji} Rolling {num_dice}d{dice_sides}",
            value=f"**Individual rolls:** {', '.join(map(str, rolls))}\n**Total:** {total}",
            inline=False
        )
        
        # Add some flavor text for special rolls
        if num_dice == 1:
            if rolls[0] == 1:
                embed.add_field(name=":skull: Critical Fail!", value="Ouch, that's a 1!", inline=False)
            elif rolls[0] == dice_sides:
                embed.add_field(name=":star: Critical Success!", value=f"Maximum roll of {dice_sides}!", inline=False)
        else:
            # Check for all max or all min rolls
            if all(roll == dice_sides for roll in rolls):
                embed.add_field(name=":fire: LEGENDARY!", value="All maximum rolls!", inline=False)
            elif all(roll == 1 for roll in rolls):
                embed.add_field(name=":skull: DISASTER!", value="All ones... yikes!", inline=False)
        
        embed.set_footer(text=f"Rolled by {ctx.author.mention}")
        
        await ctx.send(embed=embed)
    
    @roll_dice.error
    async def roll_dice_error(self, ctx, error):
        """Handle errors for the roll command"""
        if isinstance(error, commands.MissingRequiredArgument):
            # Default to 1d6 if no argument provided
            await self.roll_dice(ctx, "1d6")
        else:
            await ctx.send(f":x: An error occurred: {str(error)}")


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(FunCommands(bot))