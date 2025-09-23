import requests
import time
import os
from pymongo import MongoClient, errors
from dotenv import load_dotenv

API_BASE = "https://pokeapi.co/api/v2/move/"

load_dotenv()
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
db_name = os.getenv("MONGO_DB_NAME", "legion_discord_bot")
client = MongoClient(mongo_uri)
db = client[db_name]
moves_collection = db["moves"]
moves_collection.create_index("name", unique=True)

limit = 1000  # Large enough to get all moves

print("Fetching move list...")
resp = requests.get(f"{API_BASE}?limit={limit}")
resp.raise_for_status()
move_list = resp.json()["results"]
print(f"Found {len(move_list)} moves.")

inserted = 0
skipped = 0
for i, move_ref in enumerate(move_list, 1):
    move_url = move_ref["url"]
    print(f"[{i}/{len(move_list)}] Fetching: {move_ref['name']} from {move_url}")
    try:
        move_resp = requests.get(move_url)
        if move_resp.status_code != 200:
            print(f"Failed to fetch {move_ref['name']} (status {move_resp.status_code})")
            continue
        move_data = move_resp.json()
        move_data["name"] = move_data["name"].replace("-", " ").title()  # Normalize name for lookup
        try:
            moves_collection.insert_one(move_data)
            inserted += 1
            print(f"Inserted: {move_data['name']} (ID: {move_data['id']})")
        except errors.DuplicateKeyError:
            skipped += 1
            print(f"Skipped duplicate: {move_data['name']}")
    except Exception as e:
        print(f"Error fetching {move_ref['name']}: {e}")
        continue
    if i % 50 == 0:
        print(f"Processed {i} moves...")
    time.sleep(0.5)  # Delay to avoid rate limiting

print(f"Done! Inserted: {inserted}, Skipped (duplicates): {skipped}")
