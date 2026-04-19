import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

def api_request(url, params=None):
    try:
        response = requests.get(url, params=params, headers=headers)
        return response.json() if response.status_code == 200 else None
    except:
        return None

@app.route('/')
def home():
    return "NBA Betting Server is Active"

@app.route('/teams', methods=['GET'])
def get_teams():
    raw_data = api_request("https://api.balldontlie.io/v1/teams")
    if raw_data and "data" in raw_data:
        # Принудительно проверяем наличие имен
        teams = []
        for t in raw_data["data"]:
            abbr = t.get("abbreviation")
            full = t.get("full_name")
            if abbr and full:
                teams.append({"abbreviation": abbr, "fullName": full})
        return jsonify({"teams": teams})
    return jsonify({"teams": []})

@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    # Запрашиваем без фильтров по сезонам, берем последние игры
    raw_data = api_request("https://api.balldontlie.io/v1/games", params={"per_page": 50})
    matches = []
    if raw_data and "data" in raw_data:
        for game in raw_data["data"]:
            home = game.get("home_team", {}).get("abbreviation")
            away = game.get("visitor_team", {}).get("abbreviation")
            
            # Если команды есть, добавляем в список
            if home and away:
                d = game.get("date", "")
                date_str = f"{d[8:10]}.{d[5:7]}" if len(d) > 10 else "TBD"
                matches.append({
                    "homeTeam": home,
                    "awayTeam": away,
                    "startTime": f"{date_str} | {game.get('status', 'Scheduled')}"
                })
    
    # Если список пуст, шлем хотя бы одну заглушку, чтобы приложение не тупило
    if not matches:
        matches.append({"homeTeam": "LAL", "awayTeam": "GSW", "startTime": "No Data"})
        
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    home_abbr = request.args.get('home')
    away_abbr = request.args.get('away')
    raw_games = api_request("https://api.balldontlie.io/v1/games", params={"per_page": 100})
    
    h_totals, a_totals = [], []
    if raw_games and "data" in raw_games:
        for g in raw_games["data"]:
            h_s = g.get("home_team_score")
            v_s = g.get("visitor_team_score")
            if h_s and v_s and (h_s + v_s > 0):
                total = h_s + v_s
                if g["home_team"]["abbreviation"] == home_abbr or g["visitor_team"]["abbreviation"] == home_abbr:
                    h_totals.append(total)
                if g["home_team"]["abbreviation"] == away_abbr or g["visitor_team"]["abbreviation"] == away_abbr:
                    a_totals.append(total)

    if not h_totals or not a_totals:
        return jsonify(None), 404

    return jsonify({
        "home": {"last10": {"avgTotal": sum(h_totals)/len(h_totals), "last10Totals": h_totals[-10:]}},
        "away": {"last10": {"avgTotal": sum(a_totals)/len(a_totals), "last10Totals": a_totals[-10:]}},
        "headToHead": {"avgTotal": (sum(h_totals)/len(h_totals) + sum(a_totals)/len(a_totals)) / 2}
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
