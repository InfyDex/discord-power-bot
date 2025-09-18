"""
Pokemon System Models
Contains data structures for Pokemon and Player entities.
"""

from .pokemon_model import PokemonData, CaughtPokemon
from .player_model import PlayerData, PlayerStats, PlayerInventory

__all__ = [
    'PokemonData',
    'CaughtPokemon', 
    'PlayerData',
    'PlayerStats',
    'PlayerInventory'
]