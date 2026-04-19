import os
import requests
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Твой API ключ
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

def get_stats_for_team(t_id):
    """Вспомогательная функция для получения средних показателей команды"""
    params = {"team_ids[]": [t_id], "per_page": 15}
    try:
        res = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            games = res.json().get("data", [])
            totals = [g["home_team_score"] + g["visitor_team_score"] for g in games if g.get("home_team_score")]
            if totals:
                return {
                    "avg": round(sum(totals) / len(totals), 1),
                    "last10": [float(x) for x in totals[:10]]
                }
    except Exception as e:
        print(f"Error fetching team {t_id}: {e}")
    return {"avg": 0.0, "last10": []}

@app.route('/')
def home():
    return "NBA Betting Server is Online", 200

@app.route('/teams', methods=['GET'])
def get_teams():
    r = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    if r.status_code == 200:
        data = r.json().get("data", [])
        return jsonify({"teams": [{"abbreviation": t["abbreviation"], "fullName": t["full_name"]} for t in data]})
    return jsonify({"teams": []})

# --- НОВЫЙ ЭНДПОИНТ ДЛЯ SPLASH (ВСЁ В ОДНОМ) ---
@app.route('/upcoming_with_stats', methods=['GET'])
def get_upcoming_with_stats():
    today = datetime.date.today().isoformat()
    params = {"per_page": 15, "start_date": today}
    
    r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    if r.status_code != 200:
        return jsonify([])

    raw_data = r.json().get("data", [])
    upcoming = [g for g in raw_data if g.get("period") == 0 and "Final" not in g.get("status", "")]
    
    full_data = []
    local_cache = {}

    for g in upcoming:
        h_id, a_id = g["home_team"]["id"], g["visitor_team"]["id"]
        h_abbr, a_abbr = g["home_team"]["abbreviation"], g["visitor_team"]["abbreviation"]

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

# --- СТАРЫЙ ЭНДПОИНТ ДЛЯ СОВМЕСТИМОСТИ (ЧТОБЫ НЕ БЫЛО 404) ---
@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    today = datetime.date.today().isoformat()
    params = {"per_page": 25, "start_date": today}
    r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    
    matches = []
    if r.status_code == 200:
        data = r.json().get("data", [])
        for g in data:
            if g.get("period") == 0 and "Final" not in g.get("status", ""):
                d = g.get("date", "")
                date_str = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else "TBD"
                matches.append({
                    "homeTeam": g["home_team"]["abbreviation"],
                    "awayTeam": g["visitor_team"]["abbreviation"],
                    "startTime": f"{date_str} | {g.get('status', 'Scheduled')}"
                })
    return jsonify(matches)

# --- СТАРЫЙ ЭНДПОИНТ ДЛЯ СТАТИСТИКИ ---
@app.route('/match_stats', methods=['GET'])
def get_stats():
    h_abbr = request.args.get('home')
    a_abbr = request.args.get('away')
    
    # Ищем ID команд по их аббревиатурам
    r_teams = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    h_id, a_id = None, None
    if r_teams.status_code == 200:
        for t in r_teams.json().get("data", []):
            if t["abbreviation"] == h_abbr: h_id = t["id"]
            if t["abbreviation"] == a_abbr: a_id = t["id"]
    
    if h_id and a_id:
        h_data = get_stats_for_team(h_id)
        a_data = get_stats_for_team(a_id)
        return jsonify({
            "home": {"last10": {"avgTotal": h_data["avg"], "last10Totals": h_data["last10"]}},
            "away": {"last10": {"avgTotal": a_data["avg"], "last10Totals": a_data["last10"]}},
            "headToHead": {"avgTotal": round((h_data["avg"] + a_data["avg"]) / 2, 1)}
        })
    return jsonify({"error": "Teams not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
