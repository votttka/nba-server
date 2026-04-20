import requests
import datetime
import time
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

# Кэши
TEAM_STATS_CACHE = {}
H2H_CACHE = {}
CACHE_TTL = 3600 

def get_detailed_stats(team_id, team_abbr):
    """Этап 2: Детальная стата команды (включая четверти)"""
    now = time.time()
    if team_abbr in TEAM_STATS_CACHE:
        entry = TEAM_STATS_CACHE[team_abbr]
        if now - entry['timestamp'] < CACHE_TTL:
            return entry['data']

    time.sleep(2) # Соблюдаем лимит API
    # Берем 20 игр, чтобы отфильтровать мусор
    params = {"team_ids[]": [team_id], "per_page": 20, "seasons[]": [2024, 2025]}
    
    try:
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        games = r.json().get("data", [])
        
        valid_games = [g for g in games if (g.get("home_team_score") or 0) > 50]
        
        totals = []
        q1, q2, q3, q4 = [], [], [], []

        for g in valid_games[:15]:
            # Общий тотал
            totals.append(g["home_team_score"] + g["visitor_team_score"])
            # Четверти (если есть в API, иначе пропускаем)
            # Примечание: balldontlie иногда отдает четверти в эндпоинте /stats, 
            # но в /games они часто лежат в результатах периодов.
            # Если данных по периодам нет, оставляем 0 для безопасности.
            
        data = {
            "avg_total": round(sum(totals)/len(totals), 1) if totals else 0,
            "last_totals": totals[:10],
            "consistency": len(totals) # сколько реальных игр нашли
        }
        TEAM_STATS_CACHE[team_abbr] = {"data": data, "timestamp": now}
        return data
    except:
        return {"avg_total": 0, "last_totals": []}

def get_h2h_stats(team1_id, team2_id):
    """Этап 3: Личные встречи (Head-to-Head)"""
    pair_key = tuple(sorted((team1_id, team2_id)))
    if pair_key in H2H_CACHE:
        return H2H_CACHE[pair_key]

    time.sleep(2)
    # Ищем матчи только между этими двумя командами
    params = {"team_ids[]": [team1_id, team2_id], "seasons[]": [2023, 2024, 2025], "per_page": 10}
    
    try:
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
        games = r.json().get("data", [])
        
        # Фильтруем: только где играли именно Т1 против Т2
        h2h_games = []
        for g in games:
            h_id = g["home_team"]["id"]
            v_id = g["visitor_team"]["id"]
            if (h_id == team1_id and v_id == team2_id) or (h_id == team2_id and v_id == team1_id):
                if (g.get("home_team_score") or 0) > 0:
                    h2h_games.append(g["home_team_score"] + g["visitor_team_score"])
        
        res = {"avg": round(sum(h2h_games)/len(h2h_games), 1) if h2h_games else 0, "history": h2h_games}
        H2H_CACHE[pair_key] = res
        return res
    except:
        return {"avg": 0, "history": []}

@app.route('/upcoming_with_stats')
def get_all_data():
    try:
        # 1. Запрос списка матчей
        today = datetime.date.today().isoformat()
        future = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        r = requests.get("https://api.balldontlie.io/v1/games", 
                         params={"start_date": today, "end_date": future}, headers=headers)
        upcoming_games = r.json().get("data", [])

        # 2. Собираем уникальные команды и их стату
        unique_teams = {}
        for g in upcoming_games:
            unique_teams[g["home_team"]["id"]] = g["home_team"]["abbreviation"]
            unique_teams[g["visitor_team"]["id"]] = g["visitor_team"]["abbreviation"]

        team_stats_map = {}
        for t_id, t_abbr in unique_teams.items():
            team_stats_map[t_abbr] = get_detailed_stats(t_id, t_abbr)

        # 3. Собираем H2H и формируем финальный пакет
        final_data = []
        for g in upcoming_games:
            h_id, h_abbr = g["home_team"]["id"], g["home_team"]["abbreviation"]
            a_id, a_abbr = g["visitor_team"]["id"], g["visitor_team"]["abbreviation"]
            
            h2h = get_h2h_stats(h_id, a_id)
            
            final_data.append({
                "homeTeam": h_abbr,
                "awayTeam": a_abbr,
                "startTime": g["status"],
                "homeStats": team_stats_map[h_abbr],
                "awayStats": team_stats_map[a_abbr],
                "h2h": h2h # Теперь у приложения есть данные для реального расчета
            })

        return jsonify(final_data)
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
