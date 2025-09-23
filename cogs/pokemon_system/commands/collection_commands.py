from datetime import datetime
from typing import Optional

import discord

from ..managers import PokemonDatabaseManager, PlayerDataManager
from ..models.pokemon_model import CaughtPokemon
from ..utils import PokemonEmbedUtils
from ..utils.interaction_utils import UnifiedContext, create_unified_context
from ..utils.mongo_manager import MongoManager


class CollectionPokemonCommands:
    """Contains Pokémon collection management commands with shared logic architecture"""
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager, mongo_db: MongoManager=None):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
        self.mongo_db = mongo_db
    
    # ========== SHARED LOGIC FUNCTIONS ==========
    
    async def pokemon_collection_logic(self, unified_ctx: UnifiedContext, user: discord.Member = None, pokemon_identifier: str = None) -> bool:
        """
        Shared logic for both prefix and slash collection commands
        Returns True if successful, False if failed
        """
        # If no user mentioned, show the author's collection
        if user is None:
            user = unified_ctx.author
            user_id = str(unified_ctx.author.id)
            is_own_collection = True
        else:
            user_id = str(user.id)
            is_own_collection = (user.id == unified_ctx.author.id)
        pokemon_collection = []
        caught_pokemons = self.mongo_db.get_pokemon_by_owner(user_id)
        for pokemon_data in caught_pokemons:
            caught_pokemon = CaughtPokemon.from_dict(pokemon_data)
            pokemon_collection.append(caught_pokemon)

        if pokemon_identifier:
            found_pokemon: Optional[CaughtPokemon] = None

            if pokemon_identifier.startswith('#'):
                for pokemon in pokemon_collection:
                    if str(pokemon.collection_id) == pokemon_identifier[1:]:
                        found_pokemon = pokemon
                        break
            else:
                for pokemon in pokemon_collection:
                    if pokemon.name.lower() == pokemon_identifier.lower():
                        found_pokemon = pokemon
                        break

            if not found_pokemon:
                await self._pokemon_not_found(unified_ctx, pokemon_identifier)
                return False

            # Create detailed Pokémon embed
            embed = PokemonEmbedUtils.create_cached_pokemon_detail_embed(
                pokemon=found_pokemon,
                user_mention=user.mention
            )
            await unified_ctx.send(embed=embed)
            return True
        
        # Create collection embed
        embed = PokemonEmbedUtils.create_collection_embed(
            player_name=user.display_name,
            pokemon_collection=pokemon_collection,
            is_own_collection=is_own_collection,
            user_mention=user.mention
        )
        
        await unified_ctx.send(embed=embed)
        return True
    
    async def pokemon_stats_logic(self, unified_ctx: UnifiedContext) -> bool:
        """
        Shared logic for both prefix and slash stats commands
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Create stats embed
        embed = discord.Embed(
            title=f"📊 {unified_ctx.author.display_name}'s Pokemon Stats",
            color=discord.Color.blue()
        )
        
        embed.set_thumbnail(url=unified_ctx.author.display_avatar.url)
        
        # Basic stats
        total_caught = len(player.pokemon_collection)
        total_encounters = player.stats.total_encounters
        catch_rate = player.stats.get_catch_rate()
        
        embed.add_field(name="🎯 Total Caught", value=f"{total_caught}", inline=True)
        embed.add_field(name="👁️ Total Encounters", value=f"{total_encounters}", inline=True)
        embed.add_field(name="📈 Catch Rate", value=f"{catch_rate:.1f}%", inline=True)
        
        # Currency
        embed.add_field(name="💰 PokéCoins", value=f"{player.pokecoins:,}", inline=True)
        
        # Join date
        join_date = datetime.fromisoformat(player.stats.join_date).strftime("%B %d, %Y")
        embed.add_field(name="📅 Trainer Since", value=join_date, inline=True)
        
        # Enhanced Pokeball Inventory with icons
        all_balls = player.inventory.get_all_balls()
        pokeball_text = ""
        for ball_type, ball_data in all_balls.items():
            if ball_data["count"] > 0:
                # Use emoji as fallback if icon URL fails
                emoji = {"poke": "⚪", "great": "🔵", "ultra": "🟡", "master": "🟣"}.get(ball_type, "⚫")
                pokeball_text += f"{emoji} {ball_data['name']}: {ball_data['count']}\n"
        
        if not pokeball_text:
            pokeball_text = "No poke balls"
            
        embed.add_field(name="� Pokeball Inventory", value=pokeball_text, inline=True)
        
        # Rarity breakdown
        if player.pokemon_collection:
            rarity_counts = {"Common": 0, "Uncommon": 0, "Rare": 0, "Legendary": 0}
            for pokemon in player.pokemon_collection:
                if pokemon.rarity in rarity_counts:
                    rarity_counts[pokemon.rarity] += 1
            
            rarity_text = " | ".join([f"{rarity}: {count}" for rarity, count in rarity_counts.items() if count > 0])
            embed.add_field(name="⭐ Collection Breakdown", value=rarity_text, inline=False)
        
        await unified_ctx.send(embed=embed)
        return True
    
    async def pokemon_inventory_logic(self, unified_ctx: UnifiedContext) -> bool:
        """
        Shared logic for both prefix and slash inventory commands
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        embed = discord.Embed(
            title=f"🎒 {unified_ctx.author.display_name}'s Inventory",
            description="Your Pokemon game items and resources",
            color=discord.Color.green()
        )
        
        embed.set_thumbnail(url=unified_ctx.author.display_avatar.url)
        
        # Enhanced Pokeball Inventory
        all_balls = player.inventory.get_all_balls()
        pokeball_text = ""
        
        for ball_type, ball_data in all_balls.items():
            count = ball_data["count"]
            if count > 0:
                # Use emoji as fallback
                emoji = {"poke": "⚪", "great": "🔵", "ultra": "🟡", "master": "🟣"}.get(ball_type, "⚫")
                pokeball_text += f"{emoji} {ball_data['name']}: **{count}**\n"
        
        if not pokeball_text:
            pokeball_text = "No poke balls in inventory"
            
        embed.add_field(name="� Pokeball Inventory", value=pokeball_text, inline=False)
        
        # Currency
        embed.add_field(name="💰 PokéCoins", value=f"{player.pokecoins:,}", inline=True)
        
        # Stats
        total_caught = len(player.pokemon_collection)
        embed.add_field(name="📦 Pokemon Owned", value=f"{total_caught}", inline=True)
        embed.add_field(name="📊 Catch Rate", value=f"{player.stats.get_catch_rate():.1f}%", inline=True)
        
        # Current encounter
        if player.current_encounter:
            embed.add_field(name="🌿 Current Encounter", value=f"{player.current_encounter.name}", inline=True)
        else:
            embed.add_field(name="🌿 Current Encounter", value="None", inline=True)
        
        await unified_ctx.send(embed=embed)
        return True

    async def pokedex_page_logic(self, unified_ctx: UnifiedContext, page_number: int, only_show_duplicates: bool) -> bool:
        """
        Shared logic for both prefix and slash Pokédex page commands
        Returns True if successful, False if failed
        """
        pokedex_per_page = 10
        duplicate_names = {}
        if only_show_duplicates:
            # Get all Pokémon and filter for duplicates
            all_pokemons = self.mongo_db.get_pokemon_by_owner(str(unified_ctx.author.id))
            name_count = {}
            for p in all_pokemons:
                name = p.get('name')
                name_count[name] = name_count.get(name, 0) + 1
            for name in name_count:
                if name_count[name] > 1:
                    duplicate_names[name] = name_count[name]
            total_pokemon = len(duplicate_names)
        else:
            total_pokemon = self.mongo_db.count_pokemon_by_owner(str(unified_ctx.author.id))

        total_pages = (total_pokemon + pokedex_per_page - 1) // pokedex_per_page

        if page_number < 1 or page_number > total_pages:
            embed = discord.Embed(
                title="❌ Invalid Page Number",
                description=f"Please enter a page number between 1 and {total_pages}.",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False

        embed = discord.Embed(
            title=f"📖 Pokédex - Page {page_number}/{total_pages}",
            description="List of Pokémon in the database",
            color=discord.Color.purple()
        )

        if duplicate_names:
            embed.description += " (Showing Duplicates Only)"
            duplicate_names = dict(
                sorted(duplicate_names.items(), key=lambda item: item[1], reverse=True)
            )
            start_index = (page_number - 1) * pokedex_per_page
            end_index = start_index + pokedex_per_page
            duplicate_name_count = dict(list(duplicate_names.items())[start_index:end_index])
            for (name, count) in duplicate_name_count.items():
                if count > 1:
                    embed.add_field(
                        name=f"{name}",
                        value=f"Count: {count}",
                        inline=False
                    )

        else:
            # Fetch Pokémon for the requested page
            pokemons_on_page = self.mongo_db.get_pokemon_by_owner(
                str(unified_ctx.author.id),
                page=page_number,
                max_per_page = pokedex_per_page
            )

            for pokemon in pokemons_on_page:
                embed.add_field(
                    name=f"#{pokemon.get('id')} {pokemon.get('name')}",
                    value=f"Type: {', '.join(pokemon.get('types'))} | Rarity: {pokemon.get('rarity')}",
                    inline=False
                )

        embed.set_footer(text=f"Requested by {unified_ctx.author.mention}")

        embed.set_footer(text="Use the command with a page number to view other pages.")

        await unified_ctx.send(embed=embed)
        return True
    
    async def pokemon_info_logic(self, unified_ctx: UnifiedContext, pokemon_identifier: str) -> bool:
        """
        Shared logic for both prefix and slash Pokémon info commands
        Returns True if successful, False if failed
        """
        
        # Find Pokémon by ID or name
        found_pokemon = None
        
        # Check if it's a collection ID (starts with #)
        if pokemon_identifier.startswith('#'):
            try:
                collection_id = int(pokemon_identifier[1:])
                found_pokemon = self.pokemon_db.get_pokemon_by_id(collection_id)
            except ValueError:
                pass
        else:
            # Search by name
            pokemons = self.pokemon_db.search_pokemon(pokemon_identifier)
            if pokemons:
                found_pokemon = pokemons[0]
        
        if not found_pokemon:
            await self._pokemon_not_found(unified_ctx, pokemon_identifier)
            return False
        
        # Create detailed Pokémon embed
        embed = PokemonEmbedUtils.create_pokemon_detail_embed(
            pokemon=found_pokemon,
            user_mention=unified_ctx.author.mention
        )
        
        await unified_ctx.send(embed=embed)
        return True

    @staticmethod
    async def _pokemon_not_found(unified_ctx: UnifiedContext, identifier: str):
        embed = discord.Embed(
            title="❌ Pokemon Not Found",
            description=f"Could not find a Pokemon matching '{identifier}'.",
            color=discord.Color.red()
        )
        embed.add_field(name="💡 Tip", value="Use the Pokemon's name or collection ID (e.g., '#5')", inline=False)
        await unified_ctx.send(embed=embed)
    
    # ========== LEGACY PREFIX COMMANDS ==========
    
    async def pokemon_collection(self, ctx, user: discord.Member = None, pokemon_identifier: str = None):
        """View your Pokémon collection or another user's collection (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.pokemon_collection_logic(unified_ctx, user, pokemon_identifier)
    
    async def pokemon_stats(self, ctx):
        """View your Pokémon game statistics (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.pokemon_stats_logic(unified_ctx)
    
    async def pokemon_inventory(self, ctx):
        """View your Pokémon inventory and items (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.pokemon_inventory_logic(unified_ctx)
    
    async def pokemon_info(self, ctx, *, pokemon_identifier):
        """View detailed information about a specific Pokémon in your collection (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.pokemon_info_logic(unified_ctx, pokemon_identifier)

    async def pokedex_page(self, ctx, page_number: int, only_show_duplicates: bool):
        """View a page of the Pokédex (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.pokedex_page_logic(unified_ctx, page_number, only_show_duplicates)