"""
Cup Tracker -- Flask app for tracking average cups made per person
across games of 55 (cup pong with 55 cups per side).

One person logs an entire game at once, right after it happens: both
teams' full rosters (2 to 5 players per side), each player's cups made,
and which team won. The app aggregates every logged game into a
leaderboard (average cups made per game, win rate, total games) plus a
full history of every game.

Run locally with:  python cup55_app.py
Then open:          http://127.0.0.1:5001

When deployed to a host like Render, the PORT environment variable is set
automatically by the host and the app binds to 0.0.0.0 so it's reachable
from outside (e.g. from everyone's phones), not just from one computer.
"""
import hmac
import os
import secrets
from datetime import date, timedelta

from flask import Flask, jsonify, request, send_from_directory, session

import cup55_db as db

app = Flask(__name__, static_folder=None)
# Needed to sign the login session cookie. If FLASK_SECRET_KEY isn't set,
# a random one is generated at startup -- that just means everyone's
# session resets (they have to re-enter the passcode) whenever the app
# restarts, same tradeoff as the rest of this app's free-tier hosting.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(days=365)

MAX_CUPS = 55
MIN_TEAM_SIZE = 2
MAX_TEAM_SIZE = 5
MAX_BITCH_CUPS = 55
MAX_DRINKS = 200
MAX_FIRE_COUNT = 55
MAX_BITCH_CUPS_TAKEN = 55

# Optional shared-passcode gate. If SITE_PASSCODE isn't set, the app is
# wide open to anyone with the link (the old behavior) -- no code changes
# needed either way, it just activates once the env var is set on Render.
SITE_PASSCODE = os.environ.get("SITE_PASSCODE")


@app.before_request
def _require_passcode():
    if not SITE_PASSCODE:
        return None
    if request.path in ("/", "/api/login"):
        return None
    if session.get("authed"):
        return None
    return jsonify({"error": "locked", "locked": True}), 401


@app.route("/api/login", methods=["POST"])
def api_login():
    if not SITE_PASSCODE:
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    entered = str(data.get("passcode", ""))
    if entered and hmac.compare_digest(entered, SITE_PASSCODE):
        session.permanent = True
        session["authed"] = True
        return jsonify({"ok": True})
    return jsonify({"error": "Wrong passcode."}), 403


@app.route("/")
def index():
    return send_from_directory(".", "cup55_index.html")


def _optional_nonneg_int(raw, field_label, player_name, cap):
    """Parses an optional per-player stat (bitch cups / drinks / fires):
    blank/missing defaults to 0, otherwise must be a non-negative integer
    up to `cap`."""
    if raw is None or raw == "":
        return 0, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, f"{player_name}'s {field_label} needs to be a number."
    if value < 0 or value > cap:
        return None, f"{player_name}'s {field_label} has to be between 0 and {cap}."
    return value, None


def _validate_roster(raw_players, label):
    if not isinstance(raw_players, list):
        return None, f"{label} roster is missing."
    if not (MIN_TEAM_SIZE <= len(raw_players) <= MAX_TEAM_SIZE):
        return None, f"{label} needs between {MIN_TEAM_SIZE} and {MAX_TEAM_SIZE} players."

    players = []
    for p in raw_players:
        p = p or {}
        name = str(p.get("player_name", "")).strip()
        if not name:
            return None, f"Every player on {label} needs a name."
        try:
            cups = int(p.get("cups_made"))
        except (TypeError, ValueError):
            return None, f"{name}'s cups made needs to be a number."
        if cups < 0 or cups > MAX_CUPS:
            return None, f"{name}'s cups made has to be between 0 and {MAX_CUPS}."

        bitch_made, error = _optional_nonneg_int(p.get("bitch_cups_made"), "bitch cups made", name, MAX_BITCH_CUPS)
        if error:
            return None, error
        bitch_taken, error = _optional_nonneg_int(p.get("bitch_cups_taken"), "bitch cups taken", name, MAX_BITCH_CUPS_TAKEN)
        if error:
            return None, error
        drinks, error = _optional_nonneg_int(p.get("drinks_taken"), "drinks taken", name, MAX_DRINKS)
        if error:
            return None, error
        fire, error = _optional_nonneg_int(p.get("fire_count"), "fire count", name, MAX_FIRE_COUNT)
        if error:
            return None, error

        players.append((name, cups, bitch_made, bitch_taken, drinks, fire))
    return players, None


def _validate_game(data):
    logged_by = str(data.get("logged_by", "")).strip()
    if not logged_by:
        return None, "Enter your name (whoever's logging this game)."

    game_date = str(data.get("game_date") or "").strip() or date.today().isoformat()

    team_a_players, error = _validate_roster(data.get("team_a_players"), "Team A")
    if error:
        return None, error
    team_b_players, error = _validate_roster(data.get("team_b_players"), "Team B")
    if error:
        return None, error

    winner = data.get("winner")
    if winner not in ("A", "B"):
        winner = None

    last_cup_player = str(data.get("last_cup_player") or "").strip() or None
    if last_cup_player:
        roster_names = {p[0].lower() for p in team_a_players + team_b_players}
        if last_cup_player.lower() not in roster_names:
            return None, "Last cup has to be one of the players in this game."

    game = {
        "game_date": game_date,
        "session_label": data.get("session_label"),
        "team_a_name": (data.get("team_a_name") or "").strip() or "Team A",
        "team_b_name": (data.get("team_b_name") or "").strip() or "Team B",
        "winner": winner,
        "logged_by": logged_by,
        "team_a_players": team_a_players,
        "team_b_players": team_b_players,
        "last_cup_player": last_cup_player,
    }
    return game, None


@app.route("/api/games", methods=["GET"])
def api_list_games():
    return jsonify({"games": db.all_games()})


@app.route("/api/games", methods=["POST"])
def api_add_game():
    data = request.get_json(silent=True) or {}
    game, error = _validate_game(data)
    if error:
        return jsonify({"error": error}), 400

    game_id = db.add_game(
        game["game_date"], game["session_label"], game["team_a_name"], game["team_b_name"],
        game["winner"], game["logged_by"], game["team_a_players"], game["team_b_players"],
        game["last_cup_player"],
    )
    return jsonify({"ok": True, "id": game_id})


@app.route("/api/games/<int:game_id>", methods=["PUT"])
def api_update_game(game_id):
    data = request.get_json(silent=True) or {}
    game, error = _validate_game(data)
    if error:
        return jsonify({"error": error}), 400

    updated = db.update_game(
        game_id, game["logged_by"], game["game_date"], game["session_label"],
        game["team_a_name"], game["team_b_name"], game["winner"],
        game["team_a_players"], game["team_b_players"], game["last_cup_player"],
    )
    if not updated:
        return jsonify({"error": "Game not found, or it isn't yours to edit."}), 404
    return jsonify({"ok": True})


@app.route("/api/games/<int:game_id>", methods=["DELETE"])
def api_delete_game(game_id):
    data = request.get_json(silent=True) or {}
    logged_by = str(data.get("logged_by", "")).strip()
    if not logged_by:
        return jsonify({"error": "Missing logged_by."}), 400
    deleted = db.delete_game(game_id, logged_by)
    if not deleted:
        return jsonify({"error": "Game not found, or it isn't yours to delete."}), 404
    return jsonify({"ok": True})


@app.route("/api/players")
def api_players():
    return jsonify({"players": db.player_names()})


@app.route("/api/stats")
def api_stats():
    games = db.all_games()
    by_player = {}
    for g in games:
        for team, roster in (("A", g["team_a_players"]), ("B", g["team_b_players"])):
            if g["winner"] is None:
                won = None
            else:
                won = (g["winner"] == team)
            for p in roster:
                name = p["player_name"]
                stats = by_player.setdefault(name, {
                    "player_name": name,
                    "games_played": 0,
                    "total_cups": 0,
                    "total_bitch_cups_made": 0,
                    "total_bitch_cups_taken": 0,
                    "total_drinks": 0,
                    "total_fires": 0,
                    "total_last_cups": 0,
                    "wins": 0,
                    "losses": 0,
                    "unrecorded_results": 0,
                })
                stats["games_played"] += 1
                stats["total_cups"] += p["cups_made"]
                stats["total_bitch_cups_made"] += p.get("bitch_cups_made", 0) or 0
                stats["total_bitch_cups_taken"] += p.get("bitch_cups_taken", 0) or 0
                stats["total_drinks"] += p.get("drinks_taken", 0) or 0
                stats["total_fires"] += p.get("fire_count", 0) or 0
                last_cup = (g.get("last_cup_player") or "").strip().lower()
                if last_cup and last_cup == name.strip().lower():
                    stats["total_last_cups"] += 1
                if won is True:
                    stats["wins"] += 1
                elif won is False:
                    stats["losses"] += 1
                else:
                    stats["unrecorded_results"] += 1

    leaderboard = []
    for stats in by_player.values():
        games_played = stats["games_played"]
        avg_cups = round(stats["total_cups"] / games_played, 2) if games_played else 0
        avg_bitch_cups_made = round(stats["total_bitch_cups_made"] / games_played, 2) if games_played else 0
        avg_bitch_cups_taken = round(stats["total_bitch_cups_taken"] / games_played, 2) if games_played else 0
        avg_drinks = round(stats["total_drinks"] / games_played, 2) if games_played else 0
        decided = stats["wins"] + stats["losses"]
        win_rate = round(stats["wins"] / decided * 100, 1) if decided else None
        leaderboard.append({
            **stats,
            "avg_cups": avg_cups,
            "avg_bitch_cups_made": avg_bitch_cups_made,
            "avg_bitch_cups_taken": avg_bitch_cups_taken,
            "avg_drinks": avg_drinks,
            "win_rate": win_rate,
        })

    leaderboard.sort(key=lambda s: (-s["avg_cups"], -s["games_played"]))
    return jsonify({
        "leaderboard": leaderboard,
        "max_cups": MAX_CUPS,
        "min_team_size": MIN_TEAM_SIZE,
        "max_team_size": MAX_TEAM_SIZE,
    })


if __name__ == "__main__":
    db.init_db()
    # PORT is set automatically by cloud hosts (e.g. Render). Locally it
    # falls back to 5001. Binding to 0.0.0.0 (instead of 127.0.0.1) lets
    # the app accept connections from other devices, like everyone's phones.
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
