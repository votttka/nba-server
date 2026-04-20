import os
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import threading

app = Flask(__name__)
CORS(app)

API_KEY = "de0a081d8eb05282905920ff73eba124"

# Два источника API
API_SOURCES = {
    "v1": {
        "url": "https://v1.basketball.api-sports.io",
        "headers": {
            'x-rapidapi-host': 'v1.basketball.api-sports.io',
            'x-rapidapi-key': API_KEY
        }
    },
    "v2": {
        "url": "https://v2.nba.api-sports.io",
        "headers": {
            'x-rapidapi-host': 'v2.nba.api-sports.io',
            'x-rapidapi-key': API_KEY
        }
    }
}

master_cache = {"data": None, "last_update": None, "loading": False}

def make_api_request(source, endpoint, params=None):
    """Делает запрос к API"""
    try:
        url = f"{API_SOURCES[source]['url']}/{endpoint}"
        response = requests.get(url, params=params, headers=API_SOURCES[source]['headers'], timeout=30)
        return response
    except Exception as e:
        print(f"Ошибка {source}: {e}")
        return None

def fetch_upcoming_games_from_source(source, days_ahead=1):
    """Получает матчи из источника"""
    all_games = []
    for i in range(days_ahead + 1):
        date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        response = make_api_request(source, "games", {"date": date})
        if response and response.status_code == 200:
            games = response.json().get("response", [])
            upcoming = [g for g in games if g.get("status", {}).get("long") in ["Not Started", "Scheduled"]]
            all_games.extend(upcoming)
            print(f"   {source.upper()} {date}: {len(upcoming)} матчей")
        time.sleep(0.3)
    return all_games

def fetch_team_stats_from_source(source, team_id, games_count=20):
    """Получает статистику команды"""
    response = make_api_request(source, "games", {"team": team_id, "season": "2025-2026"})
    if response and response.status_code == 200:
        games = response.json().get("response", [])[:games_count]
        total_points = 0
        games_analyzed = 0
        for game in games:
            if game.get("teams", {}).get("home", {}).get("id") == team_id:
                points = game.get("scores", {}).get("home", {}).get("points")
            else:
                points = game.get("scores", {}).get("visitors", {}).get("points")
            if points:
                total_points += points
                games_analyzed += 1
        return round(total_points / games_analyzed, 2) if games_analyzed > 0 else 0, games_analyzed
    return 0, 0

def fetch_h2h_stats_from_source(source, team1_id, team2_id, games_count=10):
    """Получает историю личных встреч"""
    response = make_api_request(source, "games", {"h2h": f"{team1_id}-{team2_id}", "season": "2025-2026"})
    if response and response.status_code == 200:
        games = response.json().get("response", [])[:games_count]
        total_points = 0
        games_analyzed = 0
        for game in games:
            home_score = game.get("scores", {}).get("home", {}).get("points")
            away_score = game.get("scores", {}).get("visitors", {}).get("points")
            if home_score and away_score:
                total_points += home_score + away_score
                games_analyzed += 1
        return round(total_points / games_analyzed, 2) if games_analyzed > 0 else 0, games_analyzed
    return 0, 0

def update_master_cache():
    """Обновляет кэш - собирает данные с обоих источников"""
    if master_cache["loading"]:
        return
    
    master_cache["loading"] = True
    print("\n" + "=" * 60)
    print(f"🔄 ОБНОВЛЕНИЕ КЭША - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Собираем матчи с обоих источников
    games_v1 = fetch_upcoming_games_from_source("v1", 1)
    games_v2 = fetch_upcoming_games_from_source("v2", 1)
    
    # Объединяем уникальные матчи по game_id
    all_games_dict = {}
    for game in games_v1:
        all_games_dict[game.get("id")] = game
    for game in games_v2:
        if game.get("id") not in all_games_dict:
            all_games_dict[game.get("id")] = game
    
    print(f"\n📋 Уникальных матчей: {len(all_games_dict)}")
    
    if not all_games_dict:
        print("❌ НЕТ ПРЕДСТОЯЩИХ МАТЧЕЙ")
        master_cache["loading"] = False
        return
    
    enriched_games = []
    total_requests = {"v1": 0, "v2": 0}
    
    for idx, (game_id, game) in enumerate(all_games_dict.items(), 1):
        home = game.get("teams", {}).get("home", {})
        away = game.get("teams", {}).get("visitors", {})
        
        home_id = home.get("id")
        away_id = away.get("id")
        
        if not home_id or not away_id:
            continue
        
        home_name = home.get("name", "Unknown")
        away_name = away.get("name", "Unknown")
        home_abbr = home.get("code", home_name[:3]).upper()
        away_abbr = away.get("code", away_name[:3]).upper()
        
        print(f"\n🔍 [{idx}/{len(all_games_dict)}] {home_abbr} vs {away_abbr}")
        
        # Собираем данные с v1
        h1_avg, h1_cnt = fetch_team_stats_from_source("v1", home_id, 20)
        a1_avg, a1_cnt = fetch_team_stats_from_source("v1", away_id, 20)
        h2h1_avg, h2h1_cnt = fetch_h2h_stats_from_source("v1", home_id, away_id, 10)
        total_requests["v1"] += 3
        
        # Собираем данные с v2
        h2_avg, h2_cnt = fetch_team_stats_from_source("v2", home_id, 20)
        a2_avg, a2_cnt = fetch_team_stats_from_source("v2", away_id, 20)
        h2h2_avg, h2h2_cnt = fetch_h2h_stats_from_source("v2", home_id, away_id, 10)
        total_requests["v2"] += 3
        
        # Усредняем данные с обоих источников
        home_avg = round((h1_avg + h2_avg) / 2, 2) if h1_avg and h2_avg else (h1_avg or h2_avg)
        away_avg = round((a1_avg + a2_avg) / 2, 2) if a1_avg and a2_avg else (a1_avg or a2_avg)
        h2h_avg = round((h2h1_avg + h2h2_avg) / 2, 2) if h2h1_avg and h2h2_avg else (h2h1_avg or h2h2_avg)
        
        enriched_games.append({
            "game_id": game_id,
            "date": game.get("date", {}).get("start", ""),
            "home_team": {
                "id": home_id,
                "name": home_name,
                "abbreviation": home_abbr
            },
            "away_team": {
                "id": away_id,
                "name": away_name,
                "abbreviation": away_abbr
            },
            "home_avg_points": home_avg,
            "away_avg_points": away_avg,
            "h2h_avg_total": h2h_avg
        })
        
        print(f"   📊 Результат: H:{home_avg} A:{away_avg} H2H:{h2h_avg}")
        print(f"   📡 v1: H:{h1_avg} A:{a1_avg} H2H:{h2h1_avg}")
        print(f"   📡 v2: H:{h2_avg} A:{a2_avg} H2H:{h2h2_avg}")
        
        time.sleep(0.5)
    
    master_cache["data"] = enriched_games
    master_cache["last_update"] = datetime.now().isoformat()
    master_cache["loading"] = False
    
    print("\n" + "=" * 60)
    print(f"✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО")
    print(f"📊 Обработано матчей: {len(enriched_games)}")
    print(f"📡 Запросов к v1: {total_requests['v1']}")
    print(f"📡 Запросов к v2: {total_requests['v2']}")
    print("=" * 60)

@app.route('/upcoming_stats', methods=['GET'])
def get_upcoming_stats():
    """Возвращает статистику предстоящих матчей"""
    if master_cache["data"] is None:
        return jsonify({"error": "Data is loading, please wait", "status": "loading"}), 503
    
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
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0,
        "last_update": master_cache["last_update"]
    })

@app.route('/debug', methods=['GET'])
def debug():
    return jsonify({
        "api_key": API_KEY[:10] + "...",
        "sources": ["v1", "v2"],
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0,
        "last_update": master_cache["last_update"]
    })

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "NBA Total Predictor API",
        "version": "3.0",
        "description": "Собирает данные с v1.basketball.api-sports.io и v2.nba.api-sports.io",
        "endpoints": {
            "/upcoming_stats": "GET - Статистика предстоящих матчей",
            "/health": "GET - Статус сервера",
            "/debug": "GET - Диагностика"
        }
    })

# Запуск обновления при старте
print("🚀 NBA Total Predictor Server v3")
print(f"🔑 API Key: {API_KEY[:10]}...")
print("📡 Источники: v1.basketball.api-sports.io, v2.nba.api-sports.io")
print("⏱️  Обновление каждые 6 часов (4 раза в сутки)\n")

threading.Thread(target=update_master_cache).start()

# Обновление каждые 6 часов (4 раза в сутки) - соблюдаем лимит 100 запросов/день
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_master_cache, trigger="interval", hours=6)
scheduler.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
