import os
import requests
import datetime
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
    return "NBA Betting Server v3.0 - Online"

@app.route('/teams', methods=['GET'])
def get_teams():
    raw_data = api_request("https://api.balldontlie.io/v1/teams")
    if raw_data and "data" in raw_data:
        teams = [{"abbreviation": t.get("abbreviation"), "fullName": t.get("full_name")} for t in raw_data["data"]]
        return jsonify({"teams": teams})
    return jsonify({"teams": []})

@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    # Запрашиваем игры текущего периода
    current_year = datetime.datetime.now().year
    raw_data = api_request("https://api.balldontlie.io/v1/games", params={"seasons[]": [current_year-1, current_year], "per_page": 50})
    
    matches = []
    if raw_data and "data" in raw_data:
        # Сортируем по дате, чтобы предстоящие были видны
        for game in raw_data["data"]:
            home = game.get("home_team", {}).get("abbreviation")
            away = game.get("visitor_team", {}).get("abbreviation")
            if home and away:
                d = game.get("date", "")
                date_str = f"{d[8:10]}.{d[5:7]}" if len(d) > 10 else "TBD"
                matches.append({
                    "homeTeam": home,
                    "awayTeam": away,
                    "startTime": f"{date_str} | {game.get('status', 'Scheduled')}"
                })
    
    # Если API молчит, даем дефолтную пару, чтобы не ломать UI
    if not matches:
        matches.append({"homeTeam": "LAL", "awayTeam": "GSW", "startTime": "No Live Data"})
    
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    home_abbr = request.args.get('home')
    away_abbr = request.args.get('away')
    
    current_year = datetime.datetime.now().year
    # Ищем статистику в текущем и прошлом сезоне, чтобы точно были данные
    h_totals, a_totals = [], []
    
    # Делаем два запроса для надежности
    for year in [current_year - 1, current_year]:
        params = {"seasons[]": [year], "per_page": 100}
        raw_games = api_request("https://api.balldontlie.io/v1/games", params=params)
        
        if raw_games and "data" in raw_games:
            for g in raw_games["data"]:
                h_s = g.get("home_team_score")
                v_s = g.get("visitor_team_score")
                
                # Нам нужны только игры, которые уже закончились (счет > 0)
                if h_s and v_s and (h_s + v_s > 0):
                    total = h_s + v_s
                    if g["home_team"]["abbreviation"] == home_abbr or g["visitor_team"]["abbreviation"] == home_abbr:
                        h_totals.append(total)
                    if g["home_team"]["abbreviation"] == away_abbr or g["visitor_team"]["abbreviation"] == away_abbr:
                        a_totals.append(total)

    # Если нашли хоть какие-то данные
    if h_totals and a_totals:
        avg_h = sum(h_totals) / len(h_totals)
        avg_a = sum(a_totals) / len(a_totals)
        return jsonify({
            "home": {"last10": {"avgTotal": avg_h, "last10Totals": h_totals[-10:]}},
            "away": {"last10": {"avgTotal": avg_a, "last10Totals": a_totals[-10:]}},
            "headToHead": {"avgTotal": (avg_h + avg_a) / 2}
        })

    # Если данных совсем нет (например, для новых команд или сбой API)
    return jsonify({"error": "No stats found for these teams"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
