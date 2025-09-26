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
        self.pokemon_parties = self.db["pokemon_parties"]
        
        # Create indexes for better query performance
        self._create_indexes()
        
    def _create_indexes(self):
        """Create necessary indexes for better query performance"""
        # Index for owner_id for faster lookups
        self.caught_pokemon.create_index("owner_id")
        self.pokemon_parties.create_index("owner_id")
        
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
        except Exception:
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
        except Exception:
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

    def get_last_pokemon(self, owner_id) -> Optional[Dict[str, Any]]:
        """
        Get the most recently added Pokémon for a specific user.

        Args:
            owner_id: Discord user ID of the owner
        Returns:
            The most recently added Pokémon document or None if not found
        """
        return self.caught_pokemon.find_one(
            {"owner_id": owner_id},
            sort=[("id", -1)]
        )
    
    # ========== PARTY MANAGEMENT METHODS ==========
    
    def get_party(self, owner_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user's Pokémon party
        
        Args:
            owner_id: Discord user ID of the owner
            
        Returns:
            Party document or None if not found
        """
        return self.pokemon_parties.find_one({"owner_id": owner_id})
    
    def create_or_update_party(self, owner_id: str, party_data: Dict[str, Any]) -> str:
        """
        Create or update a user's Pokémon party
        
        Args:
            owner_id: Discord user ID of the owner
            party_data: Dictionary containing party data
            
        Returns:
            ID of the inserted/updated document
        """
        party_data["owner_id"] = owner_id
        
        # Check if party already exists
        existing_party = self.get_party(owner_id)
        
        if existing_party:
            # Update existing party
            result = self.pokemon_parties.update_one(
                {"owner_id": owner_id},
                {"$set": party_data}
            )
            return str(existing_party["_id"])
        else:
            # Create new party
            result = self.pokemon_parties.insert_one(party_data)
            return str(result.inserted_id)
    
    def add_pokemon_to_party(self, owner_id: str, index: int, pokemon_id: int) -> bool:
        """
        Add a Pokémon to a specific index in the party
        
        Args:
            owner_id: Discord user ID of the owner
            index: Party index (1-6)
            pokemon_id: ID of the Pokémon to add
            
        Returns:
            True if successful, False otherwise
        """
        if not (1 <= index <= 6):
            return False
        
        # Get existing party or create default
        party = self.get_party(owner_id)
        if not party:
            party = {
                "owner_id": owner_id,
                "first_pokemon": None,
                "second_pokemon": None,
                "third_pokemon": None,
                "fourth_pokemon": None,
                "fifth_pokemon": None,
                "sixth_pokemon": None
            }
        
        # Map index to field name
        field_map = {
            1: "first_pokemon",
            2: "second_pokemon", 
            3: "third_pokemon",
            4: "fourth_pokemon",
            5: "fifth_pokemon",
            6: "sixth_pokemon"
        }
        
        # Update the specific slot
        party[field_map[index]] = pokemon_id
        
        # Save the party
        self.create_or_update_party(owner_id, party)
        return True
    
    def remove_pokemon_from_party(self, owner_id: str, index: int) -> bool:
        """
        Remove a Pokémon from a specific index in the party
        
        Args:
            owner_id: Discord user ID of the owner
            index: Party index (1-6)
            
        Returns:
            True if successful, False otherwise
        """
        if not (1 <= index <= 6):
            return False
        
        party = self.get_party(owner_id)
        if not party:
            return False
        
        # Map index to field name
        field_map = {
            1: "first_pokemon",
            2: "second_pokemon", 
            3: "third_pokemon",
            4: "fourth_pokemon",
            5: "fifth_pokemon",
            6: "sixth_pokemon"
        }
        
        # Remove the Pokémon from the specific slot
        party[field_map[index]] = None
        
        # Save the party
        self.create_or_update_party(owner_id, party)
        return True