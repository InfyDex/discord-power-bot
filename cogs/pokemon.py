"""
Pokemon Game cog for the Legion Discord Bot
Handles Pokemon encounters, catching, and collection management.
Refactored to use modular architecture with separate managers and command groups.
"""

import discord
from discord import app_commands
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


    @commands.command(name="pokemon_lookup")
    async def pokemon_lookup(self, ctx, *, pokemon_identifier):
        """
        Look up a Pokémon by name or number from the database
        Usage: !pokemon_lookup <name or number>
        """
        # Convert the identifier to either a name (string) or number (int)
        pokemon_data = None
        
        # Try to find by ID first
        if pokemon_identifier.isdigit():
            pokemon_id = pokemon_identifier
            if pokemon_id in self.pokemon_database:
                pokemon_data = self.pokemon_database[pokemon_id]
                pokemon_data["id"] = int(pokemon_id)
        else:
            # Search by name (case-insensitive)
            pokemon_name = pokemon_identifier.lower()
            for pid, pdata in self.pokemon_database.items():
                if pdata["name"].lower() == pokemon_name:
                    pokemon_data = pdata
                    pokemon_data["id"] = int(pid)
                    break
        
        if not pokemon_data:
            await ctx.send(f"❌ Pokémon '{pokemon_identifier}' not found in the database.")
            return
        
        # Create an embed similar to the example image
        embed = discord.Embed(
            title=f"{pokemon_data['name']} - Pokedex Entry",
            description=f"A {pokemon_data['rarity'].lower()} Pokémon from Generation {pokemon_data['generation']}.",
            color=self.get_type_color(pokemon_data['types'][0])
        )
        
        # Add Pokedex number
        embed.add_field(
            name="Pokedex #",
            value=f"#{pokemon_data['id']}",
            inline=True
        )
        
        # Add Type
        type_str = " / ".join(pokemon_data['types'])
        embed.add_field(
            name="Type",
            value=type_str,
            inline=True
        )
        
        # Add Rarity
        embed.add_field(
            name="Rarity",
            value=pokemon_data['rarity'],
            inline=True
        )
        
        # Add Generation
        embed.add_field(
            name="Generation",
            value=f"Gen {pokemon_data['generation']}",
            inline=True
        )
        
        # Add Catch Rate
        embed.add_field(
            name="Catch Rate",
            value=f"{int(pokemon_data['catch_rate'] * 100)}%",
            inline=True
        )
        
        # Add Base Stat Total
        embed.add_field(
            name="Base Stat Total",
            value=str(pokemon_data['stats']['total']),
            inline=True
        )
        
        # Add Base Stats
        stats_text = f"HP: {pokemon_data['stats']['hp']} | Attack: {pokemon_data['stats']['attack']} | Defense: {pokemon_data['stats']['defense']} | "
        stats_text += f"Sp. Attack: {pokemon_data['stats']['sp_attack']} | Sp. Defense: {pokemon_data['stats']['sp_defense']} | Speed: {pokemon_data['stats']['speed']}"
        embed.add_field(
            name="Base Stats",
            value=stats_text,
            inline=False
        )
        
        # Add Requested By
        embed.add_field(
            name="Requested By",
            value=f"@{ctx.author.display_name}",
            inline=False
        )
        
        # Set the Pokemon image
        if 'image_url' in pokemon_data:
            embed.set_image(url=pokemon_data['image_url'])
        
        # Add footer
        embed.set_footer(text="Pokemon Information • Legion Pokemon System")
        
        await ctx.send(embed=embed)
    
    def get_type_color(self, pokemon_type):
        """Get a color based on the Pokemon's primary type"""
        type_colors = {
            "Normal": 0xA8A878,
            "Fire": 0xF08030,
            "Water": 0x6890F0,
            "Electric": 0xF8D030,
            "Grass": 0x78C850,
            "Ice": 0x98D8D8,
            "Fighting": 0xC03028,
            "Poison": 0xA040A0,
            "Ground": 0xE0C068,
            "Flying": 0xA890F0,
            "Psychic": 0xF85888,
            "Bug": 0xA8B820,
            "Rock": 0xB8A038,
            "Ghost": 0x705898,
            "Dragon": 0x7038F8,
            "Dark": 0x705848,
            "Steel": 0xB8B8D0,
            "Fairy": 0xEE99AC
        }
        
        return type_colors.get(pokemon_type, 0x68A090)  # Default color if type not found

    @commands.command(name='pokemon_duplication', aliases=['duplicates', 'dupes'])
    async def pokemon_duplication(self, ctx):
        """Show all duplicate Pokemon in your collection"""
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        pokemon_list = self.player_data[user_id]["pokemon"]
        
        if not pokemon_list:
            embed = discord.Embed(
                title="❌ No Pokemon Found",
                description="You haven't caught any Pokemon yet! Use `!encounter` to find wild Pokemon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Count Pokemon occurrences
        pokemon_counts = {}
        for pokemon in pokemon_list:
            name = pokemon['name']
            if name not in pokemon_counts:
                pokemon_counts[name] = []
            pokemon_counts[name].append({
                'id': pokemon['id'],
                'types': pokemon['types'],
                'caught_date': pokemon['caught_date'],
                'rarity': pokemon['rarity']
            })
        
        # Filter only duplicates (count > 1)
        duplicates = {name: info for name, info in pokemon_counts.items() if len(info) > 1}
        
        if not duplicates:
            embed = discord.Embed(
                title="🔍 No Duplicates Found",
                description="You don't have any duplicate Pokemon in your collection!",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Collection size: {len(pokemon_list)} unique Pokemon")
            await ctx.send(embed=embed)
            return
        
        # Create embed
        embed = discord.Embed(
            title="🔄 Your Duplicate Pokemon",
            description=f"Found duplicates in your collection of {len(pokemon_list)} Pokemon",
            color=discord.Color.gold()
        )
        
        # Add duplicate Pokemon information
        for name, instances in duplicates.items():
            # Get the first instance for type and rarity info
            pokemon_info = instances[0]
            type_text = " / ".join(pokemon_info['types'])
            
            # Create a clean list of duplicates
            dupes_text = []
            for inst in instances:
                catch_date = datetime.fromisoformat(inst['caught_date']).strftime("%Y-%m-%d")
                dupes_text.append(f"• ID #{inst['id']} (Caught: {catch_date})")
            
            # Add field for each duplicate Pokemon
            embed.add_field(
                name=f"📋 {name} × {len(instances)}",
                value=f"**Type:** {type_text}\n**Rarity:** {pokemon_info['rarity']}\n\n**Copies:**\n" + "\n".join(dupes_text),
                inline=False
            )
        
        # Add summary
        total_dupes = sum(len(instances) - 1 for instances in duplicates.values())
        embed.add_field(
            name="📊 Summary",
            value=f"**Total Duplicate Species:** {len(duplicates)}\n**Total Extra Copies:** {total_dupes}",
            inline=False
        )
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Use !pokemon_info <id> to view detailed information about specific Pokemon")
        
        await ctx.send(embed=embed)
    
async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(Pokemon(bot))