"""
Validation Utilities
Helper functions for validating Pokemon commands and data.
"""

import discord
from typing import Optional, Tuple, List
from datetime import datetime, timedelta

from ..models.pokemon_model import PokemonData


class ValidationUtils:
    """Utilities for validating Pokemon command inputs and states"""
    
    VALID_BALL_TYPES = ["normal", "master"]
    
    @staticmethod
    def validate_ball_type(ball_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if ball type is valid
        Returns (is_valid, error_message)
        """
        if not ball_type:
            return False, "Ball type cannot be empty"
        
        ball_type = ball_type.lower().strip()
        if ball_type not in ValidationUtils.VALID_BALL_TYPES:
            valid_types = ", ".join(ValidationUtils.VALID_BALL_TYPES)
            return False, f"Invalid ball type. Valid options: {valid_types}"
        
        return True, None
    
    @staticmethod
    def validate_channel_permissions(channel_name: str, required_channel: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if user is in the correct channel
        Returns (is_valid, error_message)
        """
        if channel_name != required_channel:
            return False, f"This command can only be used in #{required_channel}"
        
        return True, None
    
    @staticmethod
    def validate_player_cooldown(last_encounter: Optional[str], cooldown_minutes: int = 5) -> Tuple[bool, Optional[str]]:
        """
        Validate if player can perform an action based on cooldown
        Returns (can_perform, time_remaining_message)
        """
        if not last_encounter:
            return True, None
        
        try:
            last_time = datetime.fromisoformat(last_encounter)
            time_diff = datetime.now() - last_time
            cooldown_time = timedelta(minutes=cooldown_minutes)
            
            if time_diff < cooldown_time:
                remaining = cooldown_time - time_diff
                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)
                
                if minutes > 0:
                    time_str = f"{minutes}m {seconds}s"
                else:
                    time_str = f"{seconds}s"
                
                return False, f"Cooldown active. Please wait {time_str}"
            
        except ValueError:
            # If date parsing fails, allow the action
            return True, None
        
        return True, None
    
    @staticmethod
    def validate_pokemon_data(pokemon: Optional[PokemonData]) -> Tuple[bool, Optional[str]]:
        """
        Validate if Pokemon data is complete and valid
        Returns (is_valid, error_message)
        """
        if not pokemon:
            return False, "No Pokemon data provided"
        
        required_fields = ['name', 'types', 'rarity', 'catch_rate']
        for field in required_fields:
            if not hasattr(pokemon, field) or getattr(pokemon, field) is None:
                return False, f"Pokemon missing required field: {field}"
        
        if not pokemon.types or len(pokemon.types) == 0:
            return False, "Pokemon must have at least one type"
        
        if not 0 <= pokemon.catch_rate <= 1:
            return False, "Pokemon catch rate must be between 0 and 1"
        
        return True, None


class ErrorUtils:
    """Utilities for creating standardized error embeds"""
    
    @staticmethod
    def create_cooldown_embed(remaining_time: str, command_name: str = "command") -> discord.Embed:
        """Create standardized cooldown error embed"""
        embed = discord.Embed(
            title="⏰ Cooldown Active",
            description=f"You need to wait **{remaining_time}** before using {command_name} again!",
            color=discord.Color.orange()
        )
        embed.add_field(name="💡 Tip", value="Cooldowns prevent spam and make the game more balanced!", inline=False)
        return embed
    
    @staticmethod
    def create_no_pokemon_embed(action: str = "perform this action") -> discord.Embed:
        """Create standardized 'no Pokemon' error embed"""
        embed = discord.Embed(
            title="❌ No Pokemon Available",
            description=f"You need to have a Pokemon to {action}!",
            color=discord.Color.red()
        )
        embed.add_field(name="🌿 Get Started", value="Use `!encounter` or `/encounter` to find wild Pokemon!", inline=False)
        return embed
    
    @staticmethod
    def create_already_attempted_embed(action: str = "catch this Pokemon") -> discord.Embed:
        """Create standardized 'already attempted' error embed"""
        embed = discord.Embed(
            title="❌ Already Attempted",
            description=f"You have already attempted to {action}!",
            color=discord.Color.red()
        )
        embed.add_field(name="🔄 Next Steps", value="Use `!encounter` to find a new Pokemon!", inline=False)
        return embed
    
    @staticmethod
    def create_insufficient_items_embed(item_name: str, required: int = 1) -> discord.Embed:
        """Create standardized 'insufficient items' error embed"""
        embed = discord.Embed(
            title="❌ Insufficient Items",
            description=f"You don't have enough {item_name}!",
            color=discord.Color.red()
        )
        if required > 1:
            embed.add_field(name="Required", value=f"{required} {item_name}", inline=True)
        embed.add_field(name="💰 Get More", value="Complete daily quests or participate in events!", inline=False)
        return embed
    
    @staticmethod
    def create_wrong_channel_embed(required_channel: str, command_name: str = "this command") -> discord.Embed:
        """Create standardized 'wrong channel' error embed"""
        embed = discord.Embed(
            title="❌ Wrong Channel",
            description=f"{command_name.title()} can only be used in the #{required_channel} channel!",
            color=discord.Color.red()
        )
        embed.add_field(name="🏠 Correct Channel", value=f"#{required_channel}", inline=False)
        return embed
    
    @staticmethod
    def create_invalid_input_embed(input_name: str, valid_options: List[str]) -> discord.Embed:
        """Create standardized 'invalid input' error embed"""
        embed = discord.Embed(
            title="❌ Invalid Input",
            description=f"Invalid {input_name} provided!",
            color=discord.Color.red()
        )
        if valid_options:
            options_text = ", ".join([f"`{option}`" for option in valid_options])
            embed.add_field(name="Valid Options", value=options_text, inline=False)
        return embed
    
    @staticmethod
    def create_system_error_embed(error_message: str = "An unexpected error occurred") -> discord.Embed:
        """Create standardized system error embed"""
        embed = discord.Embed(
            title="🚫 System Error",
            description=error_message,
            color=discord.Color.dark_red()
        )
        embed.add_field(name="🔧 Action Required", value="Please try again later or contact an administrator if the problem persists.", inline=False)
        embed.set_footer(text="Error reported automatically")
        return embed