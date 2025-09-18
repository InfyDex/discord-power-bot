"""
Collection Pokemon Commands
Handles commands related to viewing and managing Pokemon collectio        embed.add_field(name="� Pokeball Inventory", value=pokeball_text, inline=True)
        
        # Catch Limit Information
        remaining_catches = player.get_remaining_catches()
        cooldown_time = player.get_catch_cooldown_remaining()
        
        if remaining_catches == 5:
            catch_limit_text = "✅ Full catch limit available (5/5)"
        elif remaining_catches > 0:
            catch_limit_text = f"⚠️ {remaining_catches}/5 catches remaining"
            if cooldown_time:
                catch_limit_text += f"\nNext reset: {cooldown_time}"
        else:
            catch_limit_text = "🚫 Catch limit reached (0/5)"
            if cooldown_time:
                catch_limit_text += f"\nNext reset: {cooldown_time}"
        
        embed.add_field(name="🕒 Hourly Catch Limit", value=catch_limit_text, inline=True)s.
"""

import discord
from datetime import datetime
from ..managers import PokemonDatabaseManager, PlayerDataManager
from ..utils import PokemonEmbedUtils, PokemonTypeUtils
from ..utils.interaction_utils import UnifiedContext, create_unified_context


class CollectionPokemonCommands:
    """Contains Pokemon collection management commands with shared logic architecture"""
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
    
    # ========== SHARED LOGIC FUNCTIONS ==========
    
    async def _pokemon_collection_logic(self, unified_ctx: UnifiedContext, user: discord.Member = None) -> bool:
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
        
        player = self.player_db.get_player(user_id)
        
        if not player.pokemon_collection:
            # Use the embed utility which already handles empty collections
            embed = PokemonEmbedUtils.create_collection_embed(
                player_name=user.display_name,
                pokemon_collection=[],  # Empty collection
                is_own_collection=is_own_collection,
                user_mention=user.mention
            )
            await unified_ctx.send(embed=embed)
            return True
        
        # Create collection embed
        embed = PokemonEmbedUtils.create_collection_embed(
            player_name=user.display_name,
            pokemon_collection=player.pokemon_collection,
            is_own_collection=is_own_collection,
            user_mention=user.mention
        )
        
        await unified_ctx.send(embed=embed)
        return True
    
    async def _pokemon_stats_logic(self, unified_ctx: UnifiedContext) -> bool:
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
            pokeball_text = "No pokeballs"
            
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
    
    async def _pokemon_inventory_logic(self, unified_ctx: UnifiedContext) -> bool:
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
        total_value = 0
        
        for ball_type, ball_data in all_balls.items():
            count = ball_data["count"]
            if count > 0:
                # Use emoji as fallback
                emoji = {"poke": "⚪", "great": "🔵", "ultra": "🟡", "master": "🟣"}.get(ball_type, "⚫")
                pokeball_text += f"{emoji} {ball_data['name']}: **{count}**\n"
                
                # Calculate value (example values)
                values = {"poke": 1, "great": 3, "ultra": 6, "master": 50}
                total_value += count * values.get(ball_type, 1)
        
        if not pokeball_text:
            pokeball_text = "No pokeballs in inventory"
            
        embed.add_field(name="� Pokeball Inventory", value=pokeball_text, inline=False)
        embed.add_field(name="💰 Total Inventory Value", value=f"{total_value} credits", inline=True)
        
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
    
    async def _pokemon_info_logic(self, unified_ctx: UnifiedContext, pokemon_identifier: str) -> bool:
        """
        Shared logic for both prefix and slash pokemon info commands
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        if not player.pokemon_collection:
            embed = discord.Embed(
                title="📖 No Pokemon Found",
                description="You haven't caught any Pokemon yet! Use `!encounter` or `/encounter` to find Pokemon.",
                color=discord.Color.red()
            )
            await unified_ctx.send(embed=embed)
            return False
        
        # Find Pokemon by ID or name
        found_pokemon = None
        
        # Check if it's a collection ID (starts with #)
        if pokemon_identifier.startswith('#'):
            try:
                collection_id = int(pokemon_identifier[1:])
                found_pokemon = next((p for p in player.pokemon_collection if p.collection_id == collection_id), None)
            except ValueError:
                pass
        else:
            # Search by name
            found_pokemon = next((p for p in player.pokemon_collection if p.name.lower() == pokemon_identifier.lower()), None)
        
        if not found_pokemon:
            embed = discord.Embed(
                title="❌ Pokemon Not Found",
                description=f"Could not find a Pokemon matching '{pokemon_identifier}' in your collection.",
                color=discord.Color.red()
            )
            embed.add_field(name="💡 Tip", value="Use the Pokemon's name or collection ID (e.g., '#5')", inline=False)
            await unified_ctx.send(embed=embed)
            return False
        
        # Create detailed Pokemon embed
        embed = PokemonEmbedUtils.create_pokemon_detail_embed(
            pokemon=found_pokemon,
            user_mention=unified_ctx.author.mention
        )
        
        await unified_ctx.send(embed=embed)
        return True
    
    # ========== LEGACY PREFIX COMMANDS ==========
    
    async def pokemon_collection(self, ctx, user: discord.Member = None):
        """View your Pokemon collection or another user's collection (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._pokemon_collection_logic(unified_ctx, user)
    
    async def pokemon_stats(self, ctx):
        """View your Pokemon game statistics (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._pokemon_stats_logic(unified_ctx)
    
    async def pokemon_inventory(self, ctx):
        """View your Pokemon inventory and items (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._pokemon_inventory_logic(unified_ctx)
    
    async def pokemon_info(self, ctx, *, pokemon_identifier):
        """View detailed information about a specific Pokemon in your collection (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._pokemon_info_logic(unified_ctx, pokemon_identifier)