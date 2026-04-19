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
    """Качает последние матчи и считает средний тотал"""
    params = {"team_ids[]": [t_id], "per_page": 15}
    try:
        res = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            games = res.json().get("data", [])
            totals = []
            for g in games:
                h_s = g.get("home_team_score")
                v_s = g.get("visitor_team_score")
                if h_s and v_s:
                    totals.append(h_s + v_s)
            
            if totals:
                return {
                    "avg": round(sum(totals) / len(totals), 1),
                    "last10": [float(x) for x in totals[:10]]
                }
    except:
        pass
    return {"avg": 0.0, "last10": []}

@app.route('/')
def home():
    return "NBA Server: Online", 200

@app.route('/teams', methods=['GET'])
def get_teams():
    r = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    if r.status_code == 200:
        data = r.json().get("data", [])
        return jsonify({"teams": [{"abbreviation": t["abbreviation"], "fullName": t["full_name"]} for t in data]})
    return jsonify({"teams": []})

@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    """Эндпоинт для Splash Screen: грузит игры и статистику сразу"""
    today = datetime.date.today().isoformat()
    # Берем 15 ближайших игр
    params = {"per_page": 15, "start_date": today}
    
    r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    if r.status_code != 200:
        return jsonify([])

    raw_data = r.json().get("data", [])
    upcoming = [g for g in raw_data if g.get("period") == 0 and "Final" not in g.get("status", "")]
    
    full_data = []
    local_cache = {}

    for g in upcoming:
        h_id = g["home_team"]["id"]
        a_id = g["visitor_team"]["id"]
        h_abbr = g["home_team"]["abbreviation"]
        a_abbr = g["visitor_team"]["abbreviation"]

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

# Старые эндпоинты оставляем временно для совместимости (чтобы не было 404 в логах)
@app.route('/upcoming_matches', methods=['GET'])
def old_upcoming():
    return jsonify([]) # Можно вернуть пустой список, если перешел на новую версию

@app.route('/match_stats', methods=['GET'])
def old_stats():
    return jsonify({"error": "Use upcoming_with_stats"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
