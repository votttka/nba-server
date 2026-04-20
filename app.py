import os
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app)

API_KEY = "b0c40eeb-3722-40bf-b190-8a47bd87a69d"
BASE_URL = "https://api.balldontlie.io/v1"

master_cache = {"data": None, "last_update": None, "loading": False}

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
                print(f"   ❌ Ошибка: {response.text[:100]}")
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
    
    return all_games

def fetch_team_stats(team_id, limit=15):
    """Получает последние 15 игр команды"""
    url = f"{BASE_URL}/games"
    params = {
        "team_ids[]": team_id,
        "per_page": limit,
        "seasons[]": 2025
    }
    headers = {"Authorization": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            games = response.json().get("data", [])
            print(f"   📊 Команда {team_id}: {len(games)} игр")
            return games
        return []
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return []

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

def fetch_h2h_stats(team1_id, team2_id, limit=5):
    """Получает историю личных встреч"""
    url = f"{BASE_URL}/games"
    params = {
        "team_ids[]": f"{team1_id},{team2_id}",
        "per_page": limit,
        "seasons[]": 2025
    }
    headers = {"Authorization": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            games = response.json().get("data", [])
            print(f"   🤝 H2H: {len(games)} встреч")
            return games
        return []
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return []

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
    if master_cache["loading"]:
        print("⏳ Обновление уже выполняется")
        return
    
    master_cache["loading"] = True
    print("\n" + "=" * 60)
    print("🔄 НАЧАЛО ОБНОВЛЕНИЯ КЭША")
    print("=" * 60)
    
    games = fetch_games_for_next_4_days()
    
    if not games:
        print("❌ НЕТ ИГР НА БЛИЖАЙШИЕ 4 ДНЯ")
        master_cache["loading"] = False
        return
    
    enriched_games = []
    
    for idx, game in enumerate(games, 1):
        home_team = game["home_team"]
        away_team = game["visitor_team"]
        
        print(f"\n🔍 [{idx}/{len(games)}] {home_team['abbreviation']} vs {away_team['abbreviation']}")
        
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
        
        print(f"   📈 Прогноз: {predicted_total} | H:{home_avg} A:{away_avg} H2H:{h2h_avg}")
        
        time.sleep(0.5)
    
    master_cache["data"] = enriched_games
    master_cache["last_update"] = datetime.now().isoformat()
    master_cache["loading"] = False
    
    print("\n" + "=" * 60)
    print(f"✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО! Обработано {len(enriched_games)} матчей")
    print("=" * 60)

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    if master_cache["data"] is None:
        return jsonify({
            "error": "Data is loading, please wait 30-60 seconds",
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
        "last_update": master_cache["last_update"],
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0,
        "is_loading": master_cache["loading"]
    })

@app.route('/debug', methods=['GET'])
def debug():
    return jsonify({
        "api_key_loaded": True,
        "current_season": 2025,
        "cached_games": len(master_cache["data"]) if master_cache["data"] else 0
    })

# ЗАПУСКАЕМ ОБНОВЛЕНИЕ ПРИ СТАРТЕ
print("🚀 Сервер запускается...")
threading.Thread(target=update_master_cache).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
