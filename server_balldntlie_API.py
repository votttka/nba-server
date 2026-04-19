import os
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Твой API ключ
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

def api_request(url, params=None, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429: # Ограничение частоты запросов
                time.sleep(5)
                continue
            return None
        except:
            time.sleep(2)
    return None

@app.route('/')
def home():
    return "NBA Betting Server is Online!"

@app.route('/teams', methods=['GET'])
def get_teams():
    raw_data = api_request("https://api.balldontlie.io/v1/teams")
    if raw_data and "data" in raw_data:
        teams = [{"abbreviation": t.get("abbreviation"), "full_name": t.get("full_name")} for t in raw_data["data"]]
        return jsonify({"teams": teams})
    return jsonify({"teams": []})

# ТОТ САМЫЙ ЭНДПОИНТ, КОТОРОГО НЕ ХВАТАЛО
@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    # Запрашиваем игры. В бесплатном API даты могут быть ограничены,
    # поэтому если данных нет, мы вернем "заглушку", чтобы ты мог проверить спиннер.
    raw_data = api_request("https://api.balldontlie.io/v1/games", params={"per_page": 10})
    
    matches = []
    if raw_data and "data" in raw_data:
        for game in raw_data["data"]:
            matches.append({
                "homeTeam": game["home_team"]["abbreviation"],
                "awayTeam": game["visitor_team"]["abbreviation"],
                "startTime": game.get("status", "TBD")
            })
    
    # Если матчей в API на сегодня нет, добавим один тестовый, чтобы спиннер ожил
    if not matches:
        matches.append({
            "homeTeam": "LAL",
            "awayTeam": "GSW",
            "startTime": "Test Match"
        })
        
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    # Заглушка для статистики, чтобы приложение не падало при расчете
    return jsonify({
        "home": {"last10": {"avgTotal": 110.5, "last10Totals": [110, 112, 108]}},
        "away": {"last10": {"avgTotal": 108.2, "last10Totals": [105, 115, 102]}},
        "headToHead": {"avgTotal": 215.0}
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
