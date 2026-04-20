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

# Кэши с TTL 3600 секунд (1 час)
TEAM_STATS_CACHE = OrderedDict()
H2H_CACHE = OrderedDict()
CACHE_TTL = 3600

# Глобальный кэш для ответа /upcoming_with_stats
master_cache = {"data": None, "last_update": None}

def fetch_games_for_next_4_days():
    """Получает список матчей на ближайшие 4 дня"""
    today = datetime.now().date()
    end_date = today + timedelta(days=4)
    
    all_games = []
    for i in range(5):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        url = f"{BASE_URL}/games"
        params = {"dates[]": date_str, "per_page": 100}
        headers = {"Authorization": API_KEY}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                games = response.json().get("data", [])
                all_games.extend(games)
                print(f"✅ Загружено {len(games)} игр на {date_str}")
            else:
                print(f"❌ Ошибка {response.status_code} для {date_str}")
            time.sleep(0.5)  # Пауза, чтобы не превысить лимит API
        except Exception as e:
            print(f"❌ Ошибка при загрузке игр за {date_str}: {e}")
    
    return all_games

def fetch_team_stats(team_id, limit=15):
    """Получает последние 15 игр команды"""
    cache_key = f"team_{team_id}_limit_{limit}"
    if cache_key in TEAM_STATS_CACHE:
        cached_time, data = TEAM_STATS_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            print(f"📦 Кэш для команды {team_id}")
            return data
    
    url = f"{BASE_URL}/games"
    params = {
        "team_ids[]": team_id,
        "per_page": limit,
        "seasons[]": 2024
    }
    headers = {"Authorization": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            games = response.json().get("data", [])
            TEAM_STATS_CACHE[cache_key] = (time.time(), games)
            print(f"✅ Загружено {len(games)} игр для команды {team_id}")
            return games
    except Exception as e:
        print(f"❌ Ошибка при загрузке статистики команды {team_id}: {e}")
    return []

def calculate_average_points(games, team_id):
    """Рассчитывает среднее количество очков команды за последние игры"""
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
    cache_key = f"h2h_{min(team1_id, team2_id)}_{max(team1_id, team2_id)}"
    if cache_key in H2H_CACHE:
        cached_time, data = H2H_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            print(f"📦 Кэш H2H для {team1_id} vs {team2_id}")
            return data
    
    url = f"{BASE_URL}/games"
    params = {
        "team_ids[]": f"{team1_id},{team2_id}",
        "per_page": limit,
        "seasons[]": 2024
    }
    headers = {"Authorization": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            games = response.json().get("data", [])
            H2H_CACHE[cache_key] = (time.time(), games)
            print(f"✅ Загружено {len(games)} личных встреч")
            return games
    except Exception as e:
        print(f"❌ Ошибка при загрузке H2H: {e}")
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
    """Обновляет главный кэш со статистикой всех матчей"""
    print("🔄 Начинаю обновление кэша...")
    print("=" * 50)
    
    games = fetch_games_for_next_4_days()
    if not games:
        print("❌ Не найдено игр для обновления")
        return
    
    enriched_games = []
    total_teams = len(games) * 2
    
    for idx, game in enumerate(games, 1):
        home_team = game["home_team"]
        away_team = game["visitor_team"]
        
        print(f"\n📊 Обработка матча {idx}/{len(games)}:")
        print(f"   {home_team['full_name']} vs {away_team['full_name']}")
        
        # Получаем статистику
        home_games = fetch_team_stats(home_team["id"], 15)
        away_games = fetch_team_stats(away_team["id"], 15)
        h2h_games = fetch_h2h_stats(home_team["id"], away_team["id"], 5)
        
        # Рассчитываем средние
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
        
        print(f"   📈 Прогноз тотала: {predicted_total}")
        print(f"   🏠 {home_team['abbreviation']} среднее: {home_avg}")
        print(f"   ✈️ {away_team['abbreviation']} среднее: {away_avg}")
        print(f"   🤝 Личные встречи средний тотал: {h2h_avg}")
        
        # Небольшая пауза между командами, чтобы не превысить лимит
        time.sleep(1)
    
    master_cache["data"] = enriched_games
    master_cache["last_update"] = datetime.now().isoformat()
    print("\n" + "=" * 50)
    print(f"✅ Кэш обновлён! Обработано {len(enriched_games)} матчей")
    print(f"🕐 Время обновления: {master_cache['last_update']}")

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    """Эндпоинт для мобильного приложения"""
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
    """Эндпоинт для проверки здоровья сервера"""
    return jsonify({
        "status": "healthy",
        "cache_age": master_cache["last_update"],
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0
    })

@app.route('/', methods=['GET'])
def index():
    """Корневой эндпоинт"""
    return jsonify({
        "service": "NBA Total Predictor API",
        "version": "1.0.0",
        "endpoints": {
            "/upcoming_with_stats": "GET - Получить матчи со статистикой",
            "/health": "GET - Проверить статус сервера"
        }
    })

# Запускаем планировщик для обновления кэша каждый час
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_master_cache, trigger="interval", hours=1)
scheduler.start()

if __name__ == '__main__':
    print("🏀 NBA Total Predictor Server Starting...")
    print("=" * 50)
    # При старте сразу обновляем кэш
    update_master_cache()
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)
