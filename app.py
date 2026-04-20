import os
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from collections import OrderedDict

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
BASE_URL = "https://api.balldontlie.io/v1"

# Текущий сезон (2025-2026)
CURRENT_SEASON = datetime.now().year
if datetime.now().month < 10:  # Если сейчас до октября, используем прошлый сезон
    CURRENT_SEASON -= 1

print(f"🏀 Используется сезон: {CURRENT_SEASON}")

# Кэши
TEAM_STATS_CACHE = OrderedDict()
H2H_CACHE = OrderedDict()
CACHE_TTL = 3600
master_cache = {"data": None, "last_update": None}

def fetch_games_for_next_4_days():
    """Получает список матчей на ближайшие 4 дня"""
    today = datetime.now().date()
    all_games = []
    
    for i in range(5):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        url = f"{BASE_URL}/games"
        params = {"dates[]": date_str, "per_page": 100}
        headers = {"Authorization": API_KEY}
        
        try:
            print(f"📅 Загрузка игр за {date_str}...")
            response = requests.get(url, params=params, headers=headers, timeout=30)
            print(f"   Статус: {response.status_code}")
            
            if response.status_code == 200:
                games = response.json().get("data", [])
                all_games.extend(games)
                print(f"   ✅ Загружено {len(games)} игр")
            else:
                print(f"   ❌ Ошибка: {response.text[:200]}")
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
    
    return all_games

def fetch_team_stats(team_id, limit=15):
    """Получает последние игры команды"""
    cache_key = f"team_{team_id}_{CURRENT_SEASON}"
    if cache_key in TEAM_STATS_CACHE:
        cached_time, data = TEAM_STATS_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return data
    
    url = f"{BASE_URL}/games"
    params = {
        "team_ids[]": team_id,
        "per_page": limit,
        "seasons[]": CURRENT_SEASON
    }
    headers = {"Authorization": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            games = response.json().get("data", [])
            TEAM_STATS_CACHE[cache_key] = (time.time(), games)
            return games
    except Exception as e:
        print(f"   ❌ Ошибка загрузки команды {team_id}: {e}")
    return []

def calculate_average_points(games, team_id):
    """Рассчитывает среднее количество очков"""
    if not games:
        return 0.0
    
    total_points = 0
    count = 0
    
    for game in games:
        if game["home_team"]["id"] == team_id:
            total_points += game["home_team_score"]
            count += 1
        elif game["visitor_team"]["id"] == team_id:
            total_points += game["visitor_team_score"]
            count += 1
    
    return round(total_points / count, 2) if count > 0 else 0.0

def fetch_h2h_stats(team1_id, team2_id, limit=5):
    """Получает историю личных встреч"""
    cache_key = f"h2h_{min(team1_id, team2_id)}_{max(team1_id, team2_id)}_{CURRENT_SEASON}"
    if cache_key in H2H_CACHE:
        cached_time, data = H2H_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return data
    
    url = f"{BASE_URL}/games"
    params = {
        "team_ids[]": f"{team1_id},{team2_id}",
        "per_page": limit,
        "seasons[]": CURRENT_SEASON
    }
    headers = {"Authorization": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            games = response.json().get("data", [])
            H2H_CACHE[cache_key] = (time.time(), games)
            return games
    except Exception as e:
        print(f"   ❌ Ошибка H2H: {e}")
    return []

def calculate_h2h_average(games):
    """Рассчитывает средний тотал в личных встречах"""
    if not games:
        return 0.0
    
    total_points = 0
    for game in games:
        total_points += game["home_team_score"] + game["visitor_team_score"]
    
    return round(total_points / len(games), 2)

def update_master_cache():
    """Обновляет главный кэш"""
    print("🔄 Начинаю обновление кэша...")
    print("=" * 50)
    
    games = fetch_games_for_next_4_days()
    if not games:
        print("❌ Не найдено игр за следующие 4 дня")
        print("💡 Возможно, сейчас межсезонье или нет запланированных матчей")
        
        # Для тестирования создадим демо-данные
        print("📝 Создаю демо-данные для тестирования...")
        demo_games = [
            {
                "game_id": 1,
                "date": (datetime.now() + timedelta(days=1)).isoformat(),
                "home_team": {"id": 1, "full_name": "Los Angeles Lakers", "abbreviation": "LAL"},
                "away_team": {"id": 2, "full_name": "Golden State Warriors", "abbreviation": "GSW"},
                "home_stats": {"avg_points": 115.5, "games_analyzed": 10},
                "away_stats": {"avg_points": 118.2, "games_analyzed": 10},
                "h2h_stats": {"avg_total": 233.7, "games_analyzed": 5},
                "predicted_total": 116.8
            },
            {
                "game_id": 2,
                "date": (datetime.now() + timedelta(days=2)).isoformat(),
                "home_team": {"id": 3, "full_name": "Boston Celtics", "abbreviation": "BOS"},
                "away_team": {"id": 4, "full_name": "Miami Heat", "abbreviation": "MIA"},
                "home_stats": {"avg_points": 120.1, "games_analyzed": 10},
                "away_stats": {"avg_points": 109.8, "games_analyzed": 10},
                "h2h_stats": {"avg_total": 218.5, "games_analyzed": 5},
                "predicted_total": 114.2
            }
        ]
        master_cache["data"] = demo_games
        master_cache["last_update"] = datetime.now().isoformat()
        print(f"✅ Создано {len(demo_games)} демо-матчей для тестирования")
        return
    
    enriched_games = []
    
    for idx, game in enumerate(games, 1):
        home_team = game["home_team"]
        away_team = game["visitor_team"]
        
        print(f"\n📊 {idx}/{len(games)}: {home_team['full_name']} vs {away_team['full_name']}")
        
        home_games = fetch_team_stats(home_team["id"], 15)
        away_games = fetch_team_stats(away_team["id"], 15)
        h2h_games = fetch_h2h_stats(home_team["id"], away_team["id"], 5)
        
        home_avg = calculate_average_points(home_games, home_team["id"])
        away_avg = calculate_average_points(away_games, away_team["id"])
        h2h_avg = calculate_h2h_average(h2h_games)
        
        predicted_total = round((home_avg * 0.3) + (away_avg * 0.3) + (h2h_avg * 0.4), 2)
        
        enriched_games.append({
            "game_id": game["id"],
            "date": game["date"],
            "home_team": {
                "id": home_team["id"],
                "name": home_team["full_name"],
                "abbreviation": home_team["abbreviation"]
            },
            "away_team": {
                "id": away_team["id"],
                "name": away_team["full_name"],
                "abbreviation": away_team["abbreviation"]
            },
            "home_stats": {
                "avg_points": home_avg,
                "games_analyzed": len(home_games)
            },
            "away_stats": {
                "avg_points": away_avg,
                "games_analyzed": len(away_games)
            },
            "h2h_stats": {
                "avg_total": h2h_avg,
                "games_analyzed": len(h2h_games)
            },
            "predicted_total": predicted_total
        })
        
        print(f"   📈 Прогноз: {predicted_total}")
        time.sleep(1)
    
    master_cache["data"] = enriched_games
    master_cache["last_update"] = datetime.now().isoformat()
    print("\n" + "=" * 50)
    print(f"✅ Обновлено! {len(enriched_games)} матчей")

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    if master_cache["data"] is None:
        return jsonify({
            "error": "Data is loading, please try again in 30 seconds",
            "status": "loading"
        }), 503
    
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
        "cache_age": master_cache["last_update"],
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0
    })

@app.route('/debug', methods=['GET'])
def debug():
    """Тестовый эндпоинт для проверки API ключа"""
    test_url = f"{BASE_URL}/teams"
    headers = {"Authorization": API_KEY}
    try:
        response = requests.get(test_url, headers=headers, timeout=10)
        return jsonify({
            "api_key_test": response.status_code,
            "message": "API works" if response.status_code == 200 else "API key problem"
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "NBA Total Predictor API",
        "version": "1.0.0",
        "current_season": CURRENT_SEASON,
        "endpoints": {
            "/upcoming_with_stats": "GET - Получить матчи",
            "/health": "GET - Статус",
            "/debug": "GET - Проверить API ключ"
        }
    })

# Запускаем планировщик
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_master_cache, trigger="interval", hours=1)
scheduler.start()

if __name__ == '__main__':
    print("🏀 NBA Total Predictor Server Starting...")
    print("=" * 50)
    print(f"📅 Текущий сезон: {CURRENT_SEASON}")
    print(f"🔑 API Key: {API_KEY[:10]}...")
    update_master_cache()
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Сервер на порту {port}")
    app.run(host='0.0.0.0', port=port)
