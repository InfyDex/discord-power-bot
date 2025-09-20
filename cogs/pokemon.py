"""
Pokemon Game cog for the Legion Discord Bot
Handles Pokemon encounters, catching, and collection management.
Refactored to use modular architecture with separate managers and command groups.
"""

import discord
from discord import app_commands
from discord.ext import commands
from .pokemon_system.managers import PokemonDatabaseManager, PlayerDataManager, WildSpawnManager
from .pokemon_system.commands import BasicPokemonCommands, CollectionPokemonCommands, AdminPokemonCommands, LeaderboardCommands, ShopCommands
from .pokemon_system.utils.mongo_manager import MongoManager

class Pokemon(commands.Cog):
    """Cog for Pokemon game functionality - Refactored Modular Version"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Initialize managers
        self.pokemon_db = PokemonDatabaseManager("pokemon_master_database.json")
        self.wild_spawn = WildSpawnManager("wild_spawn_data.json")
        self.mongo_db = MongoManager()  # Initialize MongoDB connection
        self.player_db = PlayerDataManager("pokemon_data.json", mongo_db=self.mongo_db)
        
        # Initialize command groups
        self.basic_commands = BasicPokemonCommands(self.pokemon_db, self.player_db, self.wild_spawn, self.mongo_db)
        self.collection_commands = CollectionPokemonCommands(self.pokemon_db, self.player_db, self.mongo_db)
        self.admin_commands = AdminPokemonCommands(self.pokemon_db, self.player_db, self.wild_spawn, self.mongo_db)
        self.leaderboard_commands = LeaderboardCommands(bot)
        self.shop_commands = ShopCommands(self.pokemon_db, self.player_db)
        
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
    
    # Prefix Commands
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
    
    @commands.command(name='daily_claim', aliases=['daily', 'claim'])
    async def daily_claim(self, ctx):
        """Claim your daily PokéCoin bonus (100 coins every 24 hours)"""
        await self.basic_commands.daily_claim(ctx)
    
    # Slash Commands
    @app_commands.command(name="encounter", description="Encounter a wild Pokemon (5-minute cooldown)")
    async def slash_encounter_pokemon(self, interaction: discord.Interaction):
        """Encounter a wild Pokemon (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.basic_commands._encounter_pokemon_logic(unified_ctx)
    
    @app_commands.command(name="catch", description="Attempt to catch your currently encountered Pokemon")
    @app_commands.describe(ball_type="Type of Pokeball to use (normal or master)")
    @app_commands.choices(ball_type=[
        app_commands.Choice(name="Normal Pokeball", value="normal"),
        app_commands.Choice(name="Master Ball (100% catch rate)", value="master")
    ])
    async def slash_catch_pokemon(self, interaction: discord.Interaction, ball_type: str = "normal"):
        """Attempt to catch the currently encountered Pokemon (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.basic_commands._catch_pokemon_logic(unified_ctx, ball_type)
    
    @app_commands.command(name="wild_catch", description="Attempt to catch the current wild Pokemon in #pokemon channel")
    async def slash_wild_catch(self, interaction: discord.Interaction):
        """Attempt to catch the current wild Pokemon in the pokemon channel (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.basic_commands._wild_catch_logic(unified_ctx)
    
    @app_commands.command(name="wild_status", description="Check the status of wild Pokemon spawning")
    async def slash_wild_status(self, interaction: discord.Interaction):
        """Check the status of wild Pokemon spawning (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.basic_commands._wild_status_logic(unified_ctx)
    
    @app_commands.command(name="daily_claim", description="Claim your daily PokéCoin bonus (100 coins every 24 hours)")
    async def slash_daily_claim(self, interaction: discord.Interaction):
        """Claim your daily PokéCoin bonus (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.basic_commands._daily_claim_logic(unified_ctx)
    
    # ===== SHOP COMMANDS =====
    
    # Prefix Commands
    @commands.command(name='shop', aliases=['store', 'pokeshop'])
    async def shop(self, ctx):
        """View the pokeball shop"""
        await self.shop_commands.show_shop(ctx)
    
    @commands.command(name='buy')
    async def buy_pokeball(self, ctx, ball_type: str, quantity: int = 1):
        """Buy pokeballs from the shop"""
        await self.shop_commands.buy_pokeball(ctx, ball_type, quantity)
    
    # Slash Commands
    @app_commands.command(name="shop", description="View the pokeball shop with prices and your balance")
    async def shop_slash(self, interaction: discord.Interaction):
        """View the pokeball shop (slash command)"""
        await self.shop_commands.show_shop(interaction)
    
    @app_commands.command(name="buy", description="Purchase pokeballs from the shop using pokecoins")
    @app_commands.describe(
        ball_type="Type of pokeball to buy (poke, great, ultra, master)",
        quantity="Number of pokeballs to purchase (default: 1)"
    )
    async def buy_pokeball_slash(self, interaction: discord.Interaction, ball_type: str, quantity: int = 1):
        """Buy pokeballs from the shop (slash command)"""
        await self.shop_commands.buy_pokeball(interaction, ball_type, quantity)
    
    # ===== COLLECTION COMMANDS =====
    
    # Prefix Commands
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
    
    # Leaderboard Commands
    @commands.command(name='leaderboard_pokemon', aliases=['lb_pokemon', 'pokemon_leaderboard'])
    async def leaderboard_pokemon(self, ctx):
        """View the Pokemon collection leaderboard (top 10 by unique Pokemon species)"""
        await self.leaderboard_commands.leaderboard_pokemon(ctx)
    
    @commands.command(name='leaderboard_power', aliases=['lb_power', 'power_leaderboard'])
    async def leaderboard_power(self, ctx):
        """View the total power leaderboard (top 10 by combined Pokemon power)"""
        await self.leaderboard_commands.leaderboard_power(ctx)
    
    @commands.command(name='leaderboard_rarity', aliases=['lb_rarity', 'rarity_leaderboard'])
    async def leaderboard_rarity(self, ctx):
        """View the rarity score leaderboard (top 10 by rare Pokemon)"""
        await self.leaderboard_commands.leaderboard_rarity(ctx)
    
    @commands.command(name='leaderboard_rank', aliases=['lb_rank', 'rank'])
    async def leaderboard_rank(self, ctx, target_user: discord.Member = None):
        """Check individual rank in all leaderboards"""
        if target_user is None:
            target_user = ctx.author
        
        # Show ranks in all leaderboard types
        await self.leaderboard_commands.leaderboard_rank_all(ctx, target_user)

    # Slash Commands
    @app_commands.command(name="collection", description="View your Pokemon collection or another user's collection")
    @app_commands.describe(user="User whose collection to view (optional)")
    async def slash_pokemon_collection(self, interaction: discord.Interaction, user: discord.Member = None):
        """View your Pokemon collection or another user's collection (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.collection_commands._pokemon_collection_logic(unified_ctx, user)
    
    @app_commands.command(name="pokemon_stats", description="View your Pokemon game statistics")
    async def slash_pokemon_stats(self, interaction: discord.Interaction):
        """View your Pokemon game statistics (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.collection_commands._pokemon_stats_logic(unified_ctx)
    
    @app_commands.command(name="inventory", description="View your Pokemon inventory and items")
    async def slash_pokemon_inventory(self, interaction: discord.Interaction):
        """View your Pokemon inventory and items (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.collection_commands._pokemon_inventory_logic(unified_ctx)
    
    @app_commands.command(name="pokemon_info", description="View detailed information about a specific Pokemon in your collection")
    @app_commands.describe(pokemon_identifier="Pokemon name or collection ID (e.g., 'Pikachu' or '#5')")
    async def slash_pokemon_info(self, interaction: discord.Interaction, pokemon_identifier: str):
        """View detailed information about a specific Pokemon in your collection (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.collection_commands._pokemon_info_logic(unified_ctx, pokemon_identifier)
    
    # ===== ADMIN COMMANDS =====
    
    # Prefix Commands
    @commands.command(name='pokemon_admin', aliases=['padmin'])
    async def pokemon_admin(self, ctx):
        """Admin command to view Pokemon database statistics"""
        await self.admin_commands.pokemon_admin(ctx)
    
    @commands.command(name='give_pokeball', aliases=['give_ball', 'pokeball_admin'])
    async def give_pokeball(self, ctx, user: discord.Member, ball_type: str, count: int):
        """Admin command to give pokeballs to a user"""
        await self.admin_commands.give_pokeball(ctx, user, ball_type, count)
    
    @commands.command(name='give_pokecoins', aliases=['give_coins', 'coins_admin'])
    async def give_pokecoins(self, ctx, user: discord.Member, amount: int):
        """Admin command to give PokéCoins to a user"""
        await self.admin_commands.give_pokecoins(ctx, user, amount)
    
    @commands.command(name='force_wild_spawn', aliases=['fws'])
    async def force_wild_spawn(self, ctx):
        """Admin command to manually trigger a wild Pokemon spawn"""
        await self.admin_commands.force_wild_spawn(ctx)
    
    @commands.command(name='debug_channels', aliases=['dchannels'])
    async def debug_channels(self, ctx):
        """Debug command to check available channels and bot permissions"""
        await self.admin_commands.debug_channels(ctx)
    
    # Slash Commands
    @app_commands.command(name="pokemon_admin", description="View Pokemon database statistics (Admin only)")
    async def slash_pokemon_admin(self, interaction: discord.Interaction):
        """Admin command to view Pokemon database statistics (slash command)"""
        # For now, create a quick ctx-like object for admin commands
        # TODO: Refactor admin commands to use unified context
        class QuickCtx:
            def __init__(self, interaction, bot):
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = bot
        
        quick_ctx = QuickCtx(interaction, self.bot)
        await self.admin_commands.pokemon_admin(quick_ctx)
    
    @app_commands.command(name="give_pokeball", description="Give pokeballs to a user (Admin only)")
    @app_commands.describe(
        user="User to give pokeballs to",
        ball_type="Type of pokeball to give",
        count="Number of pokeballs to give"
    )
    @app_commands.choices(ball_type=[
        app_commands.Choice(name="Normal Pokeball", value="normal"),
        app_commands.Choice(name="Master Ball", value="master")
    ])
    async def slash_give_pokeball(self, interaction: discord.Interaction, user: discord.Member, ball_type: str, count: int):
        """Admin command to give pokeballs to a user (slash command)"""
        # For now, create a quick ctx-like object for admin commands
        class QuickCtx:
            def __init__(self, interaction, bot):
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = bot
        
        quick_ctx = QuickCtx(interaction, self.bot)
        await self.admin_commands.give_pokeball(quick_ctx, user, ball_type, count)
    
    @app_commands.command(name="give_pokecoins", description="Give PokéCoins to a user (Admin only)")
    @app_commands.describe(
        user="User to give PokéCoins to",
        amount="Amount of PokéCoins to give"
    )
    async def slash_give_pokecoins(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Admin command to give PokéCoins to a user (slash command)"""
        # For now, create a quick ctx-like object for admin commands
        class QuickCtx:
            def __init__(self, interaction, bot):
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = bot
        
        quick_ctx = QuickCtx(interaction, self.bot)
        await self.admin_commands.give_pokecoins(quick_ctx, user, amount)
    
    @app_commands.command(name="force_wild_spawn", description="Manually trigger a wild Pokemon spawn (Admin only)")
    async def slash_force_wild_spawn(self, interaction: discord.Interaction):
        """Admin command to manually trigger a wild Pokemon spawn (slash command)"""
        # For now, create a quick ctx-like object for admin commands
        class QuickCtx:
            def __init__(self, interaction, bot):
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = bot
        
        quick_ctx = QuickCtx(interaction, self.bot)
        await self.admin_commands.force_wild_spawn(quick_ctx)
    
    @app_commands.command(name="debug_channels", description="Check available channels and bot permissions (Admin only)")
    async def slash_debug_channels(self, interaction: discord.Interaction):
        """Debug command to check available channels and bot permissions (slash command)"""
        # For now, create a quick ctx-like object for admin commands
        class QuickCtx:
            def __init__(self, interaction, bot):
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = bot
        
        quick_ctx = QuickCtx(interaction, self.bot)
        await self.admin_commands.debug_channels(quick_ctx)

    # Leaderboard Slash Commands
    @app_commands.command(name="leaderboard_pokemon", description="View Pokemon collection leaderboard (top 10)")
    async def slash_leaderboard_pokemon(self, interaction: discord.Interaction):
        """Pokemon collection leaderboard (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.leaderboard_commands._leaderboard_pokemon_logic(unified_ctx)
    
    @app_commands.command(name="leaderboard_power", description="View total power leaderboard (top 10)")
    async def slash_leaderboard_power(self, interaction: discord.Interaction):
        """Total power leaderboard (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.leaderboard_commands._leaderboard_power_logic(unified_ctx)
    
    @app_commands.command(name="leaderboard_rarity", description="View rarity score leaderboard (top 10)")
    async def slash_leaderboard_rarity(self, interaction: discord.Interaction):
        """Rarity score leaderboard (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        unified_ctx = create_unified_context(interaction)
        await self.leaderboard_commands._leaderboard_rarity_logic(unified_ctx)
    
    @app_commands.command(name="leaderboard_rank", description="Check individual rank in all leaderboards")
    @app_commands.describe(user="User to check rank for (defaults to yourself)")
    async def slash_leaderboard_rank(self, interaction: discord.Interaction, user: discord.Member = None):
        """Individual rank lookup showing all leaderboard types (slash command)"""
        from .pokemon_system.utils.interaction_utils import create_unified_context
        if user is None:
            user = interaction.user
        unified_ctx = create_unified_context(interaction)
        await self.leaderboard_commands._leaderboard_rank_all_logic(unified_ctx, user)


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(Pokemon(bot))