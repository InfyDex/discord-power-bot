#!/bin/bash
echo "[INFO] Stopping discord-bot.service..."
systemctl stop discord-bot.service

echo "[INFO] Changing directory to /home/a1h1/python/discord-power-bot..."
cd /home/a1h1/python/discord-power-bot

echo "[INFO] Resetting git repository..."
git reset --hard

echo "[INFO] Pulling latest changes from origin/main..."
git pull origin main

echo "[INFO] Activating virtual environment..."
source venv/bin/activate

echo "[INFO] Installing requirements..."
pip install -r requirements.txt

echo "[INFO] Deactivating virtual environment..."
deactivate

echo "[INFO] Starting discord-bot.service..."
systemctl start discord-bot.service
