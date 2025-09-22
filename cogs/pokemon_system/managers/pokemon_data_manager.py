"""
Pokemon Database Manager
Handles loading and managing the Pokemon master database.
"""

import json
import os
import random
from typing import Dict, List, Optional, Tuple
from ..models.pokemon_model import PokemonData


class PokemonDatabaseManager:
    """Manages the Pokemon master database operations"""
    
    def __init__(self, database_file: str = "pokemon_master_database.json"):
        self.database_file = database_file
        self.pokemon_database: Dict[int, PokemonData] = {}
        self.load_database()
    
    def load_database(self) -> bool:
        """Load the Pokemon database from JSON file"""
        try:
            if not os.path.exists(self.database_file):
                print(f"Pokemon database file {self.database_file} not found!")
                return False
            
            with open(self.database_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # Convert raw data to PokemonData objects
            self.pokemon_database = {}
            for pokemon_id_str, pokemon_data in raw_data.items():
                pokemon_id = int(pokemon_id_str)
                self.pokemon_database[pokemon_id] = PokemonData(pokemon_id, pokemon_data)
            
            print(f"Loaded {len(self.pokemon_database)} Pokemon from database")
            return True
            
        except FileNotFoundError:
            print(f"Pokemon database file {self.database_file} not found!")
            return False
        except json.JSONDecodeError as e:
            print(f"Error decoding {self.database_file}: {e}")
            return False
        except Exception as e:
            print(f"Error loading Pokemon database: {e}")
            return False
    
    def get_pokemon_by_id(self, pokemon_id: int) -> Optional[PokemonData]:
        """Get Pokemon data by ID"""
        return self.pokemon_database.get(pokemon_id)
    
    def get_pokemon_by_name(self, name: str) -> Optional[PokemonData]:
        """Get Pokemon data by name (case-insensitive)"""
        for pokemon in self.pokemon_database.values():
            if pokemon.name.lower() == name.lower():
                return pokemon
        return None
    
    def get_pokemon_by_rarity(self, rarity: str) -> List[PokemonData]:
        """Get all Pokemon of a specific rarity"""
        return [pokemon for pokemon in self.pokemon_database.values() 
                if pokemon.rarity.lower() == rarity.lower()]
    
    def get_pokemon_by_generation(self, generation: int) -> List[PokemonData]:
        """Get all Pokemon from a specific generation"""
        return [pokemon for pokemon in self.pokemon_database.values() 
                if pokemon.generation == generation]
    
    def get_common_uncommon_pokemon(self) -> Optional[PokemonData]:
        """Get a random Pokemon that is Common or Uncommon rarity only"""
        common_uncommon_pokemon = [
            pokemon for pokemon in self.pokemon_database.values() 
            if pokemon.rarity in ['Common', 'Uncommon']
        ]
        
        if not common_uncommon_pokemon:
            return None
        
        # Weight towards common (70% common, 30% uncommon)
        common_pokemon = [p for p in common_uncommon_pokemon if p.rarity == 'Common']
        uncommon_pokemon = [p for p in common_uncommon_pokemon if p.rarity == 'Uncommon']
        
        if random.random() < 0.7 and common_pokemon:
            return random.choice(common_pokemon)
        elif uncommon_pokemon:
            return random.choice(uncommon_pokemon)
        else:
            return random.choice(common_uncommon_pokemon)
    
    def get_random_pokemon_by_rarity_weights(self) -> Optional[PokemonData]:
        """Get a random Pokemon based on rarity weights"""
        rarity_weights = {
            "Common": 0.60,
            "Uncommon": 0.30, 
            "Rare": 0.08,
            "Legendary": 0.02
        }
        
        # Choose rarity based on weights
        rarities = list(rarity_weights.keys())
        weights = list(rarity_weights.values())
        chosen_rarity = random.choices(rarities, weights=weights)[0]
        
        # Get all Pokemon of chosen rarity
        pokemon_of_rarity = self.get_pokemon_by_rarity(chosen_rarity)
        
        if not pokemon_of_rarity:
            # Fallback to any Pokemon
            pokemon_of_rarity = list(self.pokemon_database.values())
        
        if pokemon_of_rarity:
            return random.choice(pokemon_of_rarity)
        
        return None
    
    def get_database_stats(self) -> Dict[str, any]:
        """Get statistics about the Pokemon database"""
        total_pokemon = len(self.pokemon_database)
        
        # Count by generation
        generation_counts = {}
        rarity_counts = {"Common": 0, "Uncommon": 0, "Rare": 0, "Legendary": 0}
        
        for pokemon in self.pokemon_database.values():
            gen = pokemon.generation
            rarity = pokemon.rarity
            
            generation_counts[gen] = generation_counts.get(gen, 0) + 1
            if rarity in rarity_counts:
                rarity_counts[rarity] += 1
        
        return {
            "total_pokemon": total_pokemon,
            "generation_counts": generation_counts,
            "rarity_counts": rarity_counts
        }
    
    def search_pokemon(self, query: str, limit: int = 10) -> List[PokemonData]:
        """Search Pokémon by name (partial matches allowed)"""
        query = query.lower()
        matches = []
        
        for pokemon in self.pokemon_database.values():
            if query in pokemon.name.lower():
                matches.append(pokemon)
                if len(matches) >= limit:
                    break
        
        return matches
    
    def reload_database(self) -> bool:
        """Reload the database from file"""
        return self.load_database()
    
    @property
    def total_pokemon(self) -> int:
        """Get total number of Pokemon in database"""
        return len(self.pokemon_database)
    
    @property
    def available_generations(self) -> List[int]:
        """Get list of available generations"""
        generations = set(pokemon.generation for pokemon in self.pokemon_database.values())
        return sorted(list(generations))