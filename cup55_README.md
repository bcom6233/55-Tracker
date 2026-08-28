# Lambda Chi Alpha -- Game of 55 Tracker

A web app for tracking cups made across games of 55 (cup pong with 55
cups on each side), themed for Lambda Chi Alpha. Whoever's phone is
handy after a game logs the whole thing at once -- both teams' full
rosters (2v2 up to 5v5), everyone's cups made, and who won. The app
turns that into a leaderboard (average cups per game, win rate) and a
full game history.

## What it does

- **Log a whole game**: pick a date, optionally name the session (e.g.
  "Friday night at the house"), name both teams, add 2 to 5 players per
  side with each person's cups made, and mark who won.
- **Leaderboard**: every player ranked by average cups made per game,
  with total games played and win rate.
- **History**: every logged game, newest first, showing both rosters
  side by side with the winning team highlighted. Whoever logged a game
  can delete it (e.g. to fix a mistake) -- matched by the name they saved
  on their phone, no accounts or passwords needed.
- Player names autocomplete from everyone who's ever been logged, so
  typing "Ja" after a few games will suggest "Jake."
- **Team Size Projector**: estimates what each person might average in a
  different team size (2v2 through 5v5). It looks at how big a share of
  their own team's cups a player typically makes, normalizes that by how
  many teammates they had, and re-projects it onto a different team size
  assuming a full 55-cup rack gets cleared. It's a rough estimate, not a
  guarantee -- someone who's only played 2v2 might play differently once
  there are more people on their side.
- **Fun Stats**: per-player bitch cups made and bitch cups taken (per
  game), drinks taken (per game), and total times someone caught fire
  (hit 3 in a row after a rerack). These are all optional when logging a
  game -- leave any of them blank and they default to 0.

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
games from their own phones, deploy it (see below) so there's one shared
address everyone can open.

## Deploying to Render (so everyone can use it from their phone)

1. Put this project's files in a free GitHub repo (drag-and-drop upload
   on github.com works fine, no command-line git needed). You'll need:
   `cup55_app.py`, `cup55_db.py`, `cup55_index.html`,
   `cup55_requirements.txt`.
2. Create a free Render account (render.com), click **New → Web
   Service**, and connect it to that GitHub repo.
3. Make sure the **Runtime/Language** is set to **Python 3** (not
   Docker). Then set:
   - Build Command: `pip install -r cup55_requirements.txt`
   - Start Command: `python cup55_app.py`
   - Instance Type: **Free**
4. Render gives you a public address like
   `https://your-app-name.onrender.com`. Share that link -- each brother
   opens it on their own phone, saves their name once, and can log games
   from then on.

**The tradeoff**: Render's free tier "falls asleep" after 15 minutes of
no traffic, so the first load after a while takes 30-60 seconds to wake
up. After that it's normal speed. Fine for a casual tracker.

**Heads up on the database -- and how to make it permanent**: by default
this app stores everything in a small local file (SQLite). On Render's
free tier, that file gets wiped every time the app restarts or wakes up
from sleep, so game history keeps disappearing. To fix that for good,
connect a free [Turso](https://turso.tech) database -- it's the same SQL
under the hood, it's free forever (no card, no expiration, 5GB storage),
and the app switches to using it automatically once it's set up:

1. Sign up at [turso.tech](https://turso.tech) and create a database
   (the dashboard walks you through it -- takes about 2 minutes).
2. From the database's page, grab two things: the **database URL**
   (starts with `libsql://`) and an **auth token**.
3. On your Render service, go to **Environment** and add two
   environment variables:
   - `TURSO_DATABASE_URL` -- paste the database URL
   - `TURSO_AUTH_TOKEN` -- paste the auth token
4. Save, then **Manual Deploy → Deploy latest commit** so the app
   restarts with those variables set.

That's it -- no other changes needed. The app checks for those two
variables on startup: if they're set, it uses Turso (permanent); if
they're not, it falls back to the local SQLite file (gets wiped on
restart, but fine for testing on your own computer). Any games already
logged in the old local-file version won't carry over automatically,
since they're two different databases -- but everything logged after
the switch will stick around for good.

## Project files

| File | What it's for |
|---|---|
| `cup55_app.py` | Flask backend: routes for logging games, leaderboard, history |
| `cup55_db.py` | Storage layer -- one `games` row per game, one `game_players` row per player on either roster. Uses local SQLite by default, or Turso (permanent) if `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` are set |
| `cup55_index.html` | The whole frontend -- name saver, log-a-game form with dynamic team rosters, leaderboard, history, Lambda Chi Alpha (purple/green/gold) styling |
| `cup55_requirements.txt` | Python dependencies (Flask + the `libsql` client for Turso) |

## Changing team size or max cups

- Team size (currently 2 to 5 per side): change `MIN_TEAM_SIZE` /
  `MAX_TEAM_SIZE` near the top of `cup55_app.py`, and `MIN_TEAM_SIZE` /
  `MAX_TEAM_SIZE` near the top of the `<script>` in `cup55_index.html`.
- Max cups per game (currently 55): change `MAX_CUPS` near the top of
  `cup55_app.py` -- the page pulls the real number from the server
  automatically, so nothing else needs editing.
