import os
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_SPORTS_KEY")
BASE_URL = "https://v1.basketball.api-sports.io"
HEADERS = {'x-apisports-key': API_KEY}

matches_cache = {"data": None, "last_update": None}
stats_cache = {}

def fetch_matches():
    """Загружает матчи на сегодня и завтра"""
    all_matches = []
    today = datetime.now()
    
    for i in range(2):
        date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        
        try:
            response = requests.get(
                f"{BASE_URL}/games",
                params={"date": date},
                headers=HEADERS,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                games = data.get("response", [])
                
                for game in games:
                    status = game.get("status", {}).get("long", "")
                    if status in ["Not Started", "Scheduled"]:
                        match = {
                            "id": game.get("id"),
                            "date": game.get("date", {}).get("start", ""),
                            "league": game.get("league", {}).get("name", "Unknown"),
                            "home_team": {
                                "id": game.get("teams", {}).get("home", {}).get("id"),
                                "name": game.get("teams", {}).get("home", {}).get("name"),
                                "abbreviation": game.get("teams", {}).get("home", {}).get("code", "")
                            },
                            "away_team": {
                                "id": game.get("teams", {}).get("visitors", {}).get("id"),
                                "name": game.get("teams", {}).get("visitors", {}).get("name"),
                                "abbreviation": game.get("teams", {}).get("visitors", {}).get("code", "")
                            }
                        }
                        all_matches.append(match)
            else:
                print(f"Ошибка {date}: статус {response.status_code}")
                        
        except Exception as e:
            print(f"Ошибка {date}: {e}")
        
        time.sleep(0.3)
    
    return all_matches

def get_team_avg_points(team_id, limit=10):
    """Получает последние limit игр команды и возвращает среднее очков"""
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
                if game.get("teams", {}).get("home", {}).get("id") == team_id:
                    points = game.get("scores", {}).get("home", {}).get("points")
                else:
                    points = game.get("scores", {}).get("visitors", {}).get("points")
                
                if points and points > 0:
                    total_points += points
                    count += 1
            
            avg = round(total_points / count, 2) if count > 0 else 0
            return avg
        
        return 0
    except Exception as e:
        return 0

def get_h2h_avg_total(team1_id, team2_id, limit=5):
    """Получает последние limit личных встреч и возвращает средний тотал"""
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
            return avg
        
        return 0
    except Exception as e:
        return 0

@app.route('/matches', methods=['GET'])
def get_matches():
    """Возвращает список матчей (без статистики)"""
    if matches_cache["data"] is None:
        return jsonify({"error": "Loading...", "status": "loading"}), 503
    
    return jsonify({
        "success": True,
        "last_update": matches_cache["last_update"],
        "matches": matches_cache["data"],
        "total": len(matches_cache["data"])
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    """Возвращает статистику для конкретного матча"""
    match_id = request.args.get('match_id')
    
    if not match_id:
        return jsonify({"error": "match_id required"}), 400
    
    if match_id in stats_cache:
        cache_time = stats_cache[match_id]["last_update"]
        if datetime.now() - datetime.fromisoformat(cache_time) < timedelta(hours=1):
            return jsonify(stats_cache[match_id]["data"])
    
    match = None
    if matches_cache["data"]:
        for m in matches_cache["data"]:
            if str(m["id"]) == str(match_id):
                match = m
                break
    
    if not match:
        return jsonify({"error": "Match not found"}), 404
    
    home_id = match["home_team"]["id"]
    away_id = match["away_team"]["id"]
    
    home_avg = get_team_avg_points(home_id, 10)
    away_avg = get_team_avg_points(away_id, 10)
    h2h_avg = get_h2h_avg_total(home_id, away_id, 5)
    
    result = {
        "success": True,
        "match_id": match_id,
        "home_avg_points": home_avg,
        "away_avg_points": away_avg,
        "h2h_avg_total": h2h_avg
    }
    
    stats_cache[match_id] = {
        "data": result,
        "last_update": datetime.now().isoformat()
    }
    
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "cached_matches": len(matches_cache["data"]) if matches_cache["data"] else 0,
        "cached_stats": len(stats_cache)
    })

print("🚀 Сервер запускается...")
print(f"🔑 API Key загружен: {'Да' if API_KEY else 'Нет'}")

matches_cache["data"] = fetch_matches()
matches_cache["last_update"] = datetime.now().isoformat()
print(f"✅ Загружено {len(matches_cache['data'])} матчей")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
