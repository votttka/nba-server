import os
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Берём API ключ из переменной окружения
API_KEY = os.environ.get("API_SPORTS_KEY")
if not API_KEY:
    print("⚠️ ВНИМАНИЕ: API_SPORTS_KEY не задан в переменных окружения!")
    # Для локального тестирования можно указать запасной ключ, но на проде лучше не падать
    # API_KEY = "de0a081d8eb05282905920ff73eba124"  # раскомментировать только для теста

BASE_URL = "https://v1.basketball.api-sports.io"
HEADERS = {'x-apisports-key': API_KEY} if API_KEY else {}

matches_cache = {"data": None, "last_update": None}
stats_cache = {}

def fetch_matches():
    """Загружает матчи на сегодня и завтра"""
    if not API_KEY:
        print("❌ Нет API ключа, загрузка матчей невозможна")
        return []
    
    all_matches = []
    today = datetime.now()
    
    for i in range(2):
        date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        
        try:
            print(f"Запрос к API за {date}...")
            response = requests.get(
                f"{BASE_URL}/games",
                params={"date": date},
                headers=HEADERS,
                timeout=30
            )
            
            print(f"Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    games = data.get("response", [])
                    if isinstance(games, list):
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
                        print(f"   ✅ {date}: {len([m for m in all_matches if m.get('date', '').startswith(date)])} матчей")
                    else:
                        print(f"   ❌ {date}: response не список")
                else:
                    print(f"   ❌ {date}: данные не словарь, а {type(data)}")
            else:
                print(f"   ❌ {date}: ошибка {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                        
        except Exception as e:
            print(f"   ❌ Ошибка {date}: {e}")
        
        time.sleep(0.3)
    
    return all_matches

def get_team_avg_points(team_id, limit=10):
    """Получает последние limit игр команды и возвращает среднее очков"""
    if not API_KEY:
        return 0
    try:
        response = requests.get(
            f"{BASE_URL}/games",
            params={"team": team_id},
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                games = data.get("response", [])
                if isinstance(games, list):
                    games = games[:limit]
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
                    return round(total_points / count, 2) if count > 0 else 0
        return 0
    except Exception as e:
        return 0

def get_h2h_avg_total(team1_id, team2_id, limit=5):
    """Получает последние limit личных встреч и возвращает средний тотал"""
    if not API_KEY:
        return 0
    try:
        response = requests.get(
            f"{BASE_URL}/games",
            params={"h2h": f"{team1_id}-{team2_id}"},
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                games = data.get("response", [])
                if isinstance(games, list):
                    games = games[:limit]
                    total_points = 0
                    count = 0
                    for game in games:
                        home_score = game.get("scores", {}).get("home", {}).get("points")
                        away_score = game.get("scores", {}).get("visitors", {}).get("points")
                        if home_score and away_score:
                            total_points += home_score + away_score
                            count += 1
                    return round(total_points / count, 2) if count > 0 else 0
        return 0
    except Exception as e:
        return 0

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "NBA Total Predictor API",
        "status": "running",
        "api_key_set": bool(API_KEY),
        "endpoints": ["/matches", "/stats", "/health"]
    })

@app.route('/matches', methods=['GET'])
def get_matches():
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
        "cached_stats": len(stats_cache),
        "api_key_configured": bool(API_KEY)
    })

# Запуск
print("🚀 Сервер запускается...")
if API_KEY:
    print(f"🔑 API ключ загружен из переменной окружения (первые {min(5, len(API_KEY))} символов: {API_KEY[:5]}...)")
else:
    print("❌ API_SPORTS_KEY не найден в переменных окружения!")
    print("   Убедитесь, что в Render добавлена переменная окружения API_SPORTS_KEY")

matches_cache["data"] = fetch_matches()
matches_cache["last_update"] = datetime.now().isoformat()
print(f"✅ Загружено {len(matches_cache['data'])} матчей")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
