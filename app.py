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
BASE_URL = "https://v1.basketball.api-sports.io"

HEADERS = {
    'x-apisports-key': API_KEY
}

master_cache = {"data": None, "last_update": None, "loading": False}

def fetch_upcoming_games(days_ahead=2):
    """Получает матчи на ближайшие дни"""
    all_games = []
    for i in range(days_ahead + 1):
        date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        
        try:
            print(f"📅 Запрос к API за {date}...")
            response = requests.get(
                f"{BASE_URL}/games",
                params={"date": date},
                headers=HEADERS,
                timeout=30
            )
            
            print(f"   Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                games = data.get("response", [])
                # Только предстоящие матчи
                upcoming = [g for g in games if g.get("status", {}).get("long") in ["Not Started", "Scheduled"]]
                all_games.extend(upcoming)
                print(f"   ✅ {date}: {len(upcoming)} матчей из {len(games)}")
            else:
                print(f"   ❌ Ошибка: {response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
        
        time.sleep(0.3)
    
    return all_games

def fetch_team_last_games(team_id, limit=10):
    """Получает последние N игр команды"""
    try:
        response = requests.get(
            f"{BASE_URL}/games",
            params={"team": team_id},
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            games = data.get("response", [])[:limit]
            
            total_points = 0
            count = 0
            
            for game in games:
                # Определяем, была ли команда дома
                if game.get("teams", {}).get("home", {}).get("id") == team_id:
                    points = game.get("scores", {}).get("home", {}).get("points")
                else:
                    points = game.get("scores", {}).get("visitors", {}).get("points")
                
                if points and points > 0:
                    total_points += points
                    count += 1
            
            avg = round(total_points / count, 2) if count > 0 else 0
            return avg, count
        
        return 0, 0
    except Exception as e:
        print(f"      Ошибка загрузки команды {team_id}: {e}")
        return 0, 0

def fetch_h2h_last_games(team1_id, team2_id, limit=5):
    """Получает последние N личных встреч"""
    try:
        response = requests.get(
            f"{BASE_URL}/games",
            params={"h2h": f"{team1_id}-{team2_id}"},
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            games = data.get("response", [])[:limit]
            
            total_points = 0
            count = 0
            
            for game in games:
                home_score = game.get("scores", {}).get("home", {}).get("points")
                away_score = game.get("scores", {}).get("visitors", {}).get("points")
                
                if home_score and away_score:
                    total_points += home_score + away_score
                    count += 1
            
            avg = round(total_points / count, 2) if count > 0 else 0
            return avg, count
        
        return 0, 0
    except Exception as e:
        print(f"      Ошибка H2H: {e}")
        return 0, 0

def update_master_cache():
    """Обновляет кэш"""
    if master_cache["loading"]:
        return
    
    master_cache["loading"] = True
    print("\n" + "=" * 60)
    print(f"🔄 ОБНОВЛЕНИЕ КЭША - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    print("\n📅 Сбор матчей:")
    games = fetch_upcoming_games(2)
    
    if not games:
        print("❌ НЕТ ПРЕДСТОЯЩИХ МАТЧЕЙ")
        master_cache["loading"] = False
        return
    
    print(f"\n📋 Всего предстоящих матчей: {len(games)}")
    
    enriched_games = []
    
    for idx, game in enumerate(games[:30], 1):  # Ограничим 30 матчами
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
        
        league = game.get("league", {}).get("name", "Unknown")
        
        print(f"\n🔍 [{idx}/{min(30, len(games))}] [{league}] {home_abbr} vs {away_abbr}")
        
        # Получаем статистику
        home_avg, home_cnt = fetch_team_last_games(home_id, 10)
        away_avg, away_cnt = fetch_team_last_games(away_id, 10)
        h2h_avg, h2h_cnt = fetch_h2h_last_games(home_id, away_id, 5)
        
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
        
        time.sleep(0.3)
    
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
        "status": "running",
        "endpoints": ["/upcoming_stats", "/health", "/debug"]
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
        "using_requests": True,
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0
    })

print("🚀 Сервер запускается...")
print("📡 Используем requests (не http.client)")
print("🔑 API Key:", API_KEY[:10] + "...")

threading.Thread(target=update_master_cache).start()

scheduler = BackgroundScheduler()
scheduler.add_job(func=update_master_cache, trigger="interval", hours=6)
scheduler.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
