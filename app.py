import os
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_SPORTS_KEY")
BASE_URL = "https://v1.basketball.api-sports.io"
HEADERS = {'x-apisports-key': API_KEY} if API_KEY else {}

# Кэши
matches_cache = []
stats_cache = {}

def fetch_matches():
    """Загружает реальные матчи на сегодня и завтра"""
    if not API_KEY:
        raise Exception("API_SPORTS_KEY not set")
    
    all_matches = []
    today = datetime.now()
    
    for i in range(2):
        date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        resp = requests.get(f"{BASE_URL}/games", params={"date": date}, headers=HEADERS, timeout=10)
        
        if resp.status_code != 200:
            raise Exception(f"API error {resp.status_code}: {resp.text[:200]}")
        
        data = resp.json()
        # Ответ всегда словарь, содержащий 'response' — список
        games = data.get("response", [])
        if not isinstance(games, list):
            raise Exception("Response is not a list")
        
        for game in games:
            status = game.get("status", {}).get("long", "")
            if status not in ["Not Started", "Scheduled"]:
                continue
            
            home = game.get("teams", {}).get("home", {})
            away = game.get("teams", {}).get("visitors", {})
            
            all_matches.append({
                "id": game.get("id"),
                "date": game.get("date", {}).get("start", ""),
                "league": game.get("league", {}).get("name", "Unknown"),
                "home_team": {
                    "id": home.get("id"),
                    "name": home.get("name"),
                    "abbreviation": home.get("code", "")
                },
                "away_team": {
                    "id": away.get("id"),
                    "name": away.get("name"),
                    "abbreviation": away.get("code", "")
                }
            })
    
    return all_matches

def get_team_avg_points(team_id, limit=10):
    resp = requests.get(f"{BASE_URL}/games", params={"team": team_id}, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return 0
    data = resp.json()
    games = data.get("response", [])[:limit]
    total = 0
    count = 0
    for game in games:
        if game.get("teams", {}).get("home", {}).get("id") == team_id:
            pts = game.get("scores", {}).get("home", {}).get("points")
        else:
            pts = game.get("scores", {}).get("visitors", {}).get("points")
        if pts and isinstance(pts, (int, float)):
            total += pts
            count += 1
    return round(total / count, 2) if count else 0

def get_h2h_avg_total(team1_id, team2_id, limit=5):
    resp = requests.get(f"{BASE_URL}/games", params={"h2h": f"{team1_id}-{team2_id}"}, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return 0
    data = resp.json()
    games = data.get("response", [])[:limit]
    total = 0
    count = 0
    for game in games:
        home_pts = game.get("scores", {}).get("home", {}).get("points")
        away_pts = game.get("scores", {}).get("visitors", {}).get("points")
        if home_pts and away_pts and isinstance(home_pts, (int, float)) and isinstance(away_pts, (int, float)):
            total += home_pts + away_pts
            count += 1
    return round(total / count, 2) if count else 0

@app.route('/matches', methods=['GET'])
def get_matches():
    return jsonify({
        "success": True,
        "matches": matches_cache,
        "total": len(matches_cache)
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    match_id = request.args.get('match_id')
    if not match_id:
        return jsonify({"error": "match_id required"}), 400
    
    # Кэш статистики
    if match_id in stats_cache:
        return jsonify(stats_cache[match_id])
    
    # Находим матч
    match = next((m for m in matches_cache if str(m["id"]) == match_id), None)
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
    stats_cache[match_id] = result
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "matches_count": len(matches_cache)
    })

# При запуске загружаем матчи
print("Загрузка матчей...")
try:
    matches_cache = fetch_matches()
    print(f"Загружено {len(matches_cache)} матчей")
except Exception as e:
    print(f"Ошибка: {e}")
    # Если API не работает, сервер не запустится — это лучше, чем демо
    raise

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
