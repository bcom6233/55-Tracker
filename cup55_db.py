"""
Storage layer for the Game of 55 cup tracker.

By default this uses a local SQLite file, which is fine for testing on
your own computer but gets wiped whenever Render's free tier restarts or
wakes from sleep (its filesystem isn't persistent). To keep game history
around permanently, set two environment variables on Render --
TURSO_DATABASE_URL and TURSO_AUTH_TOKEN (from a free turso.tech account)
-- and this file automatically switches to that instead. No other code
changes needed; every function below works the same either way.

This logs a whole game at once: one "games" row per game (date, session,
team names, who won, who logged it) plus one "game_players" row per
player on either roster (their name, team, cups made, and the optional
Fun Stats -- bitch cups made/taken, drinks, fire count). Averages, win
rate, and history are all computed by grouping game_players rows by
player_name, joined back to their parent game to figure out who won.
"""
import os
import time

TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
USING_TURSO = bool(TURSO_URL)

if USING_TURSO:
    import libsql

    def _connect():
        return libsql.connect(database=TURSO_URL, auth_token=TURSO_AUTH_TOKEN)
else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cup55.db")

    def _connect():
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _rows_to_dicts(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _row_to_dict(cur):
    rows = _rows_to_dicts(cur)
    return rows[0] if rows else None


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
                game_id INTEGER NOT NULL,
                team TEXT NOT NULL,
                player_name TEXT NOT NULL,
                cups_made INTEGER NOT NULL,
                bitch_cups_made INTEGER NOT NULL DEFAULT 0,
                bitch_cups_taken INTEGER NOT NULL DEFAULT 0,
                drinks_taken INTEGER NOT NULL DEFAULT 0,
                fire_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Migrate any game_players table created before these columns
        # existed (SQLite/libSQL have no "ADD COLUMN IF NOT EXISTS", so
        # check first).
        existing_cols = {
            r["name"] for r in _rows_to_dicts(
                conn.execute("SELECT name FROM pragma_table_info('game_players')")
            )
        }
        for col in ("bitch_cups_made", "bitch_cups_taken", "drinks_taken", "fire_count"):
            if col not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE game_players ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
                except Exception:
                    pass
        conn.commit()
    finally:
        conn.close()


def add_game(game_date, session_label, team_a_name, team_b_name, winner, logged_by,
             team_a_players, team_b_players):
    """team_a_players / team_b_players: list of
    (player_name, cups_made, bitch_cups_made, bitch_cups_taken, drinks_taken, fire_count) tuples."""
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO games
               (game_date, session_label, team_a_name, team_b_name, winner, logged_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (game_date, (session_label or "").strip() or None,
             (team_a_name or "").strip() or None, (team_b_name or "").strip() or None,
             winner, (logged_by or "").strip() or None, time.time()),
        )
        game_id = _row_to_dict(cur)["id"]
        for team, players in (("A", team_a_players), ("B", team_b_players)):
            for name, cups, bitch_made, bitch_taken, drinks, fire in players:
                conn.execute(
                    """INSERT INTO game_players
                       (game_id, team, player_name, cups_made, bitch_cups_made, bitch_cups_taken, drinks_taken, fire_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (game_id, team, name.strip(), cups, bitch_made, bitch_taken, drinks, fire),
                )
        conn.commit()
        return game_id
    finally:
        conn.close()


def update_game(game_id, requesting_name, game_date, session_label, team_a_name, team_b_name, winner,
                 team_a_players, team_b_players):
    """Only lets the person who originally logged a game edit it -- matched
    by name, same rule as delete_game. Replaces the whole roster (simplest
    way to handle players being added/removed/changed on an edit) but
    keeps the original logged_by and created_at so ownership and history
    order don't change."""
    conn = _connect()
    try:
        row = _row_to_dict(conn.execute("SELECT logged_by FROM games WHERE id = ?", (game_id,)))
        if row is None or (row["logged_by"] or "").strip().lower() != requesting_name.strip().lower():
            return False
        conn.execute(
            """UPDATE games SET game_date = ?, session_label = ?, team_a_name = ?, team_b_name = ?, winner = ?
               WHERE id = ?""",
            (game_date, (session_label or "").strip() or None,
             (team_a_name or "").strip() or None, (team_b_name or "").strip() or None,
             winner, game_id),
        )
        conn.execute("DELETE FROM game_players WHERE game_id = ?", (game_id,))
        for team, players in (("A", team_a_players), ("B", team_b_players)):
            for name, cups, bitch_made, bitch_taken, drinks, fire in players:
                conn.execute(
                    """INSERT INTO game_players
                       (game_id, team, player_name, cups_made, bitch_cups_made, bitch_cups_taken, drinks_taken, fire_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (game_id, team, name.strip(), cups, bitch_made, bitch_taken, drinks, fire),
                )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_game(game_id, logged_by):
    """Only lets the person who logged a game delete it (typo/misclick fix) --
    matched by name since there's no real login system here."""
    conn = _connect()
    try:
        row = _row_to_dict(conn.execute("SELECT logged_by FROM games WHERE id = ?", (game_id,)))
        if row is None or (row["logged_by"] or "").strip().lower() != logged_by.strip().lower():
            return False
        conn.execute("DELETE FROM game_players WHERE game_id = ?", (game_id,))
        conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def all_games():
    conn = _connect()
    try:
        games = _rows_to_dicts(conn.execute("SELECT * FROM games ORDER BY game_date DESC, created_at DESC"))
        players = _rows_to_dicts(conn.execute("SELECT * FROM game_players ORDER BY id ASC"))
        by_game = {}
        for p in players:
            by_game.setdefault(p["game_id"], []).append(p)
        result = []
        for g in games:
            roster = by_game.get(g["id"], [])
            g["team_a_players"] = [p for p in roster if p["team"] == "A"]
            g["team_b_players"] = [p for p in roster if p["team"] == "B"]
            result.append(g)
        return result
    finally:
        conn.close()


def player_names():
    conn = _connect()
    try:
        rows = _rows_to_dicts(conn.execute(
            "SELECT DISTINCT player_name FROM game_players ORDER BY player_name COLLATE NOCASE"
        ))
        return [r["player_name"] for r in rows]
    finally:
        conn.close()
