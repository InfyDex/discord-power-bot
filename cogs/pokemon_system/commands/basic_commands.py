"""
Basic Pokemon Commands
Handles core Pokemon gameplay commands like encounters and catching.
Clean, optimized version with shared logic and no duplication.
"""

import discord
from datetime import datetime
from typing import Optional

from ..managers import PokemonDatabaseManager, PlayerDataManager, WildSpawnManager
from ..utils import PokemonEmbedUtils, PokemonTypeUtils, ValidationUtils, ErrorUtils
from ..utils.interaction_utils import UnifiedContext, create_unified_context


class BasicPokemonCommands:
    """Contains basic Pokemon gameplay commands with shared logic architecture"""
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager, wild_spawn: WildSpawnManager):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
        self.wild_spawn = wild_spawn
    
    # ========== SHARED LOGIC FUNCTIONS ==========
    
    async def _encounter_pokemon_logic(self, unified_ctx: UnifiedContext) -> bool:
        """
        Shared logic for both prefix and slash encounter commands
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Check cooldown
        if not player.can_encounter():
            cooldown_remaining = player.get_cooldown_remaining_formatted()
            if cooldown_remaining:  # Only show cooldown if there's actually time remaining
                embed = discord.Embed(
                    title="⏰ Encounter Cooldown",
                    description=f"You need to wait **{cooldown_remaining}** before encountering another Pokemon!",
                    color=discord.Color.orange()
                )
                await unified_ctx.send_error(embed)
                return False
        
        # Get random Pokemon
        pokemon = self.pokemon_db.get_random_pokemon_by_rarity_weights()
        if not pokemon:
            embed = discord.Embed(
                title="❌ Error",
                description="No Pokemon available for encounter. Please try again later.",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        
        # Update player with encounter
        player.add_encounter(pokemon)
        self.player_db.save_player(user_id)
        
        # Create and send embed
        embed = PokemonEmbedUtils.create_encounter_embed(
            pokemon=pokemon,
            user=unified_ctx.author,
            encounter_type="encounter"
        )
        
        await unified_ctx.send(embed=embed)
        return True
    
    async def _catch_pokemon_logic(self, unified_ctx: UnifiedContext, ball_type: str = "normal") -> bool:
        """
        Shared logic for both prefix and slash catch commands
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Check if there's a current encounter
        if not player.current_encounter:
            embed = discord.Embed(
                title="❌ No Pokemon to Catch",
                description="You need to encounter a Pokemon first! Use `!encounter` or `/encounter` to find a wild Pokemon.",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        
        # Validate ball type using ValidationUtils
        is_valid, error_message = ValidationUtils.validate_ball_type(ball_type)
        if not is_valid:
            embed = ErrorUtils.create_invalid_input_embed("ball type", ValidationUtils.VALID_BALL_TYPES)
            await unified_ctx.send_error(embed)
            return False
        
        ball_type = ball_type.lower()
        
        # Attempt to catch the Pokemon
        pokemon = player.current_encounter
        success, reason = player.catch_pokemon(ball_type)
        self.player_db.save_player(user_id)
        
        # Handle different outcomes
        if reason == "already_attempted":
            embed = discord.Embed(
                title="❌ Already Attempted",
                description="You have already attempted to catch this Pokemon! Use `!encounter` or `/encounter` to find a new Pokemon.",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        elif reason == "no_pokeball":
            # Get the normalized ball type and proper name
            normalized_ball_type = player.inventory._normalize_ball_type(ball_type)
            ball_info = player.inventory.get_ball_info(normalized_ball_type)
            ball_name = ball_info.get("name", ball_type.title() + " Balls")
            
            embed = discord.Embed(
                title="❌ No Pokeballs",
                description=f"You don't have any {ball_name}s left!",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        
        # Create appropriate embed based on success
        if success:
            embed = PokemonEmbedUtils.create_catch_success_embed(
                pokemon=pokemon,
                user=unified_ctx.author,
                ball_type=ball_type,
                collection_id=len(player.pokemon_collection),
                total_caught=len(player.pokemon_collection)
            )
        else:
            embed = PokemonEmbedUtils.create_catch_failure_embed(
                pokemon=pokemon,
                ball_type=ball_type,
                remaining_pokeballs=player.inventory.get_pokeball_count(ball_type)
            )
        
        await unified_ctx.send(embed=embed)
        return success
    
    async def _wild_catch_logic(self, unified_ctx: UnifiedContext) -> bool:
        """
        Shared logic for both prefix and slash wild catch commands
        Returns True if successful, False if failed
        """
        # Check if in correct channel using ValidationUtils
        is_valid, error_message = ValidationUtils.validate_channel_permissions(
            unified_ctx.channel.name, 
            self.wild_spawn.spawn_data.spawn_channel
        )
        if not is_valid:
            embed = ErrorUtils.create_wrong_channel_embed(
                self.wild_spawn.spawn_data.spawn_channel, 
                "wild Pokemon catching"
            )
            await unified_ctx.send_error(embed)
            return False
        
        user_id = str(unified_ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Check if user has already attempted to catch this wild Pokemon
        if self.wild_spawn.has_user_attempted_catch(user_id):
            embed = ErrorUtils.create_already_attempted_embed("catch this wild Pokemon")
            await unified_ctx.send_error(embed)
            return False
        
        # Check if there's a current wild Pokemon
        if not self.wild_spawn.is_wild_pokemon_available():
            embed = ErrorUtils.create_no_pokemon_embed("catch")
            embed.description = "There's no wild Pokemon available to catch right now!\nWait for the next wild spawn (every 30 minutes)."
            await unified_ctx.send_error(embed)
            return False
        
        # Check if player has pokeballs
        if not player.inventory.has_pokeball("normal"):
            embed = ErrorUtils.create_insufficient_items_embed("Normal Pokeballs")
            embed.description = "You don't have any Normal Pokeballs left! Wild Pokemon can only be caught with Normal Pokeballs."
            await unified_ctx.send_error(embed)
            return False
        
        # Get the wild Pokemon
        wild_pokemon = self.wild_spawn.get_current_wild_pokemon()
        if not wild_pokemon:
            embed = discord.Embed(
                title="❌ No Wild Pokemon",
                description="There's no wild Pokemon available to catch right now!",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        
        # Attempt to catch
        success = player.catch_wild_pokemon(wild_pokemon)
        self.player_db.save_player(user_id)
        
        # Record the catch attempt
        self.wild_spawn.record_catch_attempt(user_id, unified_ctx.author.display_name, success)
        
        if success:
            # Mark as caught in wild spawn system
            self.wild_spawn.mark_pokemon_caught(user_id, unified_ctx.author.display_name)
            
            embed = discord.Embed(
                title="🎉 Pokemon Caught!",
                description=f"**Congratulations {unified_ctx.author.mention}!**\n\nYou successfully caught the wild **{wild_pokemon.name}**!\nIt's now part of your collection.",
                color=PokemonTypeUtils.get_type_color(wild_pokemon.types)
            )
            embed.set_image(url=wild_pokemon.image_url)
            embed.set_thumbnail(url=unified_ctx.author.display_avatar.url)
            
            # Add Pokemon info
            embed.add_field(name="Type", value=PokemonTypeUtils.format_types(wild_pokemon.types), inline=True)
            embed.add_field(name="Rarity", value=f"{wild_pokemon.rarity}", inline=True)
            embed.add_field(name="Collection ID", value=f"#{len(player.pokemon_collection)}", inline=True)
            
            # Simple achievement text
            total_caught = len(player.pokemon_collection)
            embed.add_field(name="🏆 Victory!", value=f"You caught the wild {wild_pokemon.name}!\nTotal Pokemon: {total_caught}", inline=False)
            
            embed.set_footer(text=f"Caught by {unified_ctx.author.display_name}")
            
        else:
            embed = discord.Embed(
                title="💨 Pokemon Escaped!",
                description=f"The wild **{wild_pokemon.name}** broke free! Other trainers can still try to catch it.",
                color=discord.Color.orange()
            )
            embed.set_thumbnail(url=wild_pokemon.sprite_url)
            embed.add_field(name="Still Available", value="The Pokemon is still available for others to catch!", inline=False)
        
        # Add remaining pokeball count
        remaining_balls = player.inventory.normal_pokeballs
        embed.add_field(name="Normal Pokeballs Remaining", value=f"{remaining_balls}", inline=True)
        
        await unified_ctx.send(embed=embed)
        return success
    
    async def _wild_status_logic(self, unified_ctx: UnifiedContext) -> bool:
        """
        Shared logic for wild status commands
        Returns True if successful, False if failed
        """
        status = self.wild_spawn.get_spawn_status()
        
        embed = discord.Embed(
            title="🌿 Wild Pokemon Status",
            color=discord.Color.green() if status["has_wild_pokemon"] else discord.Color.red()
        )
        
        if status["has_wild_pokemon"]:
            wild_pokemon = self.wild_spawn.get_current_wild_pokemon()
            if wild_pokemon:
                embed.description = f"**A wild {wild_pokemon.name} is currently available!**"
                embed.add_field(name="Location", value=f"#{status['spawn_channel']} channel", inline=True)
                embed.add_field(name="Type", value=wild_pokemon.types[0] if wild_pokemon.types else "Unknown", inline=True)
                embed.add_field(name="Rarity", value=wild_pokemon.rarity, inline=True)
                embed.set_thumbnail(url=wild_pokemon.sprite_url)
        else:
            embed.description = "No wild Pokemon currently available."
            embed.add_field(name="Spawn Channel", value=f"#{status['spawn_channel']}", inline=True)
            
        if status["last_spawn"]:
            try:
                last_spawn = datetime.fromisoformat(status["last_spawn"])
                embed.add_field(name="Last Spawn", value=f"<t:{int(last_spawn.timestamp())}:R>", inline=True)
            except ValueError:
                embed.add_field(name="Last Spawn", value="Unknown", inline=True)
        
        await unified_ctx.send(embed=embed)
        return True
    
    # ========== LEGACY PREFIX COMMANDS ==========
    
    async def encounter_pokemon(self, ctx) -> bool:
        """Encounter a wild Pokemon (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._encounter_pokemon_logic(unified_ctx)
    
    async def catch_pokemon(self, ctx, ball_type: str = "normal") -> bool:
        """Attempt to catch the currently encountered Pokemon (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._catch_pokemon_logic(unified_ctx, ball_type)
    
    async def wild_catch(self, ctx) -> bool:
        """Attempt to catch the current wild Pokemon in the pokemon channel (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._wild_catch_logic(unified_ctx)
    
    async def wild_status(self, ctx) -> bool:
        """Check the status of wild Pokemon spawning (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self._wild_status_logic(unified_ctx)