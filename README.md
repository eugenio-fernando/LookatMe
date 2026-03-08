# LookatMe

A productivity web application that helps users manage tasks, build daily habits, track learning, and stay accountable with teammates.

**Production:** https://lookatme.fly.dev

---

## Project Overview

LookatMe is a focused productivity dashboard built around three ideas:

1. **One action per day** — guided onboarding gets users to their first task in under 30 seconds
2. **Streaks as motivation** — every completed task extends a daily streak visible to the whole workspace
3. **Accountability** — workspace members see each other's streaks and daily progress on a shared leaderboard

---

## Features

- **Task management** — create, prioritize, and complete tasks with due dates
- **Daily Mission** — server-tracked goals (3 tasks, 1 habit, 1 note) with live progress bars
- **Streak system** — per-user and global streak tracking; habit milestone logged on first daily task
- **Workspace collaboration** — invite teammates via shareable links; compare streaks on the leaderboard
- **AI Assistant** — analyze your day, plan tomorrow, summarize notes (OpenAI, 10 req/day limit)
- **Daily notes** — write and retrieve notes tied to the current day
- **Learning tracker** — log study hours and progress for any topic
- **Real-time updates** — Socket.IO pushes task/streak events to all connected clients
- **News feed** — trending headlines by category, with AI-powered article summarization
- **Onboarding flow** — first-login modal that creates a task before the user sees the dashboard
- **Invite sharing** — WhatsApp, Facebook, Twitter/X, Instagram (copy link), and email
- **Dark / light / sepia themes**
- **PWA-ready** — manifest + service worker for mobile install

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-SocketIO |
| ORM | Prisma Client Python (sync) |
| Database | SQLite (Fly.io persistent volume) |
| Frontend | HTML, CSS, Vanilla JS |
| Real-time | Socket.IO (threading async mode) |
| AI | OpenAI `gpt-4o-mini` |
| Email | Resend |
| Deployment | Docker, Fly.io Machines |

---

## Architecture

```
LookatMe/
├── run.py                  # Entrypoint (gunicorn via Docker)
├── Dockerfile
├── fly.toml
├── schema.prisma           # Single source of truth for DB schema
└── app/
    ├── __init__.py         # App factory, blueprint registration, SocketIO setup
    ├── extensions.py       # Shared SocketIO instance
    ├── models/
    │   └── db.py           # All database access functions (no raw SQL)
    ├── routes/
    │   ├── auth.py         # Login, register, verify, magic link, password reset
    │   ├── tasks.py        # CRUD + completion (emits socket events)
    │   ├── mission.py      # GET /api/mission/today
    │   ├── ai.py           # AI endpoints with DB-backed rate limiting
    │   ├── invites.py      # Workspace invite creation and acceptance
    │   ├── workspaces.py   # Workspace management + leaderboard
    │   ├── external.py     # News, notes, verse APIs
    │   └── ...
    ├── services/
    │   ├── ai_service.py   # OpenAI wrapper (test mode support)
    │   └── email_service.py
    └── templates/
        └── dashboard.html  # Single-page dashboard (all JS inline)
```

Data flows through `app/models/db.py` — all routes call named functions, no ORM queries outside that file.

---

## AI Assistant

Three endpoints, each guarded by a 10-requests/day per-user limit tracked in the `AIUsage` table.

| Endpoint | Description |
|---|---|
| `POST /api/ai/analyze-day` | Summarize pending/completed tasks and notes |
| `POST /api/ai/plan-tomorrow` | Suggest top 3 priorities for tomorrow |
| `POST /api/ai/summarize-notes` | Extract themes and action items from recent notes |

**Test mode:** set `AI_TEST_MODE=true` to return mock responses without calling OpenAI.

When the daily limit is reached the UI shows an upgrade card instead of an error string.

---

## Daily Mission System

A `DailyMission` record is created automatically on first dashboard load each day.

| Goal | Default | Tracked via |
|---|---|---|
| Tasks | 3 | `task_completed` activity entries |
| Habits | 1 | `habit_completed` logged on first streak update of the day |
| Notes | 1 | `note_created` activity entries |

Progress is computed live from the `Activity` table — no separate counter columns. The mission is marked `completed = true` in the DB once all goals are met.

---

## Installation

**Requirements:** Python 3.11+, Node not required.

```bash
git clone https://github.com/your-org/lookatme.git
cd lookatme

python -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt

# Apply schema to local SQLite
DATABASE_URL="file:$(pwd)/lookatme.db" python -m prisma db push --skip-generate

# Start dev server
python run.py
```

Visit `http://localhost:8080`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session secret |
| `DATABASE_URL` | Yes | `file:/data/lookatme.db` in production |
| `OPENAI_API_KEY` | For AI features | OpenAI API key |
| `AI_TEST_MODE` | No | Set `true` to skip OpenAI and return mock responses |
| `RESEND_API_KEY` | For email | Resend API key |
| `EMAIL_FROM` | No | Sender address (default: `onboarding@resend.dev`) |
| `FLASK_ENV` | No | Set `production` to disable debug endpoints |

Set via `.env` file locally or `fly secrets set` in production.

---

## Deployment (Fly.io)

The app runs on a Fly.io Machine with a persistent volume mounted at `/data` for the SQLite database.

```bash
# First deploy
fly launch

# Subsequent deploys
fly deploy

# Set secrets
fly secrets set SECRET_KEY=... OPENAI_API_KEY=... RESEND_API_KEY=...

# Check status
fly status -a lookatme

# Tail logs
fly logs -a lookatme
```

**Key `fly.toml` values:**

```toml
[http_service]
  internal_port = 8080   # Must match gunicorn bind address

[mounts]
  source = "lookatme_data"
  destination = "/data"
```

The database is never stored inside the container — all writes go to the `/data` volume which persists across deploys.

---

## Branch Workflow

| Branch | Purpose |
|---|---|
| `main` | Production — merged only after verification |
| `dev` | Active development |
