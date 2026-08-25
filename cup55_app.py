"""
Cup Tracker -- Flask app for tracking average cups made per person across
games of 55 (cup pong with 55 cups per side).

Each player logs their own result from their own phone right after a game
-- their name, how many cups they made, who/what they played against, and
whether they won -- and the app aggregates everyone's entries into a
leaderboard (average cups made per game, win rate, total games) plus a
full history you can filter by session.

Run locally with:  python cup55_app.py
Then open:          http://127.0.0.1:5001

When deployed to a host like Render, the PORT environment variable is set
automatically by the host and the app binds to 0.0.0.0 so it's reachable
from outside (e.g. from everyone's phones), not just from one computer.
"""
import os
import time
from datetime import date

from flask import Flask, jsonify, request, send_from_directory

import cup55_db as db

app = Flask(__name__, static_folder=None)

MAX_CUPS = 55


@app.route("/")
def index():
    return send_from_directory(".", "cup55_index.html")


def _validate_entry(data):
    player_name = str(data.get("player_name", "")).strip()
    if not player_name:
        return None, "Enter your name."

    try:
        cups_made = int(data.get("cups_made"))
    except (TypeError, ValueError):
        return None, "Cups made needs to be a number."
    if cups_made < 0 or cups_made > MAX_CUPS:
        return None, f"Cups made has to be between 0 and {MAX_CUPS}."

    game_date = str(data.get("game_date") or "").strip() or date.today().isoformat()

    won_raw = data.get("won")
    if won_raw in (True, "true", "1", 1):
        won = 1
    elif won_raw in (False, "false", "0", 0):
        won = 0
    else:
        won = None  # not recorded / unknown

    entry = {
        "player_name": player_name,
        "cups_made": cups_made,
        "opponent_name": data.get("opponent_name"),
        "team_name": data.get("team_name"),
        "won": won,
        "game_date": game_date,
        "session_label": data.get("session_label"),
    }
    return entry, None


@app.route("/api/games", methods=["GET"])
def api_list_games():
    return jsonify({"entries": db.all_entries()})


@app.route("/api/games", methods=["POST"])
def api_add_game():
    data = request.get_json(silent=True) or {}
    entry, error = _validate_entry(data)
    if error:
        return jsonify({"error": error}), 400

    entry_id = db.add_entry(
        entry["player_name"], entry["cups_made"], entry["opponent_name"],
        entry["team_name"], entry["won"], entry["game_date"], entry["session_label"],
    )
    return jsonify({"ok": True, "id": entry_id})


@app.route("/api/games/<int:entry_id>", methods=["DELETE"])
def api_delete_game(entry_id):
    data = request.get_json(silent=True) or {}
    player_name = str(data.get("player_name", "")).strip()
    if not player_name:
        return jsonify({"error": "Missing player_name."}), 400
    deleted = db.delete_entry(entry_id, player_name)
    if not deleted:
        return jsonify({"error": "Entry not found, or it isn't yours to delete."}), 404
    return jsonify({"ok": True})


@app.route("/api/players")
def api_players():
    return jsonify({"players": db.player_names()})


@app.route("/api/stats")
def api_stats():
    entries = db.all_entries()
    by_player = {}
    for e in entries:
        name = e["player_name"]
        stats = by_player.setdefault(name, {
            "player_name": name,
            "games_played": 0,
            "total_cups": 0,
            "wins": 0,
            "losses": 0,
            "unrecorded_results": 0,
        })
        stats["games_played"] += 1
        stats["total_cups"] += e["cups_made"]
        if e["won"] == 1:
            stats["wins"] += 1
        elif e["won"] == 0:
            stats["losses"] += 1
        else:
            stats["unrecorded_results"] += 1

    leaderboard = []
    for stats in by_player.values():
        games = stats["games_played"]
        avg_cups = round(stats["total_cups"] / games, 2) if games else 0
        decided_games = stats["wins"] + stats["losses"]
        win_rate = round(stats["wins"] / decided_games * 100, 1) if decided_games else None
        leaderboard.append({
            **stats,
            "avg_cups": avg_cups,
            "win_rate": win_rate,
        })

    leaderboard.sort(key=lambda s: (-s["avg_cups"], -s["games_played"]))
    return jsonify({"leaderboard": leaderboard, "max_cups": MAX_CUPS})


if __name__ == "__main__":
    db.init_db()
    # PORT is set automatically by cloud hosts (e.g. Render). Locally it
    # falls back to 5001. Binding to 0.0.0.0 (instead of 127.0.0.1) lets
    # the app accept connections from other devices, like everyone's phones.
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
