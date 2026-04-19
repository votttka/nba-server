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
    return "NBA Server Online"

@app.route('/teams', methods=['GET'])
def get_teams():
    raw_data = api_request("https://api.balldontlie.io/v1/teams")
    # Возвращаем fullName, как того требует твой MainActivity
    if raw_data and "data" in raw_data:
        teams = [{"abbreviation": t.get("abbreviation"), "fullName": t.get("full_name")} for t in raw_data["data"]]
        return jsonify({"teams": teams})
    return jsonify({"teams": []})

@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    # Запрашиваем последние 50 игр без жестких фильтров сезона, чтобы API не тупил
    raw_data = api_request("https://api.balldontlie.io/v1/games", params={"per_page": 50})
    matches = []
    if raw_data and "data" in raw_data:
        for game in raw_data["data"]:
            d = game.get("date", "")
            # Берем только актуальные/будущие сезоны (2025 и 2026)
            if "2025" in d or "2026" in d:
                date_str = f"{d[8:10]}.{d[5:7]}" if len(d) > 10 else "TBD"
                matches.append({
                    "homeTeam": game["home_team"]["abbreviation"],
                    "awayTeam": game["visitor_team"]["abbreviation"],
                    "startTime": f"{date_str} | {game.get('status', '')}"
                })
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    home_abbr = request.args.get('home')
    away_abbr = request.args.get('away')
    raw_games = api_request("https://api.balldontlie.io/v1/games", params={"per_page": 100})
    
    h_totals, a_totals = [], []
    if raw_games and "data" in raw_games:
        for g in raw_games["data"]:
            h_s, v_s = g.get("home_team_score"), g.get("visitor_team_score")
            if h_s and v_s and (h_s + v_s > 0):
                total = h_s + v_s
                if g["home_team"]["abbreviation"] == home_abbr or g["visitor_team"]["abbreviation"] == home_abbr:
                    h_totals.append(total)
                if g["home_team"]["abbreviation"] == away_abbr or g["visitor_team"]["abbreviation"] == away_abbr:
                    a_totals.append(total)

    if not h_totals or not a_totals:
        return jsonify(None), 404

    avg_h, avg_a = sum(h_totals)/len(h_totals), sum(a_totals)/len(a_totals)
    return jsonify({
        "home": {"last10": {"avgTotal": avg_h, "last10Totals": h_totals[-10:]}},
        "away": {"last10": {"avgTotal": avg_a, "last10Totals": a_totals[-10:]}},
        "headToHead": {"avgTotal": (avg_h + avg_a) / 2}
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
