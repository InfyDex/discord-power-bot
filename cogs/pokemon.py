"""
Pokemon Game cog for the Legion Discord Bot
Handles Pokemon encounters, catching, and collection management.
Refactored to use modular architecture with separate managers and command groups.
"""

import discord
from discord.ext import commands
from .pokemon_system.managers import PokemonDatabaseManager, PlayerDataManager, WildSpawnManager
from .pokemon_system.commands import BasicPokemonCommands, CollectionPokemonCommands, AdminPokemonCommands

class Pokemon(commands.Cog):
    """Cog for Pokemon game functionality - Refactored Modular Version"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Initialize managers
        self.pokemon_db = PokemonDatabaseManager("pokemon_master_database.json")
        self.player_db = PlayerDataManager("pokemon_data.json")
        self.wild_spawn = WildSpawnManager("wild_spawn_data.json")
        
        # Initialize command groups
        self.basic_commands = BasicPokemonCommands(self.pokemon_db, self.player_db, self.wild_spawn)
        self.collection_commands = CollectionPokemonCommands(self.pokemon_db, self.player_db)
        self.admin_commands = AdminPokemonCommands(self.pokemon_db, self.player_db, self.wild_spawn)
        
        # Track spawn task status
        self._spawn_task_started = False
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener that triggers when the bot is ready and connected to guilds"""
        # Only start the spawn task once, after the bot is connected
        if not self._spawn_task_started and len(self.bot.guilds) > 0:
            self.wild_spawn.start_spawn_task(self.bot, self.pokemon_db)
            self._spawn_task_started = True
            print(f"Wild Pokemon spawn task started! Bot is connected to {len(self.bot.guilds)} guild(s)")
    
    # ===== BASIC COMMANDS =====
    
    @commands.command(name='encounter', aliases=['wild', 'pokemon'])
    async def encounter_pokemon(self, ctx):
        """Encounter a wild Pokemon"""
        await self.basic_commands.encounter_pokemon(ctx)
    
    @commands.command(name='catch')
    async def catch_pokemon(self, ctx, ball_type: str = "normal"):
        """Attempt to catch the currently encountered Pokemon"""
        await self.basic_commands.catch_pokemon(ctx, ball_type)
    
    @commands.command(name='wild_catch', aliases=['wcatch'])
    async def wild_catch(self, ctx):
        """Attempt to catch the current wild Pokemon in the pokemon channel"""
        await self.basic_commands.wild_catch(ctx)
    
    @commands.command(name='wild_status', aliases=['wstatus'])
    async def wild_status(self, ctx):
        """Check the status of wild Pokemon spawning"""
        await self.basic_commands.wild_status(ctx)
    
    # ===== COLLECTION COMMANDS =====
    
    @commands.command(name='pokemon_list', aliases=['pokedex', 'collection'])
    async def pokemon_collection(self, ctx, user: discord.Member = None):
        """View your Pokemon collection or another user's collection"""
        await self.collection_commands.pokemon_collection(ctx, user)
    
    @commands.command(name='pokemon_stats', aliases=['stats'])
    async def pokemon_stats(self, ctx):
        """View your Pokemon game statistics"""
        await self.collection_commands.pokemon_stats(ctx)
    
    @commands.command(name='inventory', aliases=['inv', 'bag'])
    async def pokemon_inventory(self, ctx):
        """View your Pokemon inventory and items"""
        await self.collection_commands.pokemon_inventory(ctx)
    
    @commands.command(name='pokemon_info', aliases=['pinfo', 'pokemon_detail'])
    async def pokemon_info(self, ctx, *, pokemon_identifier):
        """View detailed information about a specific Pokemon in your collection"""
        await self.collection_commands.pokemon_info(ctx, pokemon_identifier=pokemon_identifier)
    
    # ===== ADMIN COMMANDS =====
    
    @commands.command(name='pokemon_admin', aliases=['padmin'])
    async def pokemon_admin(self, ctx):
        """Admin command to view Pokemon database statistics"""
        await self.admin_commands.pokemon_admin(ctx)
    
    @commands.command(name='give_pokeball', aliases=['give_ball', 'pokeball_admin'])
    async def give_pokeball(self, ctx, user: discord.Member, ball_type: str, count: int):
        """Admin command to give pokeballs to a user"""
        await self.admin_commands.give_pokeball(ctx, user, ball_type, count)
    
    @commands.command(name='force_wild_spawn', aliases=['fws'])
    async def force_wild_spawn(self, ctx):
        """Admin command to manually trigger a wild Pokemon spawn"""
        await self.admin_commands.force_wild_spawn(ctx)
    
    @commands.command(name='debug_channels', aliases=['dchannels'])
    async def debug_channels(self, ctx):
        """Debug command to check available channels and bot permissions"""
        await self.admin_commands.debug_channels(ctx)


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(Pokemon(bot))