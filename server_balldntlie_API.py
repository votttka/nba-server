@app.route('/match_stats', methods=['GET'])
def get_stats():
    """Статистика для расчета (ищем игры конкретно для выбранных команд)"""
    h_abbr = request.args.get('home')
    a_abbr = request.args.get('away')
    
    if not h_abbr or not a_abbr:
        return jsonify({"error": "Missing team abbreviations"}), 400

    # 1. Получаем ID команд по их аббревиатурам (нужно для точного поиска в API)
    r_teams = requests.get("https://api.balldontlie.io/v1/teams", headers=headers)
    h_id, a_id = None, None
    if r_teams.status_code == 200:
        teams_data = r_teams.json().get("data", [])
        for t in teams_data:
            if t["abbreviation"] == h_abbr: h_id = t["id"]
            if t["abbreviation"] == a_abbr: a_id = t["id"]

    # 2. Запрашиваем последние 25 игр для каждой команды отдельно
    # Это гарантирует, что мы найдем историю, даже если они не играли друг с другом недавно
    h_totals, a_totals = [], []
    
    for team_id in [h_id, a_id]:
        if not team_id: continue
        params = {"team_ids[]": [team_id], "per_page": 25}
        res = requests.get("https://api.balldontlie.io/v1/games", params=params, headers=headers)
        
        if res.status_code == 200:
            games = res.json().get("data", [])
            for g in games:
                h_s = g.get("home_team_score", 0)
                v_s = g.get("visitor_team_score", 0)
                if h_s and v_s:
                    if team_id == h_id: h_totals.append(h_s + v_s)
                    else: a_totals.append(h_s + v_s)

    # 3. Возвращаем результат, если нашли хотя бы что-то
    if h_totals and a_totals:
        avg_h = sum(h_totals) / len(h_totals)
        avg_a = sum(a_totals) / len(a_totals)
        # Для HeadToHead, если общих игр нет в выборке, берем среднее от их средних
        return jsonify({
            "home": {"last10": {"avgTotal": avg_h, "last10Totals": h_totals[:10]}},
            "away": {"last10": {"avgTotal": avg_a, "last10Totals": a_totals[:10]}},
            "headToHead": {"avgTotal": (avg_h + avg_a) / 2}
        })
    
    return jsonify({"error": f"Stats not found for {h_abbr} or {a_abbr}"}), 404
