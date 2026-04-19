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
    """Вспомогательная функция для получения цифр по ID"""
    params = {"team_ids[]": [t_id], "per_page": 15}
    res = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    if res.status_code == 200:
        games = res.json().get("data", [])
        totals = [g["home_team_score"] + g["visitor_team_score"] for g in games if g.get("home_team_score")]
        if totals:
            return {"avg": sum(totals) / len(totals), "last10": totals[:10]}
    return {"avg": 0, "last10": []}

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    """Этот метод Splash Activity будет ждать до победного"""
    today = datetime.date.today().isoformat()
    # Берем чуть меньше игр (например, 15), чтобы не ждать вечность на заставке
    params = {"per_page": 15, "start_date": today}
    
    r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    if r.status_code != 200:
        return jsonify([])

    raw_data = r.json().get("data", [])
    upcoming = [g for g in raw_data if g.get("period") == 0 and "Final" not in g.get("status", "")]
    
    full_data = []
    # Кэшируем внутри одного запроса, чтобы не качать дважды для разных матчей
    local_cache = {}

    for g in upcoming:
        h_id = g["home_team"]["id"]
        a_id = g["visitor_team"]["id"]
        h_abbr = g["home_team"]["abbreviation"]
        a_abbr = g["visitor_team"]["abbreviation"]

        if h_abbr not in local_cache:
            local_cache[h_abbr] = get_stats_for_team(h_id)
        if a_abbr not in local_cache:
            local_cache[a_abbr] = get_stats_for_team(a_id)

        d = g.get("date", "")
        date_str = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else "TBD"

        full_data.append({
            "homeTeam": h_abbr,
            "awayTeam": a_abbr,
            "startTime": f"{date_str} | {g.get('status', 'Scheduled')}",
            "stats": {
                "home": local_cache[h_abbr],
                "away": local_cache[a_abbr]
            }
        })
    
    return jsonify(full_data)

# Оставляем старые эндпоинты для совместимости, если нужно
@app.route('/')
def home(): return "Ready", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
