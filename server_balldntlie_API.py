import os
import time
import requests
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Твой API ключ
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

def api_request(url, params=None):
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"API Error: {e}")
        return None

@app.route('/')
def home():
    return "NBA Betting Server 2026 (Full Season Mode) is Online"

@app.route('/teams', methods=['GET'])
def get_teams():
    raw_data = api_request("https://api.balldontlie.io/v1/teams")
    if raw_data and "data" in raw_data:
        # Поле fullName для корректной работы с твоим MainActivity.kt
        teams = [{"abbreviation": t.get("abbreviation"), "fullName": t.get("full_name")} for t in raw_data["data"]]
        return jsonify({"teams": teams})
    return jsonify({"teams": []})

@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    # Определяем текущий год программно
    now = datetime.datetime.now()
    current_year = now.year
    prev_year = current_year - 1
    
    # Запрашиваем игры за предыдущий и текущий годы (сезон на стыке лет)
    params = {
        "seasons[]": [prev_year, current_year], 
        "per_page": 50
    }
    
    raw_data = api_request("https://api.balldontlie.io/v1/games", params=params)
    
    matches = []
    if raw_data and "data" in raw_data:
        # Сортируем: самые новые игры будут вверху списка
        sorted_games = sorted(raw_data["data"], key=lambda x: x.get("date", ""), reverse=True)
        
        for game in sorted_games:
            d = game.get("date", "")
            formatted_date = f"{d[8:10]}.{d[5:7]}" if len(d) > 10 else "N/A"
            status = game.get("status", "TBD")
            
            matches.append({
                "homeTeam": game["home_team"]["abbreviation"],
                "awayTeam": game["visitor_team"]["abbreviation"],
                "startTime": f"{formatted_date} | {status}"
            })
            
            # Ограничиваем список 30 матчами, чтобы не перегружать телефон
            if len(matches) >= 30:
                break
    
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    home_abbr = request.args.get('home')
    away_abbr = request.args.get('away')
    
    # Берем последние 80 игр для анализа статистики команд
    raw_games = api_request("https://api.balldontlie.io/v1/games", params={"per_page": 80})
    
    home_totals = []
    away_totals = []
    
    if raw_games and "data" in raw_games:
        for g in raw_games["data"]:
            h_score = g.get("home_team_score")
            v_score = g.get("visitor_team_score")
            
            # Считаем только реально завершенные матчи со счетом
            if h_score and v_score:
                total = h_score + v_score
                if g["home_team"]["abbreviation"] == home_abbr or g["visitor_team"]["abbreviation"] == home_abbr:
                    home_totals.append(total)
                if g["home_team"]["abbreviation"] == away_abbr or g["visitor_team"]["abbreviation"] == away_abbr:
                    away_totals.append(total)

    # Если по какой-то из команд данных нет — 404 (никаких фейковых прогнозов)
    if not home_totals or not away_totals:
        return jsonify(None), 404

    avg_home = sum(home_totals) / len(home_totals)
    avg_away = sum(away_totals) / len(away_totals)
    
    return jsonify({
        "home": {
            "last10": {"avgTotal": avg_home, "last10Totals": home_totals[-10:]}
        },
        "away": {
            "last10": {"avgTotal": avg_away, "last10Totals": away_totals[-10:]}
        },
        "headToHead": {"avgTotal": (avg_home + avg_away) / 2}
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
