import os
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# API KEY
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

def api_request(url, params=None, retries=3):
    for i in range(retries):
        try:
            # Send request to balldontlie
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            
            if response.status_code == 429:
                print(f"Rate limit hit. Attempt {i+1}/{retries}. Sleeping 5s...")
                time.sleep(5)
                continue
                
            print(f"API Error {response.status_code}")
            return None

        except Exception as e:
            print(f"Network error: {e}")
            time.sleep(2)
    
    return None

@app.route('/')
def home():
    return "NBA Betting Server is Running!"

@app.route('/teams', methods=['GET'])
def get_teams():
    raw_data = api_request("https://api.balldontlie.io/v1/teams")
    
    if raw_data and "data" in raw_data:
        formatted_teams = []
        for team in raw_data["data"]:
            formatted_teams.append({
                "abbreviation": team.get("abbreviation"),
                "full_name": team.get("full_name")
            })
        return jsonify({"teams": formatted_teams})
    
    return jsonify({"teams": []}), 500

@app.route('/match_stats', methods=['GET'])
def get_stats():
    # Mock stats for Android app logic
    mock_stats = {
        "home": {"last10": {"avgTotal": 110.5, "last10Totals": [105.0, 112.0, 115.0, 108.0, 110.0, 109.0, 111.0, 113.0, 107.0, 115.0]}},
        "away": {"last10": {"avgTotal": 108.2, "last10Totals": [102.0, 110.0, 105.0, 107.0, 109.0, 112.0, 106.0, 110.0, 108.0, 103.0]}},
        "headToHead": {"avgTotal": 218.5}
    }
    return jsonify(mock_stats)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
