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

API_KEY = "b0c40eeb-3722-40bf-b190-8a47bd87a69d"
BASE_URL = "https://api.balldontlie.io/v1"

# Определяем сезоны: с 2025 по текущий год
CURRENT_YEAR = datetime.now().year
SEASONS = list(range(2025, CURRENT_YEAR + 1))

print(f"📅 Загружаем данные для сезонов: {SEASONS}")

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
            if response.status_code == 200:
                games = response.json().get("data", [])
                all_games.extend(games)
                print(f"   ✅ Найдено {len(games)} игр")
            else:
                print(f"   ❌ Ошибка {response.status_code}")
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    return all_games

def fetch_team_stats(team_id, limit=20):
    """Получает последние игры команды за все сезоны с 2025"""
    cache_key = f"team_{team_id}_seasons_{SEASONS[0]}_{SEASONS[-1]}"
    if cache_key in TEAM_STATS_CACHE:
        cached_time, data = TEAM_STATS_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return data
    
    all_games = []
    
    # Запрашиваем данные для каждого сезона
    for season in SEASONS:
        url = f"{BASE_URL}/games"
        params = {
            "team_ids[]": team_id,
            "per_page": limit,
            "seasons[]": season
        }
        headers = {"Authorization": API_KEY}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                games = response.json().get("data", [])
                all_games.extend(games)
                print(f"   📊 Команда {team_id} сезон {season}: {len(games)} игр")
            time.sleep(0.3)
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    # Сортируем по дате и берем последние limit игр
    all_games.sort(key=lambda x: x["date"], reverse=True)
    all_games = all_games[:limit]
    
    TEAM_STATS_CACHE[cache_key] = (time.time(), all_games)
    return all_games

def calculate_average_points(games, team_id):
    """Рассчитывает среднее количество очков команды"""
    if not games:
        return 0.0
    
    total_points = 0
    count = 0
    
    for game in games:
        if game["home_team"]["id"] == team_id and game["home_team_score"]:
            total_points += game["home_team_score"]
            count += 1
        elif game["visitor_team"]["id"] == team_id and game["visitor_team_score"]:
            total_points += game["visitor_team_score"]
            count += 1
    
    return round(total_points / count, 2) if count > 0 else 0.0

def fetch_h2h_stats(team1_id, team2_id, limit=10):
    """Получает историю личных встреч за все сезоны с 2025"""
    cache_key = f"h2h_{min(team1_id, team2_id)}_{max(team1_id, team2_id)}_seasons_{SEASONS[0]}_{SEASONS[-1]}"
    if cache_key in H2H_CACHE:
        cached_time, data = H2H_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return data
    
    all_games = []
    
    for season in SEASONS:
        url = f"{BASE_URL}/games"
        params = {
            "team_ids[]": f"{team1_id},{team2_id}",
            "per_page": limit,
            "seasons[]": season
        }
        headers = {"Authorization": API_KEY}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                games = response.json().get("data", [])
                all_games.extend(games)
                print(f"   🤝 H2H сезон {season}: {len(games)} встреч")
            time.sleep(0.3)
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    all_games.sort(key=lambda x: x["date"], reverse=True)
    all_games = all_games[:limit]
    
    H2H_CACHE[cache_key] = (time.time(), all_games)
    return all_games

def calculate_h2h_average(games):
    """Рассчитывает средний тотал в личных встречах"""
    if not games:
        return 0.0
    
    total_points = 0
    count = 0
    for game in games:
        if game["home_team_score"] and game["visitor_team_score"]:
            total_points += game["home_team_score"] + game["visitor_team_score"]
            count += 1
    
    return round(total_points / count, 2) if count > 0 else 0.0

def update_master_cache():
    """Обновляет главный кэш"""
    print("\n" + "=" * 60)
    print("🔄 НАЧАЛО ОБНОВЛЕНИЯ КЭША")
    print(f"📅 Сезоны: {SEASONS[0]} - {SEASONS[-1]}")
    print("=" * 60)
    
    games = fetch_games_for_next_4_days()
    
    if not games:
        print("❌ НЕТ ИГР НА БЛИЖАЙШИЕ 4 ДНЯ")
        return
    
    print(f"\n📋 Найдено {len(games)} предстоящих матчей. Обработка...")
    enriched_games = []
    
    for idx, game in enumerate(games, 1):
        home_team = game["home_team"]
        away_team = game["visitor_team"]
        
        print(f"\n🔍 [{idx}/{len(games)}] {home_team['abbreviation']} vs {away_team['abbreviation']}")
        
        home_games = fetch_team_stats(home_team["id"], 20)
        away_games = fetch_team_stats(away_team["id"], 20)
        h2h_games = fetch_h2h_stats(home_team["id"], away_team["id"], 10)
        
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
        
        print(f"   📈 Прогноз: {predicted_total} | H:{home_avg} A:{away_avg} H2H:{h2h_avg}")
        
        time.sleep(0.5)
    
    master_cache["data"] = enriched_games
    master_cache["last_update"] = datetime.now().isoformat()
    
    print("\n" + "=" * 60)
    print(f"✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО! Обработано {len(enriched_games)} матчей")
    print("=" * 60)

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    if master_cache["data"] is None:
        return jsonify({"error": "Data is loading, please try again in 30 seconds", "status": "loading"}), 503
    
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
        "seasons": SEASONS
    })

@app.route('/debug', methods=['GET'])
def debug():
    return jsonify({
        "seasons_loaded": SEASONS,
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0,
        "api_key_configured": True
    })

# Запускаем обновление
print(f"🚀 Сервер запускается. Сезоны для анализа: {SEASONS}")
update_master_cache()

scheduler = BackgroundScheduler()
scheduler.add_job(func=update_master_cache, trigger="interval", hours=1)
scheduler.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
