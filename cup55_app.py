"""
Cup Tracker -- Lambda Chi Alpha edition. Flask app for tracking average
cups made per person across games of 55 (cup pong with 55 cups per side).

One brother logs an entire game at once, right after it happens: both
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
import os
from datetime import date

from flask import Flask, jsonify, request, send_from_directory

import cup55_db as db

app = Flask(__name__, static_folder=None)

MAX_CUPS = 55
MIN_TEAM_SIZE = 2
MAX_TEAM_SIZE = 5


@app.route("/")
def index():
    return send_from_directory(".", "cup55_index.html")


def _validate_roster(raw_players, label):
    if not isinstance(raw_players, list):
        return None, f"{label} roster is missing."
    if not (MIN_TEAM_SIZE <= len(raw_players) <= MAX_TEAM_SIZE):
        return None, f"{label} needs between {MIN_TEAM_SIZE} and {MAX_TEAM_SIZE} players."

    players = []
    for p in raw_players:
        name = str((p or {}).get("player_name", "")).strip()
        if not name:
            return None, f"Every player on {label} needs a name."
        try:
            cups = int((p or {}).get("cups_made"))
        except (TypeError, ValueError):
            return None, f"{name}'s cups made needs to be a number."
        if cups < 0 or cups > MAX_CUPS:
            return None, f"{name}'s cups made has to be between 0 and {MAX_CUPS}."
        players.append((name, cups))
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

    game = {
        "game_date": game_date,
        "session_label": data.get("session_label"),
        "team_a_name": (data.get("team_a_name") or "").strip() or "Team A",
        "team_b_name": (data.get("team_b_name") or "").strip() or "Team B",
        "winner": winner,
        "logged_by": logged_by,
        "team_a_players": team_a_players,
        "team_b_players": team_b_players,
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
    )
    return jsonify({"ok": True, "id": game_id})


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
                    "wins": 0,
                    "losses": 0,
                    "unrecorded_results": 0,
                })
                stats["games_played"] += 1
                stats["total_cups"] += p["cups_made"]
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
        decided = stats["wins"] + stats["losses"]
        win_rate = round(stats["wins"] / decided * 100, 1) if decided else None
        leaderboard.append({**stats, "avg_cups": avg_cups, "win_rate": win_rate})

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
