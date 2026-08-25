# Game of 55 Tracker

A simple web app for tracking average cups made per person across games of
55 (cup pong with 55 cups on each side). Everyone plays from their own
phone: after a game, each player opens the app and logs their own result
-- how many cups they made, who they played, and whether they won. The
app turns all of that into a leaderboard (average cups per game, win
rate) and a full game history.

## What it does

- Each player saves their name once (remembered on their phone) and logs
  their own result after every game -- no shared device needed, no
  accounts or passwords.
- **Leaderboard**: every player ranked by average cups made per game,
  with total games played and win rate.
- **History**: every logged game, grouped by session (if you named one)
  or by date, newest first. You can delete your own entries (e.g. if you
  fat-fingered a number), but not anyone else's.
- Optional fields: who you played against, and a session name (like
  "Friday night at Jake's") so you can group a night's games together.
  Leaving those blank still works fine -- the app falls back to grouping
  by date.

## Running it locally

1. Install Python 3 if you don't have it.
2. In this folder, install Flask:
   ```
   pip install -r cup55_requirements.txt
   ```
3. Run the app:
   ```
   python cup55_app.py
   ```
4. Open `http://127.0.0.1:5001` in your browser.

This only lets you access it from the same computer. To let everyone log
their own scores from their own phones, deploy it (see below) so there's
one shared address everyone can open.

## Deploying to Render (so everyone can use it from their phone)

1. Put this project's files in a free GitHub account (drag-and-drop
   upload on github.com works fine, no command-line git needed). You'll
   need: `cup55_app.py`, `cup55_db.py`, `cup55_index.html`,
   `cup55_requirements.txt`.
2. Create a free Render account (render.com), connect it to that GitHub
   repo, and create a new **Web Service** from it.
3. Build Command: `pip install -r cup55_requirements.txt`. Start
   Command: `python cup55_app.py`. Instance Type: **Free**.
4. Render gives you a public address like
   `https://your-app-name.onrender.com`. Share that link with everyone
   playing -- each person opens it on their own phone, saves their name
   once, and logs their own results from then on.

**The tradeoff**: Render's free tier "falls asleep" after 15 minutes of
no traffic, so the first load after a while takes 30-60 seconds to wake
up. After that it's normal speed. Fine for a casual tracker; if it
bothers you, a free uptime-monitor service (like UptimeRobot) pinging the
URL every few minutes keeps it awake.

**Heads up on the database**: this app stores everything in a small local
file (SQLite). On Render's free tier, that file resets whenever the app
restarts or wakes up from sleep, which means your game history could
occasionally get wiped. For a casual tracker that's usually fine -- if
you want the history to survive long-term, the easiest fix is exporting
the leaderboard/history periodically, or upgrading to a Render plan with
a persistent disk.

## Project files

| File | What it's for |
|---|---|
| `cup55_app.py` | Flask backend: routes for logging games, leaderboard, history |
| `cup55_db.py` | SQLite storage -- one row per player per game |
| `cup55_index.html` | The whole frontend -- name picker, log-a-game form, leaderboard, history |
| `cup55_requirements.txt` | Python dependencies (just Flask) |

## Changing the max cup count

If you ever play a variant with a different number of cups per side,
change `MAX_CUPS = 55` near the top of `cup55_app.py`, and update the
`max="55"` on the cups-made input in `cup55_index.html` to match (the
page also pulls the real number from the server automatically once it
loads, so the label itself doesn't need editing).
