import os
import requests
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

# Хранилище: { "LAL": {"avg": 220, "last10": [...]}, ... }
cache = {"stats": {}}

def get_team_ids_from_upcoming(upcoming_data):
    """Собирает уникальные ID всех команд из списка будущих матчей"""
    team_ids = set()
    for g in upcoming_data:
        team_ids.add(g["home_team"]["id"])
        team_ids.add(g["visitor_team"]["id"])
    return list(team_ids)

def update_cache_for_teams(team_ids):
    """Загружает историю только для конкретных команд из списка"""
    for t_id in team_ids:
        # Берем последние 15 игр для каждой команды, чтобы была выборка
        params = {"team_ids[]": [t_id], "per_page": 15}
        res = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
        
        if res.status_code == 200:
            games = res.json().get("data", [])
            totals = []
            abbr = ""
            for g in games:
                h_s = g.get("home_team_score", 0)
                v_s = g.get("visitor_team_score", 0)
                if h_s and v_s:
                    totals.append(h_s + v_s)
                # Узнаем аббревиатуру команды (нужна для ключа в кэше)
                if not abbr:
                    if g["home_team"]["id"] == t_id: abbr = g["home_team"]["abbreviation"]
                    else: abbr = g["visitor_team"]["abbreviation"]
            
            if totals and abbr:
                cache["stats"][abbr] = {
                    "avg": sum(totals) / len(totals),
                    "last10": totals[:10]
                }

@app.route('/')
def home():
    return "NBA Server: Targeted Cache Mode", 200

@app.route('/teams', methods=['GET'])
def get_teams():
    r = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    if r.status_code == 200:
        data = r.json().get("data", [])
        return jsonify({"teams": [{"abbreviation": t["abbreviation"], "fullName": t["full_name"]} for t in data]})
    return jsonify({"teams": []})

@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    today = datetime.date.today().isoformat()
    params = {"per_page": 50, "start_date": today}
    
    r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    matches = []
    
    if r.status_code == 200:
        raw_data = r.json().get("data", [])
        # Очищаем только от завершенных игр
        upcoming = [g for g in raw_data if g.get("period") == 0 and "Final" not in g.get("status", "")]
        upcoming.sort(key=lambda x: x.get("date", ""))

        # --- КРИТИЧЕСКИЙ МОМЕНТ: ОБНОВЛЯЕМ КЭШ ТОЛЬКО ДЛЯ ЭТИХ КОМАНД ---
        team_ids = get_team_ids_from_upcoming(upcoming)
        update_cache_for_teams(team_ids)
        # --------------------------------------------------------------

        for g in upcoming:
            d = g.get("date", "")
            date_str = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else "TBD"
            matches.append({
                "homeTeam": g["home_team"]["abbreviation"],
                "awayTeam": g["visitor_team"]["abbreviation"],
                "startTime": f"{date_str} | {g.get('status', 'Scheduled')}"
            })
            
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    h_abbr = request.args.get('home')
    a_abbr = request.args.get('away')

    h_data = cache["stats"].get(h_abbr)
    a_data = cache["stats"].get(a_abbr)

    if h_data and a_data:
        return jsonify({
            "home": {"last10": {"avgTotal": h_data["avg"], "last10Totals": h_data["last10"]}},
            "away": {"last10": {"avgTotal": a_data["avg"], "last10Totals": a_data["last10"]}},
            "headToHead": {"avgTotal": (h_data["avg"] + a_data["avg"]) / 2}
        })
    
    return jsonify({"error": f"No stats for {h_abbr} or {a_abbr}"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
