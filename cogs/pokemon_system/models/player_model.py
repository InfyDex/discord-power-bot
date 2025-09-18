"""
Player Data Models
Defines data structures for player entities and their game data.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .pokemon_model import CaughtPokemon, PokemonData


class PlayerInventory:
    """Manages player's pokeball inventory"""
    
    # Poké Ball configurations with catch rate modifiers and icons
    POKEBALL_CONFIG = {
        "poke": {
            "name": "Poké Ball",
            "catch_rate_modifier": 1.0,
            "icon": "https://archives.bulbagarden.net/media/upload/b/b3/Pok%C3%A9_Ball_ZA_Art.png",
            "default_count": 5
        },
        "great": {
            "name": "Great Ball", 
            "catch_rate_modifier": 1.5,
            "icon": "https://archives.bulbagarden.net/media/upload/5/54/Bag_Great_Ball_SV_Sprite.png",
            "default_count": 0
        },
        "ultra": {
            "name": "Ultra Ball",
            "catch_rate_modifier": 2.0, 
            "icon": "https://archives.bulbagarden.net/media/upload/5/55/Bag_Ultra_Ball_SV_Sprite.png",
            "default_count": 0
        },
        "master": {
            "name": "Master Ball",
            "catch_rate_modifier": float('inf'),  # Guaranteed capture
            "icon": "https://archives.bulbagarden.net/media/upload/a/a6/Bag_Master_Ball_SV_Sprite.png", 
            "default_count": 0
        }
    }
    
    def __init__(self, inventory_data: Dict[str, int] = None):
        if inventory_data is None:
            inventory_data = {}
        
        # Initialize ball counts (backward compatibility + new balls)
        self.poke_balls = inventory_data.get("poke", inventory_data.get("normal", 5))  # Backward compatibility
        self.great_balls = inventory_data.get("great", 0)
        self.ultra_balls = inventory_data.get("ultra", 0)
        self.master_balls = inventory_data.get("master", 0)
        
        # Legacy support
        self.normal_pokeballs = self.poke_balls  # Backward compatibility
    
    def has_pokeball(self, ball_type: str) -> bool:
        """Check if player has pokeballs of specified type"""
        # Normalize ball type names
        ball_type = self._normalize_ball_type(ball_type)
        
        if ball_type == "poke":
            return self.poke_balls > 0
        elif ball_type == "great":
            return self.great_balls > 0
        elif ball_type == "ultra":
            return self.ultra_balls > 0
        elif ball_type == "master":
            return self.master_balls > 0
        return False
    
    def use_pokeball(self, ball_type: str) -> bool:
        """Use a pokeball, returns True if successful"""
        ball_type = self._normalize_ball_type(ball_type)
        
        if not self.has_pokeball(ball_type):
            return False
        
        if ball_type == "poke":
            self.poke_balls -= 1
            self.normal_pokeballs = self.poke_balls  # Keep legacy sync
        elif ball_type == "great":
            self.great_balls -= 1
        elif ball_type == "ultra":
            self.ultra_balls -= 1
        elif ball_type == "master":
            self.master_balls -= 1
        else:
            return False
        
        return True
    
    def add_pokeballs(self, ball_type: str, count: int):
        """Add pokeballs to inventory"""
        ball_type = self._normalize_ball_type(ball_type)
        
        if ball_type == "poke":
            self.poke_balls += count
            self.normal_pokeballs = self.poke_balls  # Keep legacy sync
        elif ball_type == "great":
            self.great_balls += count
        elif ball_type == "ultra":
            self.ultra_balls += count
        elif ball_type == "master":
            self.master_balls += count
    
    def get_pokeball_count(self, ball_type: str) -> int:
        """Get the count of a specific pokeball type"""
        ball_type = self._normalize_ball_type(ball_type)
        
        if ball_type == "poke":
            return self.poke_balls
        elif ball_type == "great":
            return self.great_balls
        elif ball_type == "ultra":
            return self.ultra_balls
        elif ball_type == "master":
            return self.master_balls
        return 0
    
    def _normalize_ball_type(self, ball_type: str) -> str:
        """Normalize ball type names for backward compatibility"""
        ball_type = ball_type.lower().strip()
        
        # Handle legacy names
        if ball_type in ["normal", "pokeball", "poke_ball"]:
            return "poke"
        elif ball_type in ["great_ball"]:
            return "great"
        elif ball_type in ["ultra_ball"]:
            return "ultra"
        elif ball_type in ["master_ball"]:
            return "master"
        
        return ball_type
    
    def get_ball_info(self, ball_type: str) -> Dict[str, Any]:
        """Get ball configuration info"""
        ball_type = self._normalize_ball_type(ball_type)
        return self.POKEBALL_CONFIG.get(ball_type, {})
    
    def get_all_balls(self) -> Dict[str, Dict[str, Any]]:
        """Get all ball types with their counts and info"""
        result = {}
        for ball_type, config in self.POKEBALL_CONFIG.items():
            result[ball_type] = {
                **config,
                "count": self.get_pokeball_count(ball_type)
            }
        return result
    
    def to_dict(self) -> Dict[str, int]:
        """Convert inventory to dictionary format"""
        return {
            "poke": self.poke_balls,
            "great": self.great_balls,
            "ultra": self.ultra_balls,
            "master": self.master_balls,
            # Legacy compatibility
            "normal": self.poke_balls
        }


class PlayerStats:
    """Tracks player statistics"""
    
    def __init__(self, stats_data: Dict[str, Any] = None):
        if stats_data is None:
            stats_data = {}
        
        self.total_caught = stats_data.get("total_caught", 0)
        self.total_encounters = stats_data.get("total_encounters", 0)
        self.join_date = stats_data.get("join_date", datetime.now().isoformat())
    
    def add_encounter(self):
        """Record a new encounter"""
        self.total_encounters += 1
    
    def add_catch(self):
        """Record a successful catch"""
        self.total_caught += 1
    
    def get_catch_rate(self) -> float:
        """Calculate player's catch rate percentage"""
        if self.total_encounters == 0:
            return 0.0
        return (self.total_caught / self.total_encounters) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary format"""
        return {
            "total_caught": self.total_caught,
            "total_encounters": self.total_encounters,
            "join_date": self.join_date
        }


class PlayerData:
    """Complete player data management"""
    
    def __init__(self, user_id: str, data: Dict[str, Any] = None):
        self.user_id = user_id
        
        if data is None:
            data = self._get_default_data()
        
        self.pokemon_collection: List[CaughtPokemon] = []
        self.inventory = PlayerInventory(data.get("pokeballs", {}))
        self.stats = PlayerStats(data.get("stats", {}))
        self.last_encounter = data.get("last_encounter")
        self.current_encounter: Optional[PokemonData] = None
        self.encounter_catch_attempted: bool = False  # Track if user attempted to catch current encounter
        
        # Catch history for hourly limits (5 catches per hour)
        self.catch_history: List[str] = data.get("catch_history", [])
        
        # Currency system (PokéCoins)
        self.pokecoins: int = data.get("pokecoins", 0)
        self.last_daily_claim: Optional[str] = data.get("last_daily_claim")
        
        # Load caught Pokemon
        if "pokemon" in data:
            for pokemon_data in data["pokemon"]:
                caught_pokemon = CaughtPokemon.from_dict(pokemon_data)
                self.pokemon_collection.append(caught_pokemon)
        
        # Load current encounter if exists
        if "current_encounter" in data and data["current_encounter"]:
            encounter_data = data["current_encounter"]
            self.current_encounter = PokemonData.from_dict(0, encounter_data)
            self.encounter_catch_attempted = data.get("encounter_catch_attempted", False)
        else:
            self.encounter_catch_attempted = False
    
    def _get_default_data(self) -> Dict[str, Any]:
        """Get default player data for new players"""
        return {
            "pokemon": [],
            "pokeballs": {
                "poke": 5,
                "great": 0,
                "ultra": 0, 
                "master": 0,
                # Legacy compatibility
                "normal": 5
            },
            "last_encounter": None,
            "catch_history": [],
            "pokecoins": 100,  # New players start with 100 PokéCoins
            "last_daily_claim": None,
            "stats": {
                "total_caught": 0,
                "total_encounters": 0,
                "join_date": datetime.now().isoformat()
            }
        }
    
    def can_encounter(self, cooldown_minutes: int = 5) -> bool:
        """Check if player can have a new encounter"""
        if not self.last_encounter:
            return True
        
        try:
            last_time = datetime.fromisoformat(self.last_encounter)
        except (ValueError, TypeError):
            # If last_encounter has invalid format, allow encounter
            return True
        
        # Validate cooldown_minutes for reasonable values (1-60 minutes)
        cooldown_minutes = max(1, min(cooldown_minutes, 60))
        cooldown = timedelta(minutes=cooldown_minutes)
        
        return datetime.now() - last_time >= cooldown
    
    def get_cooldown_remaining_seconds(self, cooldown_minutes: int = 5) -> int:
        """Get remaining cooldown time in seconds (for backward compatibility)"""
        if not self.last_encounter:
            return 0
        
        try:
            last_time = datetime.fromisoformat(self.last_encounter)
        except (ValueError, TypeError):
            # If last_encounter has invalid format, treat as no cooldown
            return 0
        
        # Validate cooldown_minutes for reasonable values (1-60 minutes)
        cooldown_minutes = max(1, min(cooldown_minutes, 60))
        
        next_encounter = last_time + timedelta(minutes=cooldown_minutes)
        time_left = next_encounter - datetime.now()
        
        # Use round() instead of int() to handle floating point precision better
        return max(0, round(time_left.total_seconds()))
    
    def get_cooldown_remaining_formatted(self, cooldown_minutes: int = 5) -> str:
        """Get remaining cooldown time in a user-friendly format"""
        if not self.last_encounter:
            return None
        
        try:
            last_time = datetime.fromisoformat(self.last_encounter)
        except (ValueError, TypeError):
            # If last_encounter has invalid format, treat as no cooldown
            return None
        
        # Validate cooldown_minutes for reasonable values (1-60 minutes)
        cooldown_minutes = max(1, min(cooldown_minutes, 60))
        
        next_encounter = last_time + timedelta(minutes=cooldown_minutes)
        time_left = next_encounter - datetime.now()
        
        total_seconds = max(0, round(time_left.total_seconds()))
        
        # If cooldown is expired, return None (no cooldown message needed)
        if total_seconds <= 0:
            return None
        
        # If less than 1 second remaining, show 1s for better UX
        if total_seconds < 1:
            return "1s"
        
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        if minutes > 0:
            if seconds > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{minutes}m"
        else:
            return f"{seconds}s"
    
    def can_catch(self, max_catches_per_hour: int = 5) -> bool:
        """Check if player can catch Pokemon (5 catches per hour limit)"""
        self._cleanup_old_catches()
        return len(self.catch_history) < max_catches_per_hour
    
    def get_remaining_catches(self, max_catches_per_hour: int = 5) -> int:
        """Get number of catches remaining in current hour"""
        self._cleanup_old_catches()
        return max(0, max_catches_per_hour - len(self.catch_history))
    
    def add_catch_to_history(self):
        """Add current timestamp to catch history"""
        self.catch_history.append(datetime.now().isoformat())
    
    def get_catch_cooldown_remaining(self) -> Optional[str]:
        """Get time until catch limit resets (when oldest catch expires)"""
        if not self.catch_history:
            return None
        
        self._cleanup_old_catches()
        
        # If still at catch limit after cleanup, find when oldest catch expires
        if len(self.catch_history) >= 5:
            try:
                oldest_catch = datetime.fromisoformat(self.catch_history[0])
                reset_time = oldest_catch + timedelta(hours=1)
                time_left = reset_time - datetime.now()
                
                if time_left.total_seconds() <= 0:
                    return None
                
                total_seconds = max(0, round(time_left.total_seconds()))
                
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                
                if minutes > 0:
                    if seconds > 0:
                        return f"{minutes}m {seconds}s"
                    else:
                        return f"{minutes}m"
                else:
                    return f"{seconds}s"
            except (ValueError, TypeError):
                # If timestamp is invalid, allow catching
                return None
        
        return None
    
    def _cleanup_old_catches(self):
        """Remove entire catch history if any entry is older than 1 hour"""
        if not self.catch_history:
            return
        
        current_time = datetime.now()
        
        # Check if any catch is older than 1 hour
        for catch_time_str in self.catch_history:
            try:
                catch_time = datetime.fromisoformat(catch_time_str)
                # If any catch is older than 1 hour, clear entire history
                if current_time - catch_time >= timedelta(hours=1):
                    self.catch_history = []
                    return
            except (ValueError, TypeError):
                # If any timestamp is invalid, clear entire history
                self.catch_history = []
                return
    
    # ========== CURRENCY SYSTEM ==========
    
    def add_pokecoins(self, amount: int) -> int:
        """Add PokéCoins to player's balance. Returns new balance."""
        self.pokecoins += amount
        return self.pokecoins
    
    def spend_pokecoins(self, amount: int) -> bool:
        """Spend PokéCoins if player has enough. Returns True if successful."""
        if self.pokecoins >= amount:
            self.pokecoins -= amount
            return True
        return False
    
    def can_claim_daily_bonus(self) -> bool:
        """Check if player can claim daily bonus (100 PokéCoins every 24 hours)"""
        if not self.last_daily_claim:
            return True
        
        try:
            last_claim = datetime.fromisoformat(self.last_daily_claim)
            return datetime.now() - last_claim >= timedelta(hours=24)
        except (ValueError, TypeError):
            # If timestamp is invalid, allow claim
            return True
    
    def claim_daily_bonus(self) -> tuple[bool, int]:
        """
        Claim daily bonus if available. 
        Returns (success, coins_received)
        """
        if not self.can_claim_daily_bonus():
            return False, 0
        
        daily_bonus = 100
        self.add_pokecoins(daily_bonus)
        self.last_daily_claim = datetime.now().isoformat()
        return True, daily_bonus
    
    def get_daily_claim_cooldown_remaining(self) -> Optional[str]:
        """Get time until next daily claim is available"""
        if not self.last_daily_claim:
            return None
        
        try:
            last_claim = datetime.fromisoformat(self.last_daily_claim)
            next_claim = last_claim + timedelta(hours=24)
            time_left = next_claim - datetime.now()
            
            if time_left.total_seconds() <= 0:
                return None
            
            total_seconds = max(0, round(time_left.total_seconds()))
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            
            if hours > 0:
                if minutes > 0:
                    return f"{hours}h {minutes}m"
                else:
                    return f"{hours}h"
            else:
                return f"{minutes}m"
        except (ValueError, TypeError):
            return None
    
    def add_encounter(self, pokemon: PokemonData):
        """Set current encounter and update stats"""
        self.current_encounter = pokemon
        self.encounter_catch_attempted = False  # Reset attempt flag for new encounter
        self.last_encounter = datetime.now().isoformat()
        self.stats.add_encounter()
    
    def catch_pokemon(self, ball_type: str) -> tuple[bool, str, dict]:
        """
        Attempt to catch the current encounter. 
        Returns (success, error_reason, catch_details)
        catch_details contains: {
            'pokemon_name': str,
            'original_catch_rate': float,
            'ball_modifier': float,
            'final_catch_rate': float,
            'ball_type': str,
            'ball_name': str,
            'random_roll': float
        }
        """
        catch_details = {}
        
        if not self.current_encounter:
            return False, "no_encounter", catch_details
        
        # Check if already attempted to catch this encounter
        if self.encounter_catch_attempted:
            return False, "already_attempted", catch_details
        
        # Check catch limit (5 catches per hour)
        if not self.can_catch():
            return False, "catch_limit_reached", catch_details
        
        # Normalize ball type
        ball_type = self.inventory._normalize_ball_type(ball_type)
        
        if not self.inventory.use_pokeball(ball_type):
            return False, "no_pokeball", catch_details
        
        # Mark that we've attempted to catch this encounter
        self.encounter_catch_attempted = True
        
        # Prepare catch details for logging
        pokemon_name = self.current_encounter.name
        original_catch_rate = self.current_encounter.catch_rate
        
        # Calculate catch success with ball type modifier
        ball_config = self.inventory.get_ball_info(ball_type)
        catch_rate_modifier = ball_config.get("catch_rate_modifier", 1.0)
        ball_name = ball_config.get("name", ball_type.title() + " Ball")
        
        if catch_rate_modifier == float('inf'):  # Master Ball
            final_catch_rate = 1.0
        else:
            # Apply ball modifier to base catch rate
            final_catch_rate = min(1.0, original_catch_rate * catch_rate_modifier)
        
        import random
        random_roll = random.random()
        success = random_roll <= final_catch_rate
        
        # Populate catch details for logging
        catch_details = {
            'pokemon_name': pokemon_name,
            'original_catch_rate': original_catch_rate,
            'ball_modifier': catch_rate_modifier,
            'final_catch_rate': final_catch_rate,
            'ball_type': ball_type,
            'ball_name': ball_name,
            'random_roll': random_roll,
            'success': success
        }
        
        if success:
            # Add to collection
            collection_id = len(self.pokemon_collection) + 1
            caught_pokemon = CaughtPokemon(
                pokemon_data=self.current_encounter,
                collection_id=collection_id,
                caught_date=datetime.now().isoformat(),
                caught_with=ball_type,
                caught_from="encounter"
            )
            self.pokemon_collection.append(caught_pokemon)
            self.stats.add_catch()
            # Add to catch history for hourly limit tracking
            self.add_catch_to_history()
            self.current_encounter = None  # Clear encounter
            self.encounter_catch_attempted = False  # Reset flag when encounter is cleared
            return True, "success", catch_details
        
        return False, "escaped", catch_details
    
    def catch_wild_pokemon(self, pokemon: PokemonData) -> bool:
        """Catch a wild Pokemon (different from personal encounters)"""
        # Check catch limit (5 catches per hour)
        if not self.can_catch():
            return False
        
        if not self.inventory.use_pokeball("poke"):  # Updated to use poke instead of normal
            return False
        
        # Wild Pokemon always use normal catch rate
        import random
        success = random.random() <= pokemon.catch_rate
        
        if success:
            collection_id = len(self.pokemon_collection) + 1
            caught_pokemon = CaughtPokemon(
                pokemon_data=pokemon,
                collection_id=collection_id,
                caught_date=datetime.now().isoformat(),
                caught_with="poke",  # Updated to use poke instead of normal
                caught_from="wild_spawn"
            )
            self.pokemon_collection.append(caught_pokemon)
            self.stats.add_catch()
            # Add to catch history for hourly limit tracking
            self.add_catch_to_history()
        
        return success
    
    def get_pokemon_by_id(self, collection_id: int) -> Optional[CaughtPokemon]:
        """Get Pokemon from collection by ID"""
        return next((p for p in self.pokemon_collection if p.collection_id == collection_id), None)
    
    def get_pokemon_by_name(self, name: str) -> Optional[CaughtPokemon]:
        """Get Pokemon from collection by name"""
        return next((p for p in self.pokemon_collection if p.name.lower() == name.lower()), None)
    
    def get_collection_by_rarity(self) -> Dict[str, List[CaughtPokemon]]:
        """Group Pokemon collection by rarity"""
        by_rarity = {"Common": [], "Uncommon": [], "Rare": [], "Legendary": []}
        
        for pokemon in self.pokemon_collection:
            rarity = pokemon.rarity
            if rarity in by_rarity:
                by_rarity[rarity].append(pokemon)
        
        return by_rarity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert player data to dictionary format for JSON storage"""
        pokemon_list = [pokemon.to_dict() for pokemon in self.pokemon_collection]
        
        data = {
            "pokemon": pokemon_list,
            "pokeballs": self.inventory.to_dict(),
            "last_encounter": self.last_encounter,
            "catch_history": self.catch_history,
            "pokecoins": self.pokecoins,
            "last_daily_claim": self.last_daily_claim,
            "stats": self.stats.to_dict(),
            "encounter_catch_attempted": self.encounter_catch_attempted
        }
        
        # Include current encounter if exists
        if self.current_encounter:
            data["current_encounter"] = self.current_encounter.to_dict()
        
        return data