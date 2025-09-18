"""
Player Data Models
Defines data structures for player entities and their game data.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .pokemon_model import CaughtPokemon, PokemonData


class PlayerInventory:
    """Manages player's pokeball inventory"""
    
    def __init__(self, inventory_data: Dict[str, int] = None):
        if inventory_data is None:
            inventory_data = {"normal": 5, "master": 0}
        
        self.normal_pokeballs = inventory_data.get("normal", 5)
        self.master_pokeballs = inventory_data.get("master", 0)
    
    def has_pokeball(self, ball_type: str) -> bool:
        """Check if player has pokeballs of specified type"""
        if ball_type == "normal":
            return self.normal_pokeballs > 0
        elif ball_type == "master":
            return self.master_pokeballs > 0
        return False
    
    def use_pokeball(self, ball_type: str) -> bool:
        """Use a pokeball, returns True if successful"""
        if not self.has_pokeball(ball_type):
            return False
        
        if ball_type == "normal":
            self.normal_pokeballs -= 1
        elif ball_type == "master":
            self.master_pokeballs -= 1
        else:
            return False
        
        return True
    
    def add_pokeballs(self, ball_type: str, count: int):
        """Add pokeballs to inventory"""
        if ball_type == "normal":
            self.normal_pokeballs += count
        elif ball_type == "master":
            self.master_pokeballs += count
    
    def get_pokeball_count(self, ball_type: str) -> int:
        """Get the count of a specific pokeball type"""
        if ball_type == "normal":
            return self.normal_pokeballs
        elif ball_type == "master":
            return self.master_pokeballs
        return 0
    
    def to_dict(self) -> Dict[str, int]:
        """Convert inventory to dictionary format"""
        return {
            "normal": self.normal_pokeballs,
            "master": self.master_pokeballs
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
            "pokeballs": {"normal": 5, "master": 0},
            "last_encounter": None,
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
    
    def add_encounter(self, pokemon: PokemonData):
        """Set current encounter and update stats"""
        self.current_encounter = pokemon
        self.encounter_catch_attempted = False  # Reset attempt flag for new encounter
        self.last_encounter = datetime.now().isoformat()
        self.stats.add_encounter()
    
    def catch_pokemon(self, ball_type: str) -> tuple[bool, str]:
        """Attempt to catch the current encounter. Returns (success, error_reason)"""
        if not self.current_encounter:
            return False, "no_encounter"
        
        # Check if already attempted to catch this encounter
        if self.encounter_catch_attempted:
            return False, "already_attempted"
        
        if not self.inventory.use_pokeball(ball_type):
            return False, "no_pokeball"
        
        # Mark that we've attempted to catch this encounter
        self.encounter_catch_attempted = True
        
        # Calculate catch success
        catch_rate = 1.0 if ball_type == "master" else self.current_encounter.catch_rate
        import random
        success = random.random() <= catch_rate
        
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
            self.current_encounter = None  # Clear encounter
            self.encounter_catch_attempted = False  # Reset flag when encounter is cleared
            return True, "success"
        
        return False, "escaped"
    
    def catch_wild_pokemon(self, pokemon: PokemonData) -> bool:
        """Catch a wild Pokemon (different from personal encounters)"""
        if not self.inventory.use_pokeball("normal"):
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
                caught_with="normal",
                caught_from="wild_spawn"
            )
            self.pokemon_collection.append(caught_pokemon)
            self.stats.add_catch()
        
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
            "stats": self.stats.to_dict(),
            "encounter_catch_attempted": self.encounter_catch_attempted
        }
        
        # Include current encounter if exists
        if self.current_encounter:
            data["current_encounter"] = self.current_encounter.to_dict()
        
        return data