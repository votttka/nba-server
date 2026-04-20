import os
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_SPORTS_KEY")
BASE_URL = "https://v1.basketball.api-sports.io"

@app.route('/matches', methods=['GET'])
def get_matches():
    if not API_KEY:
        return jsonify({"error": "API_SPORTS_KEY not set"}), 500
    
    all_matches = []
    today = datetime.now()
    
    for i in range(2):
        date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"{BASE_URL}/games"
        params = {"date": date}
        headers = {"x-apisports-key": API_KEY}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            # Логируем статус и тип ответа
            print(f"Date {date}: status {response.status_code}, content-type: {response.headers.get('content-type')}")
            
            # Пытаемся распарсить JSON
            try:
                data = response.json()
            except Exception as json_err:
                # Если не JSON, возвращаем текст ошибки как есть
                return jsonify({
                    "error": "API returned non-JSON response",
                    "status": response.status_code,
                    "body": response.text[:500]
                }), 500
            
            # Проверяем, что data - словарь
            if not isinstance(data, dict):
                return jsonify({
                    "error": "API response is not a dict",
                    "type": str(type(data)),
                    "body": str(data)[:500]
                }), 500
            
            # Проверяем наличие поля response
            if "response" not in data:
                return jsonify({
                    "error": "No 'response' field in API response",
                    "data_keys": list(data.keys()) if isinstance(data, dict) else None,
                    "full_response": data
                }), 500
            
            games = data["response"]
            if not isinstance(games, list):
                return jsonify({
                    "error": "'response' is not a list",
                    "response_type": str(type(games))
                }), 500
            
            for game in games:
                status = game.get("status", {}).get("long", "")
                if status not in ["Not Started", "Scheduled"]:
                    continue
                home = game.get("teams", {}).get("home", {})
                away = game.get("teams", {}).get("visitors", {})
                all_matches.append({
                    "id": game.get("id"),
                    "date": game.get("date", {}).get("start", ""),
                    "league": game.get("league", {}).get("name", "Unknown"),
                    "home_team": {
                        "id": home.get("id"),
                        "name": home.get("name"),
                        "abbreviation": home.get("code", "")
                    },
                    "away_team": {
                        "id": away.get("id"),
                        "name": away.get("name"),
                        "abbreviation": away.get("code", "")
                    }
                })
        except Exception as e:
            return jsonify({"error": f"Request failed: {str(e)}"}), 500
    
    return jsonify({
        "success": True,
        "matches": all_matches,
        "total": len(all_matches)
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "api_key_set": bool(API_KEY),
        "api_key_preview": API_KEY[:5] + "..." if API_KEY else None
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
