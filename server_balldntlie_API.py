from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Настройки API
API_KEY = "ff4db192-c9ea-4b22-a0af-8e8c6ae93b7b"
HEADERS = {"Authorization": API_KEY}
DELAY = 1.2 

def api_request(url, params=None):
    """Безопасный запрос к API с обработкой лимитов"""
    time.sleep(DELAY)
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print("⚠️ Лимит запросов (429). Спим 5 секунд...")
            time.sleep(5)
            return api_request(url, params)
        return None
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return None

def get_team_id(team_abbr):
    data = api_request("https://api.balldontlie.io/v1/teams")
    if data:
        for team in data.get('data', []):
            if team.get('abbreviation') == team_abbr.upper():
                return team.get('id'), team.get('full_name')
    return None, None

def get_team_stats(team_abbr):
    team_id, team_name = get_team_id(team_abbr)
    if not team_id: return None

    # Ищем игры в сезонах 2024 и 2025
    params = {'team_ids[]': team_id, 'seasons[]': [2024, 2025], 'per_page': 50}
    data = api_request("https://api.balldontlie.io/v1/games", params)

    if not data or not data.get('data'): return {'error': 'No data'}

    # Берем только завершенные матчи
    games = [g for g in data['data'] if g.get('home_team_score') and g.get('visitor_team_score')]
    games.sort(key=lambda x: x['date'], reverse=True)
    
    totals = [g['home_team_score'] + g['visitor_team_score'] for g in games[:10]]
    
    return {
        'team_id': team_id,
        'team_name': team_name,
        'totals': totals,
        'count': len(totals)
    }

def get_h2h_stats(id1, id2):
    params = {'team_ids[]': id1, 'opponent_team_ids[]': id2, 'seasons[]': [2024, 2025]}
    data = api_request("https://api.balldontlie.io/v1/games", params)
    if not data or not data.get('data'): return []
    games = [g for g in data['data'] if g.get('home_team_score') and g.get('visitor_team_score')]
    return [g['home_team_score'] + g['visitor_team_score'] for g in games]

@app.route('/')
def home():
    return "NBA Server is Running!"

@app.route('/upcoming', methods=['GET'])
def get_upcoming():
    today = datetime.now().strftime('%Y-%m-%d')
    params = {'dates[]': today}
    data = api_request("https://api.balldontlie.io/v1/games", params)
    matches = []
    if data and data.get('data'):
        for g in data['data']:
            matches.append({
                "home_team": g['home_team']['abbreviation'],
                "away_team": g['visitor_team']['abbreviation'],
                "start_time": g['status']
            })
    if not matches:
        matches = [{"home_team": "ATL", "away_team": "MEM", "start_time": "No games today"}]
    return jsonify({"matches": matches})

@app.route('/match_stats', methods=['GET'])
def match_stats():
    home_abbr = request.args.get('home', '').upper()
    away_abbr = request.args.get('away', '').upper()
    
    h_data = get_team_stats(home_abbr)
    a_data = get_team_stats(away_abbr)
    
    if not h_data or not a_data or 'error' in h_data or 'error' in a_data:
        return jsonify({'error': 'Команды не найдены'}), 404

    if h_data['count'] < 5 or a_data['count'] < 5:
        return jsonify({'error': 'МАЛО ДАННЫХ: нужно минимум 5 игр'}), 400

    h2h_totals = get_h2h_stats(h_data['team_id'], a_data['team_id'])
    
    return jsonify({
        'home': {'last_10': {'avg_total': round(sum(h_data['totals'])/h_data['count'], 1), 'last_10_totals': h_data['totals']}},
        'away': {'last_10': {'avg_total': round(sum(a_data['totals'])/a_data['count'], 1), 'last_10_totals': a_data['totals']}},
        'head_to_head': {
            'avg_total': round(sum(h2h_totals)/len(h2h_totals), 1) if h2h_totals else 0,
            'games_count': len(h2h_totals)
        }
    })

@app.route('/teams', methods=['GET'])
def get_teams():
    data = api_request("https://api.balldontlie.io/v1/teams")
    teams = []
    if data:
        for t in data.get('data', []):
            teams.append({'abbreviation': t['abbreviation'], 'full_name': t['full_name']})
    return jsonify({'teams': teams})

# ВАЖНО: Настройка порта для Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)