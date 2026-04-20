import os
import requests
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

def get_stats_for_team(t_id):
    """Качает последние 15 игр для расчета среднего тотала"""
    params = {"team_ids[]": [t_id], "per_page": 15}
    try:
        res = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            games = res.json().get("data", [])
            # Считаем сумму очков только там, где игра завершена
            totals = [g["home_team_score"] + g["visitor_team_score"] for g in games if g.get("home_team_score") is not None]
            if totals:
                return {"avg": round(sum(totals) / len(totals), 1), "last10": [float(x) for x in totals[:10]]}
    except: pass
    return {"avg": 0.0, "last10": []}

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    """Эндпоинт для Splash: грузит только актуальные матчи со статистикой"""
    try:
        # Ставим дату начала на "вчера", чтобы не потерять матчи из-за разницы поясов
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        
        # Берем 50 записей, чтобы хватило на несколько дней вперед
        params = {"per_page": 50, "start_date": yesterday}
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=15)
        
        if r.status_code != 200:
            return jsonify([])

        raw_data = r.json().get("data", [])
        
        # ФИЛЬТР: оставляем только те матчи, которые еще не закончились (счета нет)
        upcoming = [g for g in raw_data if g.get("home_team_score") is None or g.get("home_team_score") == 0]
        
        # Если вдруг из-за конца сезона список пуст, берем просто 5 последних из выдачи (для теста)
        if not upcoming:
            upcoming = raw_data[:5]

        full_data = []
        local_cache = {}

        for g in upcoming:
            h_id, a_id = g["home_team"]["id"], g["visitor_team"]["id"]
            h_abbr, a_abbr = g["home_team"]["abbreviation"], g["visitor_team"]["abbreviation"]

            # Кэшируем статы, чтобы не качать одно и то же по 10 раз для разных матчей
            if h_abbr not in local_cache: local_cache[h_abbr] = get_stats_for_team(h_id)
            if a_abbr not in local_cache: local_cache[a_abbr] = get_stats_for_team(a_id)

            d = g.get("date", "")
            date_display = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else "TBD"

            full_data.append({
                "homeTeam": h_abbr,
                "awayTeam": a_abbr,
                "startTime": f"{date_display} | {g.get('status', 'Upcoming')}",
                "homeStats": local_cache[h_abbr],
                "awayStats": local_cache[a_abbr]
            })
        return jsonify(full_data)
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify([])

@app.route('/teams', methods=['GET'])
def get_teams():
    r = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    if r.status_code == 200:
        data = r.json().get("data", [])
        return jsonify({"teams": [{"abbreviation": t["abbreviation"], "fullName": t["full_name"]} for t in data]})
    return jsonify({"teams": []})

@app.route('/')
def home():
    return "NBA Preload Server: Active", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
