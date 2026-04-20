import os
import json
import http.client
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import threading

app = Flask(__name__)
CORS(app)

API_KEY = "de0a081d8eb05282905920ff73eba124"

master_cache = {"data": None, "last_update": None, "loading": False}

def make_api_request(endpoint):
    """Делает запрос к v1.basketball.api-sports.io (все лиги, нет NBA)"""
    try:
        conn = http.client.HTTPSConnection("v1.basketball.api-sports.io")
        headers = {'x-apisports-key': API_KEY}
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            print(f"   Ошибка {res.status}")
            return None
    except Exception as e:
        print(f"   Ошибка: {e}")
        return None

def fetch_upcoming_games(days_ahead=2):
    """Получает матчи на ближайшие дни"""
    all_games = []
    for i in range(days_ahead + 1):
        date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        
        result = make_api_request(f"/games?date={date}")
        
        if result and "response" in result:
            games = result["response"]
            # Только предстоящие матчи
            upcoming = [g for g in games if g.get("status", {}).get("long") in ["Not Started", "Scheduled"]]
            all_games.extend(upcoming)
            print(f"   {date}: {len(upcoming)} матчей")
        
        time.sleep(0.3)
    
    return all_games

def fetch_last_games(team_id, limit=10):
    """Получает последние N игр команды"""
    result = make_api_request(f"/games?team={team_id}")
    
    if result and "response" in result:
        games = result["response"][:limit]
        
        total_points = 0
        games_analyzed = 0
        
        for game in games:
            if game.get("teams", {}).get("home", {}).get("id") == team_id:
                points = game.get("scores", {}).get("home", {}).get("points")
            else:
                points = game.get("scores", {}).get("visitors", {}).get("points")
            
            if points and points > 0:
                total_points += points
                games_analyzed += 1
        
        avg = round(total_points / games_analyzed, 2) if games_analyzed > 0 else 0
        return avg, games_analyzed
    
    return 0, 0

def fetch_last_h2h(team1_id, team2_id, limit=5):
    """Получает последние N личных встреч"""
    result = make_api_request(f"/games?h2h={team1_id}-{team2_id}")
    
    if result and "response" in result:
        games = result["response"][:limit]
        
        total_points = 0
        games_analyzed = 0
        
        for game in games:
            home_score = game.get("scores", {}).get("home", {}).get("points")
            away_score = game.get("scores", {}).get("visitors", {}).get("points")
            
            if home_score and away_score:
                total_points += home_score + away_score
                games_analyzed += 1
        
        avg = round(total_points / games_analyzed, 2) if games_analyzed > 0 else 0
        return avg, games_analyzed
    
    return 0, 0

def update_master_cache():
    """Обновляет кэш"""
    if master_cache["loading"]:
        return
    
    master_cache["loading"] = True
    print("\n" + "=" * 60)
    print(f"🔄 ОБНОВЛЕНИЕ КЭША - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📡 Источник: v1.basketball.api-sports.io (без NBA)")
    print("=" * 60)
    
    print("\n📅 Сбор матчей:")
    games = fetch_upcoming_games(2)
    
    if not games:
        print("❌ НЕТ ПРЕДСТОЯЩИХ МАТЧЕЙ")
        master_cache["loading"] = False
        return
    
    print(f"\n📋 Всего матчей: {len(games)}")
    
    enriched_games = []
    
    for idx, game in enumerate(games, 1):
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
        
        # Название турнира/лиги
        league = game.get("tournament", {}).get("name", "")
        if not league:
            league = game.get("league", {}).get("name", "")
        
        print(f"\n🔍 [{idx}/{len(games)}] [{league}] {home_abbr} vs {away_abbr}")
        
        home_avg, home_cnt = fetch_last_games(home_id, 10)
        away_avg, away_cnt = fetch_last_games(away_id, 10)
        h2h_avg, h2h_cnt = fetch_last_h2h(home_id, away_id, 5)
        
        enriched_games.append({
            "game_id": game.get("id"),
            "date": game.get("date", {}).get("start", ""),
            "league": league,
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
        
        print(f"   📊 H:{home_avg} A:{away_avg} H2H:{h2h_avg}")
        
        time.sleep(0.5)
    
    master_cache["data"] = enriched_games
    master_cache["last_update"] = datetime.now().isoformat()
    master_cache["loading"] = False
    
    print("\n" + "=" * 60)
    print(f"✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО! Обработано {len(enriched_games)} матчей")
    print("=" * 60)

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "NBA Total Predictor API",
        "version": "7.0",
        "status": "running",
        "endpoints": {
            "/upcoming_stats": "GET - Статистика предстоящих матчей",
            "/health": "GET - Статус сервера",
            "/debug": "GET - Диагностика"
        }
    })

@app.route('/upcoming_stats', methods=['GET'])
def get_upcoming_stats():
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
    return jsonify({
        "api_source": "v1.basketball.api-sports.io",
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0,
        "last_update": master_cache["last_update"]
    })

print("🚀 NBA Total Predictor Server v7")
print("📡 Источник: v1.basketball.api-sports.io (все лиги, NBA отсутствует)")
print("⏱️  Обновление каждые 6 часов")

threading.Thread(target=update_master_cache).start()

scheduler = BackgroundScheduler()
scheduler.add_job(func=update_master_cache, trigger="interval", hours=6)
scheduler.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
