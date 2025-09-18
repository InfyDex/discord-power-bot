"""
Pokemon Type Utilities
Helper functions for Pokemon type colors, rarities, and formatting.
"""

from typing import List


class PokemonTypeUtils:
    """Utilities for Pokemon type handling"""
    
    TYPE_COLORS = {
        "Normal": 0xA8A878,
        "Fire": 0xF08030,
        "Water": 0x6890F0,
        "Electric": 0xF8D030,
        "Grass": 0x78C850,
        "Ice": 0x98D8D8,
        "Fighting": 0xC03028,
        "Poison": 0xA040A0,
        "Ground": 0xE0C068,
        "Flying": 0xA890F0,
        "Psychic": 0xF85888,
        "Bug": 0xA8B820,
        "Rock": 0xB8A038,
        "Ghost": 0x705898,
        "Dragon": 0x7038F8,
        "Dark": 0x705848,
        "Steel": 0xB8B8D0,
        "Fairy": 0xEE99AC
    }
    
    RARITY_EMOJIS = {
        "Common": "⚪",
        "Uncommon": "🟢", 
        "Rare": "🔵",
        "Legendary": "🟡"
    }
    
    @classmethod
    def get_type_color(cls, pokemon_types: List[str]) -> int:
        """Get Discord embed color based on primary Pokemon type"""
        primary_type = pokemon_types[0] if pokemon_types else "Normal"
        return cls.TYPE_COLORS.get(primary_type, 0x000000)
    
    @classmethod
    def get_rarity_emoji(cls, rarity: str) -> str:
        """Get emoji for Pokemon rarity"""
        return cls.RARITY_EMOJIS.get(rarity, "⚪")
    
    @classmethod
    def format_types(cls, types: List[str]) -> str:
        """Format type list as string"""
        return " / ".join(types)