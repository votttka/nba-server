import os
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from collections import OrderedDict
import threading

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
BASE_URL = "https://api.balldontlie.io/v1"

CURRENT_SEASON = 2025
master_cache = {"data": None, "last_update": None, "loading": False}

def update_master_cache():
    if master_cache["loading"]:
        return
    master_cache["loading"] = True
    print("🔄 Загрузка данных...")
    
    # Для теста - демо-данные (потом замените на реальный API)
    demo_games = [
        {
            "game_id": 1,
            "date": (datetime.now() + timedelta(days=1)).isoformat(),
            "home_team": {"id": 1, "name": "Los Angeles Lakers", "abbreviation": "LAL"},
            "away_team": {"id": 2, "name": "Golden State Warriors", "abbreviation": "GSW"},
            "home_stats": {"avg_points": 115.5, "games_analyzed": 15},
            "away_stats": {"avg_points": 118.2, "games_analyzed": 15},
            "h2h_stats": {"avg_total": 233.7, "games_analyzed": 5},
            "predicted_total": 116.8
        }
    ]
    
    master_cache["data"] = demo_games
    master_cache["last_update"] = datetime.now().isoformat()
    master_cache["loading"] = False
    print("✅ Кэш обновлён (демо-режим)")

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    if master_cache["data"] is None:
        return jsonify({"error": "Loading...", "status": "loading"}), 503
    return jsonify({
        "success": True,
        "last_update": master_cache["last_update"],
        "games": master_cache["data"],
        "total_games": len(master_cache["data"])
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0
    })

@app.route('/debug', methods=['GET'])
def debug():
    return jsonify({"api_key_test": 200, "message": "Demo mode active"})

# ЗАПУСКАЕМ ОБНОВЛЕНИЕ ПРИ СТАРТЕ (для Gunicorn)
threading.Thread(target=update_master_cache).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
