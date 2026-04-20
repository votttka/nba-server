import requests
import datetime
import time
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Твой ключ и заголовки
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
headers = {"Authorization": API_KEY}

# Кэши для экономии лимитов API
TEAM_STATS_CACHE = {}
H2H_CACHE = {}
CACHE_TTL = 3600  # 1 час

def get_detailed_stats(team_id, team_abbr):
    """Запрос детальной статистики команды"""
    now = time.time()
    if team_abbr in TEAM_STATS_CACHE:
        entry = TEAM_STATS_CACHE[team_abbr]
        if now - entry['timestamp'] < CACHE_TTL:
            return entry['data']

    print(f"  [Stats] Загрузка данных для {team_abbr}...")
    time.sleep(1.5)  # Пауза для соблюдения лимитов (уменьшил с 2с до 1.5с)
    
    params = {"team_ids[]": [team_id], "per_page": 20, "seasons[]": [2024, 2025]}
    
    try:
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        games = r.json().get("data", [])
        
        # Фильтруем только завершенные матчи с реальным счетом
        valid_games = [g for g in games if (g.get("home_team_score") or 0) > 50]
        
        totals = []
        for g in valid_games[:15]:
            total = (g.get("home_team_score") or 0) + (g.get("visitor_team_score") or 0)
            if total > 100:
                totals.append(total)
        
        avg_total = round(sum(totals)/len(totals), 1) if totals else 0
        
        data = {
            "avg_total": avg_total,
            "last_totals": totals[:10],
            "consistency": len(totals)
        }
        
        TEAM_STATS_CACHE[team_abbr] = {"data": data, "timestamp": now}
        return data
    except Exception as e:
        print(f"  [Error] Не удалось получить статсу {team_abbr}: {e}")
        return {"avg_total": 0, "last_totals": [], "consistency": 0}

def get_h2h_stats(team1_id, team2_id):
    """Запрос личных встреч (Head-to-Head)"""
    pair_key = tuple(sorted((team1_id, team2_id)))
    if pair_key in H2H_CACHE:
        return H2H_CACHE[pair_key]

    print(f"  [H2H] Загрузка личных встреч {team1_id} vs {team2_id}...")
    time.sleep(1.5)
    
    params = {"team_ids[]": [team1_id, team2_id], "seasons[]": [2023, 2024, 2025], "per_page": 10}
    
    try:
        r = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers, timeout=10)
        games = r.json().get("data", [])
        
        h2h_games = []
        for g in games:
            h_id = g["home_team"]["id"]
            v_id = g["visitor_team"]["id"]
            # Проверяем, что играли именно эти две команды друг против друга
            if (h_id == team1_id and v_id == team2_id) or (h_id == team2_id and v_id == team1_id):
                score_h = g.get("home_team_score") or 0
                score_v = g.get("visitor_team_score") or 0
                if score_h > 0 and score_v > 0:
                    h2h_games.append(score_h + score_v)
        
        avg_h2h = round(sum(h2h_games)/len(h2h_games), 1) if h2h_games else 0
        res = {"avg": avg_h2h, "history": h2h_games}
        
        H2H_CACHE[pair_key] = res
        return res
    except Exception as e:
        print(f"  [Error] Ошибка H2H: {e}")
        return {"avg": 0, "history": []}

@app.route('/upcoming_with_stats')
def get_all_data():
    print(f"\n--- Новый запрос от приложения: {datetime.datetime.now()} ---")
    try:
        # 1. Запрос списка матчей (берем на 4 дня вперед)
        today = datetime.date.today().isoformat()
        future = (datetime.date.today() + datetime.timedelta(days=4)).isoformat()
        
        print(f"1. Запрос расписания с {today} по {future}...")
        r = requests.get("https://api.balldontlie.io/v1/games", 
                         params={"start_date": today, "end_date": future}, headers=headers, timeout=10)
        
        if r.status_code != 200:
            print(f"Ошибка API: {r.status_code}")
            return jsonify({"error": f"API returned {r.status_code}"}), 500

        upcoming_games = r.json().get("data", [])
        print(f"Найдено предстоящих игр: {len(upcoming_games)}")

        if not upcoming_games:
            print("Расписание пусто. Проверьте дату или ключ.")
            return jsonify([])

        # 2. Собираем уникальные команды для получения статистики
        unique_teams = {}
        for g in upcoming_games:
            unique_teams[g["home_team"]["id"]] = g["home_team"]["abbreviation"]
            unique_teams[g["visitor_team"]["id"]] = g["visitor_team"]["abbreviation"]

        print(f"2. Сбор статистики для {len(unique_teams)} уникальных команд...")
        team_stats_map = {}
        for t_id, t_abbr in unique_teams.items():
            team_stats_map[t_abbr] = get_detailed_stats(t_id, t_abbr)

        # 3. Формируем итоговый пакет данных
        print("3. Формирование финального пакета данных...")
        final_data = []
        for g in upcoming_games:
            h_id, h_abbr = g["home_team"]["id"], g["home_team"]["abbreviation"]
            a_id, a_abbr = g["visitor_team"]["id"], g["visitor_team"]["abbreviation"]
            
            # Личные встречи
            h2h = get_h2h_stats(h_id, a_id)
            
            final_data.append({
                "homeTeam": h_abbr,
                "awayTeam": a_abbr,
                "startTime": g.get("status", "Unknown"),
                "homeStats": team_stats_map.get(h_abbr),
                "awayStats": team_stats_map.get(a_abbr),
                "h2h": h2h
            })

        print(f"Успех! Отправлено в приложение {len(final_data)} матчей.")
        return jsonify(final_data)

    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # На Render порт задается переменной окружения
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
