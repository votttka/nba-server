import requests
import datetime
import time
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Твой API Ключ
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

# Кэш в памяти сервера, чтобы не "долбить" API при каждом запуске приложения пользователем
# Структура: { "TEAM_ABBR": {"data": {...}, "timestamp": 123456789} }
GLOBAL_STATS_CACHE = {}
CACHE_TTL = 3600  # Данные хранятся 1 час, потом обновляются

def get_team_stats_safe(team_id, team_abbr):
    """
    Берет статистику команды. Сначала проверяет кэш. 
    Если в кэше пусто или данные устарели — делает запрос к API.
    """
    now = time.time()
    
    # 1. Проверяем кэш
    if team_abbr in GLOBAL_STATS_CACHE:
        cache_entry = GLOBAL_STATS_CACHE[team_abbr]
        if now - cache_entry['timestamp'] < CACHE_TTL:
            print(f">>> [CACHE] {team_abbr} взят из памяти")
            return cache_entry['data']

    # 2. Если в кэше нет, идем в API
    print(f">>> [API] Запрос статистики для {team_abbr}...")
    
    # ПАУЗА 2 секунды. Это критически важно, чтобы не поймать бан от API 
    # (лимит 30 запросов в минуту)
    time.sleep(2) 
    
    params = {"team_ids[]": [team_id], "per_page": 15}
    try:
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            games = r.json().get("data", [])
            # Считаем тоталы только для завершенных матчей
            totals = [g["home_team_score"] + g["visitor_team_score"] for g in games if g.get("home_team_score") is not None]
            
            if totals:
                stats_data = {
                    "avg": round(sum(totals) / len(totals), 1),
                    "last10": [float(x) for x in totals[:10]]
                }
                # Сохраняем в кэш
                GLOBAL_STATS_CACHE[team_abbr] = {
                    'data': stats_data,
                    'timestamp': now
                }
                return stats_data
    except Exception as e:
        print(f"!!! Ошибка при запросе {team_abbr}: {e}")
    
    return {"avg": 0.0, "last10": []}

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    """Главный эндпоинт для Splash-экрана: Грузит игры на 5 дней + статы"""
    try:
        today = datetime.date.today()
        start_date = today.isoformat()
        end_date = (today + datetime.timedelta(days=4)).isoformat()
        
        # Шаг 1: Получаем список всех игр на ближайшие 5 дней
        print(f"--- Запрос расписания с {start_date} по {end_date} ---")
        params = {"start_date": start_date, "end_date": end_date}
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
        
        if r.status_code != 200:
            print(f"Ошибка API при получении расписания: {r.status_code}")
            return jsonify([])

        games_list = r.json().get("data", [])
        if not games_list:
            return jsonify([])

        # Шаг 2: Выделяем уникальные команды, чтобы не запрашивать одну и ту же дважды
        unique_teams = {}
        for g in games_list:
            unique_teams[g["home_team"]["id"]] = g["home_team"]["abbreviation"]
            unique_teams[g["visitor_team"]["id"]] = g["visitor_team"]["abbreviation"]

        # Шаг 3: Собираем статистику для каждой уникальной команды
        stats_map = {}
        for t_id, t_abbr in unique_teams.items():
            stats_map[t_abbr] = get_team_stats_safe(t_id, t_abbr)

        # Шаг 4: Формируем финальный массив для Android
        result_payload = []
        for g in games_list:
            h_abbr = g["home_team"]["abbreviation"]
            a_abbr = g["visitor_team"]["abbreviation"]
            
            result_payload.append({
                "homeTeam": h_abbr,
                "awayTeam": a_abbr,
                "startTime": f"{g['date'][8:10]}.{g['date'][5:7]} | {g['status']}",
                "homeStats": stats_map.get(h_abbr),
                "awayStats": stats_map.get(a_abbr)
            })

        print(f"--- Сбор данных завершен. Отправлено {len(result_payload)} матчей ---")
        return jsonify(result_payload)

    except Exception as e:
        print(f"Критическая ошибка сервера: {e}")
        return jsonify([])

@app.route('/teams', methods=['GET'])
def get_teams():
    """Оставляем для совместимости, но теперь он почти не нужен"""
    return jsonify({"teams": [{"abbreviation": "CACHE", "fullName": "Using Preloaded Data"}]})

@app.route('/')
def home():
    return "NBA Betting Server: Online", 200

if __name__ == '__main__':
    # На локалке запускается на 10000 порту
    app.run(host='0.0.0.0', port=10000)
