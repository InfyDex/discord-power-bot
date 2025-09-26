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
    
    # ========== PARTY MANAGEMENT COMMANDS ==========
    
    async def party_add_logic(self, unified_ctx: UnifiedContext, index: int, pokemon_id: int) -> bool:
        """
        Shared logic for adding Pokémon to party
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        
        # Validate index
        if not isinstance(index, int) or not (1 <= index <= 6):
            embed = discord.Embed(
                title="❌ Invalid Party Index",
                description="Party index must be a number between 1 and 6.",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False
        
        # Validate pokemon_id
        if not isinstance(pokemon_id, int) or pokemon_id <= 0:
            embed = discord.Embed(
                title="❌ Invalid Pokemon ID",
                description="Pokemon ID must be a positive number.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Tip", 
                value="Use `!collection` to see valid Pokemon IDs.", 
                inline=False
            )
            await unified_ctx.send(embed=embed)
            return False
        
        # Check if user owns the Pokémon
        user_pokemon = self.mongo_db.get_pokemon_by_owner(user_id)
        owned_pokemon = None
        
        for pokemon in user_pokemon:
            if pokemon.get('id') == pokemon_id:
                owned_pokemon = pokemon
                break
        
        if not owned_pokemon:
            embed = discord.Embed(
                title="❌ Pokémon Not Found",
                description=f"You don't own a Pokémon with ID #{pokemon_id}.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Tip", 
                value="Use `!collection` to see your Pokémon and their IDs.", 
                inline=False
            )
            await unified_ctx.send(embed=embed)
            return False
        
        # Check if Pokémon is already in party
        existing_party = self.mongo_db.get_party(user_id)
        if existing_party:
            slot_map = {
                1: "first_pokemon",
                2: "second_pokemon",
                3: "third_pokemon", 
                4: "fourth_pokemon",
                5: "fifth_pokemon",
                6: "sixth_pokemon"
            }
            
            for slot_num, slot_field in slot_map.items():
                if existing_party.get(slot_field) == pokemon_id and slot_num != index:
                    embed = discord.Embed(
                        title="❌ Pokémon Already in Party",
                        description=f"**{owned_pokemon['name']}** is already in your party at slot {slot_num}!\nEach Pokémon can only be in one party slot.",
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="💡 Tip", 
                        value=f"Remove it from slot {slot_num} first, or choose a different Pokémon.", 
                        inline=False
                    )
                    await unified_ctx.send(embed=embed)
                    return False
        
        # Add Pokémon to party
        success = self.mongo_db.add_pokemon_to_party(user_id, index, pokemon_id)
        
        if success:
            embed = discord.Embed(
                title="✅ Pokémon Added to Party",
                description=f"**{owned_pokemon['name']}** (#{pokemon_id}) has been added to party slot {index}!",
                color=discord.Color.green()
            )
            
            # Add Pokémon details
            embed.add_field(name="Name", value=owned_pokemon['name'], inline=True)
            embed.add_field(name="Type", value=", ".join(owned_pokemon['types']), inline=True)
            embed.add_field(name="Rarity", value=owned_pokemon['rarity'], inline=True)
            embed.add_field(name="Party Slot", value=f"Position {index}", inline=True)
            
            if 'sprite_url' in owned_pokemon and owned_pokemon['sprite_url']:
                embed.set_thumbnail(url=owned_pokemon['sprite_url'])
            
            await unified_ctx.send(embed=embed)
            return True
        else:
            embed = discord.Embed(
                title="❌ Failed to Add Pokémon",
                description="An error occurred while adding the Pokémon to your party.",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False
    
    async def party_show_logic(self, unified_ctx: UnifiedContext) -> bool:
        """
        Shared logic for showing user's party
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        
        # Get user's party
        party = self.mongo_db.get_party(user_id)
        
        if not party:
            embed = discord.Embed(
                title="📋 Your Pokémon Party",
                description="Your party is empty! Use `!party_add <index> <pokemon_id>` to add Pokémon.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="🔹 How to add Pokémon:", 
                value="1. Use `!collection` to see your Pokémon IDs\n2. Use `!party_add 1 25` to add Pokémon #25 to slot 1", 
                inline=False
            )
            await unified_ctx.send(embed=embed)
            return True
        
        # Get user's actual Pokemon collection for validation
        user_pokemon = self.mongo_db.get_pokemon_by_owner(user_id)
        valid_pokemon_ids = {pokemon.get('id') for pokemon in user_pokemon}
        
        # Map party slots
        slot_map = {
            1: "first_pokemon",
            2: "second_pokemon",
            3: "third_pokemon", 
            4: "fourth_pokemon",
            5: "fifth_pokemon",
            6: "sixth_pokemon"
        }
        
        # Check for orphaned references and clean them up
        cleaned_party = dict(party)
        has_orphaned = False
        
        for slot_num, slot_field in slot_map.items():
            pokemon_id = party.get(slot_field)
            if pokemon_id and pokemon_id not in valid_pokemon_ids:
                cleaned_party[slot_field] = None
                has_orphaned = True
        
        # If we found orphaned references, update the party and recurse
        if has_orphaned:
            self.mongo_db.create_or_update_party(user_id, cleaned_party)
            # Recursively call this function to show the cleaned party
            return await self.party_show_logic(unified_ctx)
        
        embed = discord.Embed(
            title=f"📋 {unified_ctx.author.display_name}'s Pokémon Party",
            description="Your current party lineup:",
            color=discord.Color.blue()
        )
        
        embed.set_thumbnail(url=unified_ctx.author.display_avatar.url)
        
        party_count = 0
        
        for slot_num in range(1, 7):
            slot_field = slot_map[slot_num]
            pokemon_id = party.get(slot_field)
            
            if pokemon_id:
                # Get Pokémon details
                pokemon_data = None
                
                for pokemon in user_pokemon:
                    if pokemon.get('id') == pokemon_id:
                        pokemon_data = pokemon
                        break
                
                if pokemon_data:
                    party_count += 1
                    embed.add_field(
                        name=f"🔹 Slot {slot_num}",
                        value=f"**{pokemon_data['name']}** (#{pokemon_id})\nType: {', '.join(pokemon_data['types'])}\nRarity: {pokemon_data['rarity']}",
                        inline=True
                    )
            else:
                embed.add_field(
                    name=f"🔸 Slot {slot_num}",
                    value="*Empty*",
                    inline=True
                )
        
        embed.add_field(
            name="📊 Party Stats",
            value=f"**{party_count}/6** slots filled",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Use `!party_add <slot> <pokemon_id>` to add Pokémon\n• Use `!party_remove <slot>` to remove specific Pokémon\n• Use `!collection` to see your Pokémon IDs",
            inline=False
        )
        
        await unified_ctx.send(embed=embed)
        return True
    
    async def party_add(self, ctx, index: int, pokemon_id: int):
        """Add a Pokémon to your party (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.party_add_logic(unified_ctx, index, pokemon_id)
    
    async def party_show(self, ctx):
        """Show your current party (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.party_show_logic(unified_ctx)
    
    async def party_remove_logic(self, unified_ctx: UnifiedContext, index: int) -> bool:
        """
        Shared logic for removing Pokémon from party
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        
        # Validate index
        if not isinstance(index, int) or not (1 <= index <= 6):
            embed = discord.Embed(
                title="❌ Invalid Party Index",
                description="Party index must be a number between 1 and 6.",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False
        
        # Get current party
        party = self.mongo_db.get_party(user_id)
        if not party:
            embed = discord.Embed(
                title="❌ No Party Found",
                description="You don't have a party yet! Use `!party_add` to add Pokémon first.",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False
        
        # Check if slot has a Pokémon
        slot_map = {
            1: "first_pokemon",
            2: "second_pokemon",
            3: "third_pokemon", 
            4: "fourth_pokemon",
            5: "fifth_pokemon",
            6: "sixth_pokemon"
        }
        
        slot_field = slot_map[index]
        pokemon_id = party.get(slot_field)
        
        if not pokemon_id:
            embed = discord.Embed(
                title="❌ Slot Already Empty",
                description=f"Party slot {index} is already empty!",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False
        
        # Get Pokémon details for confirmation
        user_pokemon = self.mongo_db.get_pokemon_by_owner(user_id)
        pokemon_data = None
        
        for pokemon in user_pokemon:
            if pokemon.get('id') == pokemon_id:
                pokemon_data = pokemon
                break
        
        # Remove Pokémon from party
        success = self.mongo_db.remove_pokemon_from_party(user_id, index)
        
        if success:
            pokemon_name = pokemon_data['name'] if pokemon_data else f"Pokemon #{pokemon_id}"
            embed = discord.Embed(
                title="✅ Pokémon Removed from Party",
                description=f"**{pokemon_name}** has been removed from party slot {index}!",
                color=discord.Color.green()
            )
            
            if pokemon_data and 'sprite_url' in pokemon_data and pokemon_data['sprite_url']:
                embed.set_thumbnail(url=pokemon_data['sprite_url'])
            
            await unified_ctx.send(embed=embed)
            return True
        else:
            embed = discord.Embed(
                title="❌ Failed to Remove Pokémon",
                description="An error occurred while removing the Pokémon from your party.",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False
    
    async def party_remove(self, ctx, index: int):
        """Remove a Pokémon from your party at a specific index (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.party_remove_logic(unified_ctx, index)
