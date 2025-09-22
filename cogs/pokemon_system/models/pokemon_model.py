"""
Pokemon Data Models
Defines data structures for Pokemon entities.
"""

from typing import Dict, List, Any


class PokemonStats:
    """Represents Pokemon base stats"""
    
    def __init__(self, stats_data: Dict[str, int]):
        self.hp = stats_data.get('hp', 0)
        self.attack = stats_data.get('attack', 0)
        self.defense = stats_data.get('defense', 0)
        self.sp_attack = stats_data.get('sp_attack', 0)
        self.sp_defense = stats_data.get('sp_defense', 0)
        self.speed = stats_data.get('speed', 0)
        self.total = stats_data.get('total', self.calculate_total())
    
    def calculate_total(self) -> int:
        """Calculate total base stat points"""
        return self.hp + self.attack + self.defense + self.sp_attack + self.sp_defense + self.speed
    
    def to_dict(self) -> Dict[str, int]:
        """Convert stats to dictionary format"""
        return {
            'hp': self.hp,
            'attack': self.attack,
            'defense': self.defense,
            'sp_attack': self.sp_attack,
            'sp_defense': self.sp_defense,
            'speed': self.speed,
            'total': self.total
        }


class PokemonData:
    """Represents a Pokemon from the master database"""
    
    def __init__(self, pokemon_id: int, data: Dict[str, Any]):
        self.id = pokemon_id
        self.name = data['name']
        self.types = data['types'] if isinstance(data['types'], list) else [data['types']]
        self.rarity = data['rarity']
        self.catch_rate = data['catch_rate']
        self.generation = data['generation']
        self.description = data['description']
        self.image_url = data['image_url']
        self.sprite_url = data['sprite_url']
        self.stats = PokemonStats(data['stats'])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Pokemon to dictionary format"""
        return {
            'id': self.id,
            'name': self.name,
            'types': self.types,
            'rarity': self.rarity,
            'catch_rate': self.catch_rate,
            'generation': self.generation,
            'description': self.description,
            'image_url': self.image_url,
            'sprite_url': self.sprite_url,
            'stats': self.stats.to_dict()
        }
    
    @classmethod
    def from_dict(cls, pokemon_id: int, data: Dict[str, Any]) -> 'PokemonData':
        """Create PokemonData from dictionary"""
        return cls(pokemon_id, data)


class CaughtPokemon:
    """Represents a Pokemon in a player's collection"""
    
    def __init__(self, pokemon_data: PokemonData, collection_id: int, 
                 caught_date: str, caught_with: str, caught_from: str = "encounter"):
        self.pokemon_data = pokemon_data
        self.collection_id = collection_id
        self.caught_date = caught_date
        self.caught_with = caught_with  # 'normal' or 'master'
        self.caught_from = caught_from  # 'encounter' or 'wild_spawn'
    
    @property
    def name(self) -> str:
        return self.pokemon_data.name
    
    @property
    def types(self) -> List[str]:
        return self.pokemon_data.types
    
    @property
    def rarity(self) -> str:
        return self.pokemon_data.rarity
    
    @property
    def stats(self) -> PokemonStats:
        return self.pokemon_data.stats
    
    @property
    def generation(self) -> int:
        return self.pokemon_data.generation
    
    @property
    def description(self) -> str:
        return self.pokemon_data.description
    
    @property
    def image_url(self) -> str:
        return self.pokemon_data.image_url
    
    @property
    def sprite_url(self) -> str:
        return self.pokemon_data.sprite_url
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert caught Pokemon to dictionary format for JSON storage"""
        return {
            'name': self.name,
            'types': self.types,
            'rarity': self.rarity,
            'caught_date': self.caught_date,
            'id': self.collection_id,
            'stats': self.stats.to_dict(),
            'generation': self.generation,
            'description': self.description,
            'image_url': self.image_url,
            'sprite_url': self.sprite_url,
            'caught_with': self.caught_with,
            'caught_from': self.caught_from
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CaughtPokemon':
        """Create CaughtPokemon from dictionary"""
        # Create a PokemonData object from the stored data
        pokemon_data = PokemonData(
            pokemon_id=0,  # Collection Pokemon don't need the original ID
            data={
                'name': data['name'],
                'types': data['types'],
                'rarity': data['rarity'],
                'generation': data['generation'],
                'description': data['description'],
                'image_url': data['image_url'],
                'sprite_url': data['sprite_url'],
                'stats': data['stats'],
                'catch_rate': 0.5  # Default catch rate for stored Pokemon
            }
        )
        
        return cls(
            pokemon_data=pokemon_data,
            collection_id=data['id'],
            caught_date=data['caught_date'],
            caught_with=data.get('caught_with', 'normal'),
            caught_from=data.get('caught_from', 'encounter')
        )