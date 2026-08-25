"""
Small local SQLite layer for the Game of 55 cup tracker.

game_entries -- one row per player per game. Each player logs their own
result from their own phone after a game finishes, so a single real-world
game of 55 usually produces two rows here (one per side) rather than one
shared "game" record -- that avoids needing any live sync between phones.
Everything (averages, win rate, history) is computed by grouping these
rows by player_name.

Note: if this app is deployed on a host with an ephemeral filesystem (like
Render's free tier), this SQLite file may reset whenever the app restarts
or wakes from sleep. That just means the log starts fresh occasionally --
see the README for how to avoid that if it matters to you.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cup55.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                cups_made INTEGER NOT NULL,
                opponent_name TEXT,
                team_name TEXT,
                won INTEGER,
                game_date TEXT NOT NULL,
                session_label TEXT,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def add_entry(player_name, cups_made, opponent_name, team_name, won, game_date, session_label):
    import time
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO game_entries
               (player_name, cups_made, opponent_name, team_name, won, game_date, session_label, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (player_name.strip(), cups_made, (opponent_name or "").strip() or None,
             (team_name or "").strip() or None, won, game_date,
             (session_label or "").strip() or None, time.time()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_entry(entry_id, player_name):
    """Only lets a player delete their own entry (typo/misclick fix) --
    matched by name since there's no real login system here."""
    conn = _connect()
    try:
        cur = conn.execute(
            "DELETE FROM game_entries WHERE id = ? AND player_name = ?",
            (entry_id, player_name.strip()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def all_entries():
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM game_entries ORDER BY game_date DESC, created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def player_names():
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT player_name FROM game_entries ORDER BY player_name COLLATE NOCASE"
        ).fetchall()
        return [r["player_name"] for r in rows]
    finally:
        conn.close()
