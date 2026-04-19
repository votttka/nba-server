import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

@app.route('/')
def home():
    # Эта строка нужна, чтобы Splash Screen понимал, что сервер жив
    return "Server is Online"

@app.route('/teams', methods=['GET'])
def get_teams():
    r = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    if r.status_code == 200:
        data = r.json().get("data", [])
        teams = [{"abbreviation": t["abbreviation"], "fullName": t["full_name"]} for t in data]
        return jsonify({"teams": teams})
    return jsonify({"teams": []})

@app.route('/upcoming_matches', methods=['GET'])
def get_upcoming_matches():
    # Берем последние 50 игр без жестких фильтров по датам, чтобы не ломать выдачу
    r = requests.get("https://api.balldontlie.io/v1/games", params={"per_page": 50}, headers=headers)
    matches = []
    if r.status_code == 200:
        data = r.json().get("data", [])
        for g in data:
            # Форматируем дату обратно в человеческий вид (ДД.ММ)
            raw_date = g.get("date", "2026-01-01")
            formatted_date = f"{raw_date[8:10]}.{raw_date[5:7]}"
            
            matches.append({
                "homeTeam": g["home_team"]["abbreviation"],
                "awayTeam": g["visitor_team"]["abbreviation"],
                "startTime": f"{formatted_date} | {g.get('status', '')}"
            })
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    h_abbr = request.args.get('home')
    a_abbr = request.args.get('away')
    
    # Берем большую пачку игр для расчета
    r = requests.get("https://api.balldontlie.io/v1/games", params={"per_page": 100}, headers=headers)
    
    h_totals, a_totals = [], []
    if r.status_code == 200:
        data = r.json().get("data", [])
        for g in data:
            h_score = g.get("home_team_score", 0)
            v_score = g.get("visitor_team_score", 0)
            
            if h_score and v_score: # Считаем только если игра завершена
                total = h_score + v_score
                if g["home_team"]["abbreviation"] == h_abbr or g["visitor_team"]["abbreviation"] == h_abbr:
                    h_totals.append(total)
                if g["home_team"]["abbreviation"] == a_abbr or g["visitor_team"]["abbreviation"] == a_abbr:
                    a_totals.append(total)

    if h_totals and a_totals:
        return jsonify({
            "home": {"last10": {"avgTotal": sum(h_totals)/len(h_totals), "last10Totals": h_totals[-10:]}},
            "away": {"last10": {"avgTotal": sum(a_totals)/len(a_totals), "last10Totals": a_totals[-10:]}},
            "headToHead": {"avgTotal": (sum(h_totals)/len(h_totals) + sum(a_totals)/len(a_totals)) / 2}
        })
    return jsonify({"error": "No data"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
