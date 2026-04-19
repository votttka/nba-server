import os
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Твой API ключ (убедись, что он прописан в настройках Render или здесь)
API_KEY = "твой_ключ_здесь" 
headers = {"Authorization": API_KEY}

def api_request(url, params=None, retries=3):
    """
    Безопасная функция запроса. 
    Если лимит превышен, она подождет и попробует снова, но не более 3 раз.
    """
    for i in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            
            if response.status_code == 429:
                print(f"⚠️ Лимит запросов (429). Попытка {i+1}/{retries}. Спим 5 сек...")
                time.sleep(5)
                continue # Идем на следующую итерацию цикла
                
            print(f"❌ Ошибка сервера {response.status_code}: {response.text}")
            return None

        except Exception as e:
            print(f"🔥 Ошибка сети: {e}")
            time.sleep(2)
    
    return None # Если за 3 попытки не вышло, возвращаем пустоту

@app.route('/')
def home():
    return "NBA Betting Server is Running!"

@app.route('/teams', methods=['GET'])
def get_teams():
    # Balldontlie отдает данные в ключе "data"
    raw_data = api_request("https://api.balldontlie.io/v1/teams")
    
    if raw_data and "data" in raw_data:
        # Трансформируем под формат, который ждет Android
        formatted_teams = []
        for team in raw_data["data"]:
            formatted_teams.append({
                "abbreviation": team.get("abbreviation"),
                "full_name": team.get("full_name")
            })
        return jsonify({"teams": formatted_teams})
    
    return jsonify({"teams": []}), 500

@app.route('/upcoming_matches', methods=['GET'])
def get_matches():
    # Пример эндпоинта для матчей (можешь подправить под свои нужды)
    raw_data = api_request("https://api.balldontlie.io/v1/games", params={"per_page": 10})
    
    matches = []
    if raw_data and "data" in raw_data:
        for game in raw_data["data"]:
            matches.append({
                "homeTeam": game["home_team"]["abbreviation"],
                "awayTeam": game["visitor_team"]["abbreviation"],
                "startTime": game["status"]
            })
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    home = request.args.get('home')
    away = request.args.get('away')
    
    # Здесь должна быть твоя логика сбора статистики
    # Для примера отдаем структуру, которую ждет Android:
    mock_stats = {
        "home": {"last10": {"avgTotal": 110.5, "last10Totals": [105.0, 112.0, 115.0, 108.0, 110.0, 109.0, 111.0, 113.0, 107.0, 115.0]}},
        "away": {"last10": {"avgTotal": 108.2, "last10Totals": [102.0, 110.0, 105.0, 107.0, 109.0, 112.0, 106.0, 110.0, 108.0, 103.0]}},
        "headToHead": {"avgTotal": 218.5}
    }
    return jsonify(mock_stats)

if __name__ == '__main__':
    # На Render порт берется из переменной окружения
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
