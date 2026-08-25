"""
SQLite layer for the Game of 55 cup tracker (Lambda Chi Alpha edition).

This logs a whole game at once: one "games" row per game (date, session,
team names, who won, who logged it) plus one "game_players" row per
player on either roster (their name, team, and cups made). One brother
can log an entire game -- both rosters and every score -- right after it
happens, instead of every player needing to open the app themselves.

Averages, win rate, and history are all computed by grouping
game_players rows by player_name, joined back to their parent game to
figure out who won.

Note: if this app is deployed on a host with an ephemeral filesystem
(like Render's free tier), this SQLite file may reset whenever the app
restarts or wakes from sleep. See the README for details.
"""
import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cup55.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_date TEXT NOT NULL,
                session_label TEXT,
                team_a_name TEXT,
                team_b_name TEXT,
                winner TEXT,
                logged_by TEXT,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
                team TEXT NOT NULL,
                player_name TEXT NOT NULL,
                cups_made INTEGER NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def add_game(game_date, session_label, team_a_name, team_b_name, winner, logged_by,
             team_a_players, team_b_players):
    """team_a_players / team_b_players: list of (player_name, cups_made) tuples."""
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO games
               (game_date, session_label, team_a_name, team_b_name, winner, logged_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (game_date, (session_label or "").strip() or None,
             (team_a_name or "").strip() or None, (team_b_name or "").strip() or None,
             winner, (logged_by or "").strip() or None, time.time()),
        )
        game_id = cur.lastrowid
        for team, players in (("A", team_a_players), ("B", team_b_players)):
            for name, cups in players:
                conn.execute(
                    "INSERT INTO game_players (game_id, team, player_name, cups_made) VALUES (?, ?, ?, ?)",
                    (game_id, team, name.strip(), cups),
                )
        conn.commit()
        return game_id
    finally:
        conn.close()


def delete_game(game_id, logged_by):
    """Only lets the person who logged a game delete it (typo/misclick fix) --
    matched by name since there's no real login system here."""
    conn = _connect()
    try:
        row = conn.execute("SELECT logged_by FROM games WHERE id = ?", (game_id,)).fetchone()
        if row is None or (row["logged_by"] or "").strip().lower() != logged_by.strip().lower():
            return False
        conn.execute("DELETE FROM game_players WHERE game_id = ?", (game_id,))
        cur = conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def all_games():
    conn = _connect()
    try:
        games = conn.execute(
            "SELECT * FROM games ORDER BY game_date DESC, created_at DESC"
        ).fetchall()
        players = conn.execute(
            "SELECT * FROM game_players ORDER BY id ASC"
        ).fetchall()
        by_game = {}
        for p in players:
            by_game.setdefault(p["game_id"], []).append(dict(p))
        result = []
        for g in games:
            gd = dict(g)
            roster = by_game.get(g["id"], [])
            gd["team_a_players"] = [p for p in roster if p["team"] == "A"]
            gd["team_b_players"] = [p for p in roster if p["team"] == "B"]
            result.append(gd)
        return result
    finally:
        conn.close()


def player_names():
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT player_name FROM game_players ORDER BY player_name COLLATE NOCASE"
        ).fetchall()
        return [r["player_name"] for r in rows]
    finally:
        conn.close()
