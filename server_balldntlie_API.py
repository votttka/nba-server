import os
import requests
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

@app.route('/')
def home():
    return "Server Online", 200

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
    """Только БУДУЩИЕ игры для ставок"""
    today = datetime.date.today().isoformat()
    
    # start_date = сегодня. API вернет всё, что запланировано от текущего момента и дальше.
    params = {
        "per_page": 100,
        "start_date": today 
    }
    
    r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
    matches = []
    
    if r.status_code == 200:
        data = r.json().get("data", [])
        
        # Фильтруем только те игры, которые еще не начались (status не содержит очки и не 'Final')
        # И сортируем по дате: ближайшие к нам — в самом верху
        data.sort(key=lambda x: x.get("date", ""))

        for g in data:
            # Пропускаем игры, которые уже завершены, если API их случайно подмешало
            if g.get("period") != 0 or "Final" in g.get("status", ""):
                continue

            d = g.get("date", "")
            date_str = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else "TBD"
            
            matches.append({
                "homeTeam": g["home_team"]["abbreviation"],
                "awayTeam": g["visitor_team"]["abbreviation"],
                "startTime": f"{date_str} | {g.get('status', 'Scheduled')}"
            })
            
    return jsonify(matches)

@app.route('/match_stats', methods=['GET'])
def get_stats():
    """Анализ истории для расчета валуя (берем 100 последних ЛЮБЫХ игр)"""
    h_abbr = request.args.get('home')
    a_abbr = request.args.get('away')
    
    # Для статистики нам как раз нужны прошедшие игры, поэтому тут фильтры по датам не ставим
    r = requests.get("https://api.balldontlie.io/v1/games", params={"per_page": 100}, headers=headers)
    
    h_totals, a_totals = [], []
    if r.status_code == 200:
        data = r.json().get("data", [])
        for g in data:
            h_s = g.get("home_team_score", 0)
            v_s = g.get("visitor_team_score", 0)
            
            if h_s and v_s and (h_s + v_s > 0):
                total = h_s + v_s
                if g["home_team"]["abbreviation"] == h_abbr or g["visitor_team"]["abbreviation"] == h_abbr:
                    h_totals.append(total)
                if g["home_team"]["abbreviation"] == a_abbr or g["visitor_team"]["abbreviation"] == a_abbr:
                    a_totals.append(total)

    if h_totals and a_totals:
        avg_h = sum(h_totals) / len(h_totals)
        avg_a = sum(a_totals) / len(a_totals)
        return jsonify({
            "home": {"last10": {"avgTotal": avg_h, "last10Totals": h_totals[-10:]}},
            "away": {"last10": {"avgTotal": avg_a, "last10Totals": a_totals[-10:]}},
            "headToHead": {"avgTotal": (avg_h + avg_a) / 2}
        })
    return jsonify({"error": "No stats found"}), 404

@app.route('/calculate', methods=['GET'])
def calculate():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
    
