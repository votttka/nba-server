import os
import requests
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Твой ключ API
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

def get_stats_for_team(t_id):
    """Вспомогательная функция: тянет последние 15 игр для конкретной команды"""
    params = {"team_ids[]": [t_id], "per_page": 15}
    try:
        res = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            games = res.json().get("data", [])
            # Считаем сумму очков в каждой игре
            totals = [g["home_team_score"] + g["visitor_team_score"] for g in games if g.get("home_team_score")]
            if totals:
                return {
                    "avg": round(sum(totals) / len(totals), 1),
                    "last10": totals[:10]
                }
    except Exception as e:
        print(f"Error fetching stats for team {t_id}: {e}")
    return {"avg": 0, "last10": []}

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    """Главный эндпоинт для Splash Activity"""
    today = datetime.date.today().isoformat()
    params = {"per_page": 15, "start_date": today}
    
    r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    if r.status_code != 200:
        return jsonify([])

    raw_data = r.json().get("data", [])
    # Оставляем только те матчи, которые еще не начались
    upcoming = [g for g in raw_data if g.get("period") == 0 and "Final" not in g.get("status", "")]
    
    full_data = []
    local_cache = {} # Чтобы не качать стату дважды для одной и той же команды

    for g in upcoming:
        h_id, a_id = g["home_team"]["id"], g["visitor_team"]["id"]
        h_abbr, a_abbr = g["home_team"]["abbreviation"], g["visitor_team"]["abbreviation"]

        # Если статы этой команды еще нет в этом запросе — качаем
        if h_abbr not in local_cache: local_cache[h_abbr] = get_stats_for_team(h_id)
        if a_abbr not in local_cache: local_cache[a_abbr] = get_stats_for_team(a_id)

        d = g.get("date", "")
        date_str = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else "TBD"

        full_data.append({
            "homeTeam": h_abbr,
            "awayTeam": a_abbr,
            "startTime": f"{date_str} | {g.get('status', 'Scheduled')}",
            "homeStats": local_cache[h_abbr],
            "awayStats": local_cache[a_abbr]
        })
    
    return jsonify(full_data)

@app.route('/teams', methods=['GET'])
def get_teams():
    """Оставляем для проверки связи (пинга)"""
    r = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    return jsonify(r.json()) if r.status_code == 200 else jsonify({"teams": []})

if __name__ == '__main__':
    # Порт 10000 для Render
    app.run(host='0.0.0.0', port=10000)
