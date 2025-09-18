"""
Wild Spawn Manager
Handles wild Pokemon spawning system including background tasks and spawn data management.
"""

import json
import os
import discord
from discord.ext import tasks
from typing import Optional, Dict, Any
from datetime import datetime
from ..models.pokemon_model import PokemonData


class WildSpawnData:
    """Manages wild spawn data structure"""
    
    def __init__(self, data: Dict[str, Any] = None):
        if data is None:
            data = {}
        
        self.last_spawn = data.get("last_spawn")
        self.current_wild = data.get("current_wild")
        self.spawn_channel = data.get("spawn_channel", "pokemon")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "last_spawn": self.last_spawn,
            "current_wild": self.current_wild,
            "spawn_channel": self.spawn_channel
        }


class WildSpawnManager:
    """Manages wild Pokemon spawning operations"""
    
    def __init__(self, spawn_data_file: str = "wild_spawn_data.json"):
        self.spawn_data_file = spawn_data_file
        self.spawn_data: WildSpawnData = self.load_spawn_data()
        self.spawn_task = None
        self._spawn_task_started = False
        self._spawn_error_count = 0
    
    def load_spawn_data(self) -> WildSpawnData:
        """Load wild spawn data from JSON file"""
        if os.path.exists(self.spawn_data_file):
            try:
                with open(self.spawn_data_file, 'r') as f:
                    data = json.load(f)
                return WildSpawnData(data)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        # Return default data if file doesn't exist or has errors
        return WildSpawnData()
    
    def save_spawn_data(self) -> bool:
        """Save wild spawn data to JSON file"""
        try:
            with open(self.spawn_data_file, 'w') as f:
                json.dump(self.spawn_data.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving wild spawn data: {e}")
            return False
    
    def set_current_wild_pokemon(self, pokemon: PokemonData, channel_id: int):
        """Set the current wild Pokemon"""
        self.spawn_data.current_wild = {
            "pokemon": pokemon.to_dict(),
            "spawn_time": datetime.now().isoformat(),
            "caught_by": None,
            "channel_id": channel_id,
            "attempted_catches": {}  # Fresh attempts for new Pokemon spawn
        }
        self.spawn_data.last_spawn = datetime.now().isoformat()
        self.save_spawn_data()
    
    def mark_pokemon_caught(self, user_id: str, username: str):
        """Mark the current wild Pokemon as caught"""
        if self.spawn_data.current_wild:
            self.spawn_data.current_wild["caught_by"] = {
                "user_id": user_id,
                "username": username,
                "caught_time": datetime.now().isoformat()
            }
            self.save_spawn_data()
    
    def has_user_attempted_catch(self, user_id: str) -> bool:
        """Check if user has already attempted to catch the current wild Pokemon"""
        if not self.spawn_data.current_wild:
            return False
        
        attempted_catches = self.spawn_data.current_wild.get("attempted_catches", {})
        return user_id in attempted_catches
    
    def record_catch_attempt(self, user_id: str, username: str, success: bool):
        """Record a catch attempt by a user"""
        if self.spawn_data.current_wild:
            if "attempted_catches" not in self.spawn_data.current_wild:
                self.spawn_data.current_wild["attempted_catches"] = {}
            
            self.spawn_data.current_wild["attempted_catches"][user_id] = {
                "username": username,
                "attempt_time": datetime.now().isoformat(),
                "success": success
            }
            self.save_spawn_data()
    
    def get_current_wild_pokemon(self) -> Optional[PokemonData]:
        """Get the current wild Pokemon if available"""
        if not self.spawn_data.current_wild or self.spawn_data.current_wild.get("caught_by"):
            return None
        
        pokemon_data = self.spawn_data.current_wild.get("pokemon")
        if pokemon_data:
            return PokemonData.from_dict(pokemon_data.get('id', 0), pokemon_data)
        
        return None
    
    def is_wild_pokemon_available(self) -> bool:
        """Check if there's a wild Pokemon available to catch"""
        return (self.spawn_data.current_wild is not None and 
                self.spawn_data.current_wild.get("caught_by") is None)
    
    def get_spawn_status(self) -> Dict[str, Any]:
        """Get current spawn status information"""
        status = {
            "has_wild_pokemon": self.is_wild_pokemon_available(),
            "spawn_channel": self.spawn_data.spawn_channel,
            "last_spawn": self.spawn_data.last_spawn
        }
        
        if self.spawn_data.current_wild:
            if self.spawn_data.current_wild.get("caught_by"):
                status["caught_by"] = self.spawn_data.current_wild["caught_by"]
            else:
                status["spawn_time"] = self.spawn_data.current_wild.get("spawn_time")
                pokemon_data = self.spawn_data.current_wild.get("pokemon")
                if pokemon_data:
                    status["pokemon_name"] = pokemon_data.get("name")
                    status["pokemon_rarity"] = pokemon_data.get("rarity")
        
        return status
    
    def start_spawn_task(self, bot, pokemon_database_manager):
        """Start the background task for wild Pokemon spawning"""
        from ..utils.pokemon_utils import PokemonEmbedUtils
        
        @tasks.loop(minutes=30)
        async def wild_spawn_loop():
            await self._spawn_wild_pokemon(bot, pokemon_database_manager)
        
        self.spawn_task = wild_spawn_loop
        self.spawn_task.start()
        self._spawn_task_started = True
    
    async def _spawn_wild_pokemon(self, bot, pokemon_database_manager):
        """Internal method to spawn a wild Pokemon"""
        try:
            # Find the pokemon channel
            channel = await self._find_spawn_channel(bot)
            if not channel:
                return
            
            # Get a common or uncommon Pokemon
            pokemon = pokemon_database_manager.get_common_uncommon_pokemon()
            if not pokemon:
                print("No common/uncommon Pokemon found for spawning!")
                return
            
            # Store the wild Pokemon data
            self.set_current_wild_pokemon(pokemon, channel.id)
            
            # Import embed utils here to avoid circular imports
            from ..utils.pokemon_utils import PokemonEmbedUtils
            
            # Create and send spawn embed
            embed = PokemonEmbedUtils.create_wild_spawn_embed(pokemon)
            await channel.send(embed=embed)
            
            # Reset error counter on successful spawn
            self._spawn_error_count = 0
            
        except Exception as e:
            print(f"Error in wild spawn: {e}")
    
    async def _find_spawn_channel(self, bot) -> Optional[discord.TextChannel]:
        """Find the designated spawn channel"""
        target_channel_name = self.spawn_data.spawn_channel
        
        print(f"Looking for channel named: '{target_channel_name}'")
        print(f"Bot is in {len(bot.guilds)} guild(s)")
        
        for guild in bot.guilds:
            print(f"Searching in guild: {guild.name}")
            
            # List all text channels for debugging
            text_channels = [ch.name for ch in guild.text_channels]
            print(f"Available text channels: {text_channels}")
            
            # Try to find the channel
            channel = discord.utils.get(guild.text_channels, name=target_channel_name)
            if channel:
                print(f"Found channel: {channel.name} (ID: {channel.id})")
                return channel
            else:
                # Try case-insensitive search
                for ch in guild.text_channels:
                    if ch.name.lower() == target_channel_name.lower():
                        print(f"Found channel with case-insensitive match: {ch.name} (ID: {ch.id})")
                        return ch
        
        # Handle channel not found
        self._spawn_error_count += 1
        
        # Log error every 10 attempts to avoid spam
        if self._spawn_error_count <= 3 or self._spawn_error_count % 10 == 0:
            print(f"Pokemon spawn channel '{target_channel_name}' not found in any guild! (Attempt {self._spawn_error_count})")
            if self._spawn_error_count <= 3:
                print("Please make sure:")
                print("1. The bot has access to the channel")
                print("2. The channel name is exactly 'pokemon' (lowercase)")
                print("3. The bot has 'View Channels' and 'Send Messages' permissions")
        
        return None
    
    async def force_spawn(self, bot, pokemon_database_manager) -> bool:
        """Manually trigger a wild Pokemon spawn"""
        try:
            await self._spawn_wild_pokemon(bot, pokemon_database_manager)
            return True
        except Exception as e:
            print(f"Error in forced spawn: {e}")
            return False
    
    def clear_current_wild(self):
        """Clear the current wild Pokemon (admin function)"""
        self.spawn_data.current_wild = None
        self.save_spawn_data()
    
    def set_spawn_channel(self, channel_name: str):
        """Set the spawn channel name"""
        self.spawn_data.spawn_channel = channel_name
        self.save_spawn_data()
    
    def stop_spawn_task(self):
        """Stop the spawning task"""
        if self.spawn_task:
            self.spawn_task.stop()
            self._spawn_task_started = False
    
    @property
    def is_task_running(self) -> bool:
        """Check if the spawn task is running"""
        return self._spawn_task_started and self.spawn_task is not None