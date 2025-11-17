"""
Basic Pokémon Commands
Handles core Pokémon gameplay commands like encounters and catching.
Clean, optimized version with shared logic and no duplication.
"""

from datetime import datetime

import discord

from config import Config
from ..managers import PokemonDatabaseManager, PlayerDataManager, WildSpawnManager
from ..models import CaughtPokemon
from ..utils import PokemonEmbedUtils, PokemonTypeUtils, ValidationUtils, ErrorUtils
from ..utils.interaction_utils import UnifiedContext, create_unified_context
from ..utils.mongo_manager import MongoManager


class BasicPokemonCommands:
    """Contains basic Pokémon gameplay commands with shared logic architecture"""
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager, wild_spawn: WildSpawnManager, mongo_db: MongoManager=None):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
        self.wild_spawn = wild_spawn
        self.mongo_db = mongo_db
        
        # Setup logging
        self.logger = Config.setup_logging()
    
    def _log_catch_attempt(self, user, catch_details):
        """Log detailed catch attempt information"""
        details = catch_details
        # Sanitize display name to ASCII-only characters to avoid encoding issues
        safe_display_name = user.display_name.encode('ascii', 'replace').decode('ascii')
        user_info = f"{safe_display_name} ({user.id})"
        
        # Log basic catch attempt
        self.logger.info(f"CATCH ATTEMPT - User: {user_info}")
        self.logger.info(f"  Pokemon: {details['pokemon_name']}")
        self.logger.info(f"  Ball Used: {details['ball_name']} ({details['ball_type']})")
        self.logger.info(f"  Original Catch Rate: {details['original_catch_rate']:.1%}")
        
        # Log ball effect
        if details['ball_modifier'] == float('inf'):
            self.logger.info(f"  Ball Effect: Master Ball (Guaranteed Capture)")
            self.logger.info(f"  Final Catch Rate: 100.0%")
        else:
            self.logger.info(f"  Ball Modifier: {details['ball_modifier']}x")
            self.logger.info(f"  Final Catch Rate: {details['final_catch_rate']:.1%}")
        
        # Log outcome
        self.logger.info(f"  Random Roll: {details['random_roll']:.3f}")
        
        if details['success']:
            self.logger.info(f"  RESULT: [SUCCESS] CAUGHT! ({details['random_roll']:.3f} <= {details['final_catch_rate']:.3f})")
        else:
            self.logger.info(f"  RESULT: [FAILED] ESCAPED ({details['random_roll']:.3f} > {details['final_catch_rate']:.3f})")
        
        # Log performance comparison
        original_success = details['random_roll'] <= details['original_catch_rate']
        if details['ball_modifier'] != 1.0 and details['ball_modifier'] != float('inf'):
            if details['success'] and not original_success:
                self.logger.info(f"  BALL IMPACT: [HELPFUL] Ball helped secure the catch!")
            elif not details['success'] and original_success:
                self.logger.info(f"  BALL IMPACT: [NOTE] Would have caught with Poke Ball") 
            elif details['success'] and original_success:
                self.logger.info(f"  BALL IMPACT: [BONUS] Would have caught anyway, but ball improved odds")
            else:
                self.logger.info(f"  BALL IMPACT: [INSUFFICIENT] Ball wasn't enough to secure catch")
        
        self.logger.info("---")
    
    # ========== SHARED LOGIC FUNCTIONS ==========
    
    async def encounter_pokemon_logic(self, unified_ctx: UnifiedContext) -> bool:
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
        
        # Check if player already owns this Pokemon
        already_owned = self.mongo_db.has_pokemon_by_name(user_id, pokemon.name)
        
        # Create and send embed
        embed = PokemonEmbedUtils.create_encounter_embed(
            pokemon=pokemon,
            user=unified_ctx.author,
            already_owned=already_owned
        )
        
        await unified_ctx.send(embed=embed)
        return True
    
    async def catch_pokemon_logic(self, unified_ctx: UnifiedContext, ball_type: str = "normal") -> bool:
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
        
        # Attempt to catch the Pokémon
        pokemon = player.current_encounter
        success, reason, catch_details = player.catch_pokemon(ball_type)
        
        # Store the Pokémon in MongoDB only (no longer storing in JSON)
        if success:
            # Store Pokémon data as individual fields (flattened structure)
            pokemon_dict = {}
            
            # Get Pokemon data
            if hasattr(pokemon, "to_dict"):
                pokemon_data = pokemon.to_dict()
            else:
                pokemon_data = pokemon.__dict__
                
            # Add all Pokémon data fields directly to the root level
            pokemon_dict.update(pokemon_data)
            
            # Remove catch_rate as it's not needed in storage
            if "catch_rate" in pokemon_dict:
                del pokemon_dict["catch_rate"]
            last_pokemon = self.mongo_db.get_last_pokemon(user_id)
            if last_pokemon:
                pokemon_id = last_pokemon["id"] + 1
            else:
                pokemon_id = 1
            pokemon_dict["id"] = pokemon_id
            
            # Add metadata
            pokemon_dict["owner_id"] = user_id
            pokemon_dict["caught_date"] = datetime.now().isoformat()
            pokemon_dict["caught_with"] = ball_type
            pokemon_dict["caught_from"] = "encounter"
            
            self.mongo_db.add_pokemon(pokemon_dict)
            player.pokemon_collection.append(pokemon)  # Update in-memory collection for immediate feedback
            
        # Still save player data (but without the Pokemon)
        self.player_db.save_player(user_id)
        
        # Log comprehensive catch information
        if catch_details:
            self._log_catch_attempt(unified_ctx.author, catch_details)
        
        # Handle different outcomes
        if reason == "already_attempted":
            embed = discord.Embed(
                title="❌ Already Attempted",
                description="You have already attempted to catch this Pokemon! Use `!encounter` or `/encounter` to find a new Pokemon.",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        elif reason == "catch_limit_reached":
            remaining_catches = player.get_remaining_catches()
            cooldown_time = player.get_catch_cooldown_remaining()
            
            embed = discord.Embed(
                title="🕒 Catch Limit Reached",
                description=f"You've reached your hourly catch limit (3 Pokemon per hour).\n\n"
                           f"**Remaining catches:** {remaining_catches}/3\n"
                           f"**Next catch available in:** {cooldown_time if cooldown_time else 'Soon'}",
                color=discord.Color.orange()
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
            )
        else:
            embed = PokemonEmbedUtils.create_catch_failure_embed(
                pokemon=pokemon,
                ball_type=ball_type,
                remaining_pokeballs=player.inventory.get_pokeball_count(ball_type)
            )
        
        await unified_ctx.send(embed=embed)
        return success
    
    async def wild_catch_logic(self, unified_ctx: UnifiedContext) -> bool:
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
        
        # Check if user has already attempted to catch this wild Pokémon
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
        if not player.inventory.has_pokeball("poke"):  # Updated to use poke
            embed = ErrorUtils.create_insufficient_items_embed("Poké Balls")
            embed.description = "You don't have any Poké Balls left! Wild Pokemon can only be caught with Poké Balls."
            await unified_ctx.send_error(embed)
            return False
        
        # Check catch limit (5 catches per hour)
        if not player.can_catch():
            remaining_catches = player.get_remaining_catches()
            cooldown_time = player.get_catch_cooldown_remaining()
            
            embed = discord.Embed(
                title="🕒 Catch Limit Reached",
                description=f"You've reached your hourly catch limit (3 Pokemon per hour).\n\n"
                           f"**Remaining catches:** {remaining_catches}/3\n"
                           f"**Next catch available in:** {cooldown_time if cooldown_time else 'Soon'}",
                color=discord.Color.orange()
            )
            await unified_ctx.send_error(embed)
            return False
        
        # Get the wild Pokémon
        wild_pokemon = self.wild_spawn.get_current_wild_pokemon()
        if not wild_pokemon:
            embed = discord.Embed(
                title="❌ No Wild Pokemon",
                description="There's no wild Pokemon available to catch right now!",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        
        ball_type = "poke"
        success = player.catch_wild_pokemon(wild_pokemon)
        self.player_db.save_player(user_id)
        
        # Record the catch attempt
        self.wild_spawn.record_catch_attempt(user_id, unified_ctx.author.display_name, success)
        
        if success:
            # Mark as caught in wild spawn system
            self.wild_spawn.mark_pokemon_caught(user_id, unified_ctx.author.display_name)
            
            # Store Pokémon in MongoDB
            pokemon_dict = {}
            
            # Get Pokemon data
            if hasattr(wild_pokemon, "to_dict"):
                pokemon_data = wild_pokemon.to_dict()
            else:
                pokemon_data = wild_pokemon.__dict__
                
            # Add all Pokémon data fields directly to the root level
            pokemon_dict.update(pokemon_data)
            
            # Remove catch_rate as it's not needed in storage
            if "catch_rate" in pokemon_dict:
                del pokemon_dict["catch_rate"]


            last_pokemon = self.mongo_db.get_last_pokemon(user_id)
            if last_pokemon:
                pokemon_id = last_pokemon["id"] + 1
            else:
                pokemon_id = 1
            pokemon_dict["id"] = pokemon_id
            pokemon_dict["id"] = pokemon_id
            
            # Add metadata
            pokemon_dict["owner_id"] = user_id
            pokemon_dict["caught_date"] = datetime.now().isoformat()
            pokemon_dict["caught_with"] = ball_type
            pokemon_dict["caught_from"] = "wild_spawn"
            
            self.mongo_db.add_pokemon(pokemon_dict)
            player.pokemon_collection.append(CaughtPokemon.from_dict(pokemon_dict))  # Update in-memory collection for immediate feedback
            
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
        remaining_balls = player.inventory.poke_balls
        embed.add_field(name="Poké Balls Remaining", value=f"{remaining_balls}", inline=True)
        
        await unified_ctx.send(embed=embed)
        return success
    
    async def wild_status_logic(self, unified_ctx: UnifiedContext) -> bool:
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
    
    async def daily_claim_logic(self, unified_ctx: UnifiedContext) -> bool:
        """
        Shared logic for both prefix and slash daily claim commands
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Check if daily claim is available
        if not player.can_claim_daily_bonus():
            cooldown_time = player.get_daily_claim_cooldown_remaining()
            
            embed = discord.Embed(
                title="🕒 Daily Bonus Already Claimed",
                description="You've already claimed your daily bonus!\n\n"
                           f"**Next claim available in:** {cooldown_time if cooldown_time else 'Soon'}",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="💰 Current Balance", 
                value=f"{player.pokecoins:,} PokéCoins", 
                inline=True
            )
            await unified_ctx.send_error(embed)
            return False
        
        # Claim daily bonus
        success, coins_received = player.claim_daily_bonus()
        self.player_db.save_player(user_id)
        
        if success:
            embed = discord.Embed(
                title="🎁 Daily Bonus Claimed!",
                description=f"**Congratulations {unified_ctx.author.mention}!**\n\n"
                           f"You've claimed your daily bonus of **{coins_received:,} PokéCoins**!",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="💰 Balance Update",
                value=f"**Received:** +{coins_received:,} PokéCoins\n"
                      f"**New Balance:** {player.pokecoins:,} PokéCoins",
                inline=False
            )
            
            embed.add_field(
                name="🔄 Next Claim",
                value="Available in 24 hours",
                inline=True
            )
            
            embed.add_field(
                name="💡 Tip",
                value="Use PokéCoins to buy items and upgrades!",
                inline=True
            )
            
            embed.set_thumbnail(url=unified_ctx.author.display_avatar.url)
            embed.set_footer(text=f"Daily bonus claimed by {unified_ctx.author.display_name}")
            
            await unified_ctx.send(embed=embed)
            return True
        
        # Should not reach here, but handle just in case
        embed = discord.Embed(
            title="❌ Claim Failed",
            description="Failed to claim daily bonus. Please try again later.",
            color=discord.Color.red()
        )
        await unified_ctx.send_error(embed)
        return False
    
    async def check_pokemon_logic(self, unified_ctx: UnifiedContext, pokemon_name: str) -> bool:
        """
        Shared logic for checking if player owns a specific Pokémon
        Returns True if successful, False if failed
        """
        user_id = str(unified_ctx.author.id)
        
        # Capitalize pokemon name properly
        pokemon_name_formatted = pokemon_name.strip().title()
        
        # Check if the pokemon exists in the database
        pokemon_data = self.pokemon_db.get_pokemon_by_name(pokemon_name_formatted)
        if not pokemon_data:
            embed = discord.Embed(
                title="❌ Pokémon Not Found",
                description=f"**{pokemon_name_formatted}** doesn't exist in the Pokémon database.\n\nPlease check the spelling and try again.",
                color=discord.Color.red()
            )
            await unified_ctx.send_error(embed)
            return False
        
        # Check if player owns this pokemon
        has_pokemon = self.mongo_db.has_pokemon_by_name(user_id, pokemon_data.name)
        
        # Count how many of this pokemon the player has
        owned_count = self.mongo_db.caught_pokemon.count_documents({
            "owner_id": user_id,
            "name": pokemon_data.name
        })
        
        # Create embed based on ownership
        if has_pokemon:
            embed = discord.Embed(
                title="✅ Pokémon Found in Collection!",
                description=f"**{unified_ctx.author.mention}** owns **{pokemon_data.name}**!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Owned Count",
                value=f"You have **{owned_count}** {pokemon_data.name}{'s' if owned_count > 1 else ''} in your collection",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ Pokémon Not in Collection",
                description=f"**{unified_ctx.author.mention}** doesn't own **{pokemon_data.name}** yet.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="How to Get",
                value=f"Use `!encounter` or `!wild` to find and catch {pokemon_data.name}!",
                inline=False
            )
        
        # Add Pokemon info
        type_text = PokemonTypeUtils.format_types(pokemon_data.types)
        embed.add_field(name="Type", value=type_text, inline=True)
        embed.add_field(name="Rarity", value=pokemon_data.rarity, inline=True)
        embed.add_field(name="Pokedex #", value=f"#{pokemon_data.id}", inline=True)
        
        embed.set_thumbnail(url=pokemon_data.sprite_url)
        embed.set_footer(text=f"Check requested by {unified_ctx.author.display_name}")
        
        await unified_ctx.send(embed=embed)
        return True
    
    # ========== LEGACY PREFIX COMMANDS ==========
    
    async def encounter_pokemon(self, ctx) -> bool:
        """Encounter a wild Pokémon (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.encounter_pokemon_logic(unified_ctx)
    
    async def catch_pokemon(self, ctx, ball_type: str = "normal") -> bool:
        """Attempt to catch the currently encountered Pokémon (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.catch_pokemon_logic(unified_ctx, ball_type)
    
    async def wild_catch(self, ctx) -> bool:
        """Attempt to catch the current wild Pokémon in the Pokémon channel (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.wild_catch_logic(unified_ctx)
    
    async def wild_status(self, ctx) -> bool:
        """Check the status of wild Pokémon spawning (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.wild_status_logic(unified_ctx)
    
    async def daily_claim(self, ctx) -> bool:
        """Claim daily PokéCoin bonus (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.daily_claim_logic(unified_ctx)
    
    async def check_pokemon(self, ctx, *, pokemon_name: str) -> bool:
        """Check if you own a specific Pokémon (legacy prefix command)"""
        unified_ctx = create_unified_context(ctx)
        return await self.check_pokemon_logic(unified_ctx, pokemon_name)