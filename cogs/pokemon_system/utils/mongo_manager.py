"""
MongoDB Manager
Handles connection and operations with MongoDB for Pokémon data.
"""

import os
from typing import Dict, List, Any, Optional
from pymongo import MongoClient
from dotenv import load_dotenv
from bson.objectid import ObjectId

# Load environment variables
load_dotenv()

class MongoManager:
    """Manages MongoDB connection and operations for Pokémon data"""
    
    def __init__(self):
        # Get MongoDB connection details from environment variables
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB_NAME", "legion_discord_bot")
        
        # Connect to MongoDB
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.caught_pokemon = self.db["caught_pokemon"]
        
        # Create indexes for better query performance
        self._create_indexes()
        
    def _create_indexes(self):
        """Create necessary indexes for better query performance"""
        # Index for owner_id for faster lookups
        self.caught_pokemon.create_index("owner_id")
        
    def add_pokemon(self, pokemon_data: Dict[str, Any]) -> str:
        """
        Add a Pokémon to the database
        
        Args:
            pokemon_data: Dictionary containing Pokémon data with owner_id
            
        Returns:
            ID of the inserted document
        """
        if "owner_id" not in pokemon_data:
            raise ValueError("Pokemon data must include owner_id")
            
        result = self.caught_pokemon.insert_one(pokemon_data)
        return str(result.inserted_id)

    def get_pokemon_by_owner(
            self,
            owner_id: str,
            page: Optional[int] = None,
            max_per_page: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all Pokémon owned by a specific user, optionally paginated.

        Args:
            owner_id: Discord user ID of the owner
            page: Page number (1-based), optional
            max_per_page: Maximum items per page, optional

        Returns:
            List of Pokémon documents
        """

        query = {"owner_id": owner_id}
        cursor = self.caught_pokemon.find(query)
        if page is not None and max_per_page is not None:
            skip = (page - 1) * max_per_page
            cursor = cursor.skip(skip).limit(max_per_page)
        return list(cursor)
        
    def get_pokemon_by_id(self, pokemon_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific Pokémon by its MongoDB ID
        
        Args:
            pokemon_id: MongoDB ID of the Pokémon
            
        Returns:
            Pokémon document or None if not found
        """
        try:
            return self.caught_pokemon.find_one({"_id": ObjectId(pokemon_id)})
        except:
            return None
            
    def delete_pokemon(self, pokemon_id: str) -> bool:
        """
        Delete a Pokémon from the database
        
        Args:
            pokemon_id: MongoDB ID of the Pokémon
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            result = self.caught_pokemon.delete_one({"_id": ObjectId(pokemon_id)})
            return result.deleted_count > 0
        except:
            return False
            
    def delete_all_pokemon_by_owner(self, owner_id: str) -> int:
        """
        Delete all Pokémon owned by a specific user
        
        Args:
            owner_id: Discord user ID of the owner
            
        Returns:
            Number of deleted documents
        """
        result = self.caught_pokemon.delete_many({"owner_id": owner_id})
        return result.deleted_count
        
    def count_pokemon_by_owner(self, owner_id: str) -> int:
        """
        Count Pokémon owned by a specific user
        
        Args:
            owner_id: Discord user ID of the owner
            
        Returns:
            Number of Pokémon owned by the user
        """
        return self.caught_pokemon.count_documents({"owner_id": owner_id})

    def get_pokemon_grouped_by_owner(self) -> List[Dict[str, Any]]:
        """
        Fetch all Pokémon entries grouped by owner_id.

        Returns:
            List of dicts with owner_id and their Pokémon list.
        """
        pipeline = [
            {
                "$group": {
                    "_id": "$owner_id",
                    "pokemons": {"$push": "$$ROOT"}
                }
            }
        ]
        return list(self.caught_pokemon.aggregate(pipeline))