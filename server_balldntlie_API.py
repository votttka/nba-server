import requests
import datetime
import time
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b" # Твой ключ
headers = {"Authorization": API_KEY}

def get_team_stats_safe(team_id):
    """Берет последние 15 игр команды. С паузой для обхода лимитов API."""
    time.sleep(2) # ПАУЗА 2 секунды, чтобы соблюдать лимит 30 запросов в минуту
    params = {"team_ids[]": [team_id], "per_page": 15}
    try:
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            games = r.json().get("data", [])
            # Считаем только реально завершенные матчи со счетом
            totals = [g["home_team_score"] + g["visitor_team_score"] for g in games if g.get("home_team_score")]
            if totals:
                return {"avg": round(sum(totals) / len(totals), 1), "last10": [float(x) for x in totals[:10]]}
    except Exception as e:
        print(f"Ошибка получения статы для команды {team_id}: {e}")
    return {"avg": 0.0, "last10": []}

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    """ЭНДПОИНТ ДЛЯ SPLASH: Грузит игры на 5 дней + статы по каждой команде"""
    try:
        start_date = datetime.date.today().isoformat()
        end_date = (datetime.date.today() + datetime.timedelta(days=4)).isoformat()
        
        # 1. Получаем список матчей
        params = {"start_date": start_date, "end_date": end_date}
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
        
        if r.status_code != 200:
            return jsonify([])

        games_list = r.json().get("data", [])
        if not games_list:
            return jsonify([])

        # 2. Собираем уникальные ID команд, чтобы не запрашивать одну команду дважды
        unique_teams = {}
        for g in games_list:
            unique_teams[g["home_team"]["id"]] = g["home_team"]["abbreviation"]
            unique_teams[g["visitor_team"]["id"]] = g["visitor_team"]["abbreviation"]

        # 3. Собираем статистику по каждой уникальной команде (с паузами)
        stats_cache = {}
        for t_id, t_abbr in unique_teams.items():
            print(f"Загрузка статистики для {t_abbr}...")
            stats_cache[t_abbr] = get_team_stats_safe(t_id)

        # 4. Формируем финальный пакет данных
        result_payload = []
        for g in games_list:
            h_abbr = g["home_team"]["abbreviation"]
            a_abbr = g["visitor_team"]["abbreviation"]
            
            result_payload.append({
                "homeTeam": h_abbr,
                "awayTeam": a_abbr,
                "startTime": f"{g['date'][8:10]}.{g['date'][5:7]} | {g['status']}",
                "homeStats": stats_cache.get(h_abbr),
                "awayStats": stats_cache.get(a_abbr)
            })

        return jsonify(result_payload)
    except Exception as e:
        print(f"Ошибка сервера: {e}")
        return jsonify([])

@app.route('/teams', methods=['GET'])
def get_teams():
    """Список всех команд (теперь работает стабильно)"""
    r = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    if r.status_code == 200:
        return jsonify({"teams": [{"abbreviation": t["abbreviation"], "fullName": t["full_name"]} for t in r.json().get("data", [])]})
    return jsonify({"teams": []})

@app.route('/')
def home():
    return "NBA Preload Engine: Ready", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
