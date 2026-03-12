# LookatMe

AI-powered productivity and habit tracking platform focused on accountability and daily streaks.

**Production:** https://lookatme.fly.dev

---

## Core Features

- **Task management** — create, prioritize, and complete tasks with due dates
- **Habit tracking** — daily streak system with milestone tracking
- **Daily notes** — write and retrieve notes tied to the current day
- **Activity feed** — social productivity stream of focus sessions, reminders, challenges, and messages
- **Activity reactions** — react to feed events with `like`, `love`, `fire`, and `clap`
- **Centralized event system** — unified event recording and websocket broadcast for activity updates
- **Daily Mission** — server-tracked goals with live progress
- **Daily Commitment** — one-sentence daily intention with completion animation and streak integration
- **AI productivity assistant** — analyze your day, plan tomorrow, summarize notes (10 req/day)
- **Weekly insights** — AI-generated summary of weekly performance
- **Friend accountability system** — invite friends and compare streaks side by side
- **Invite system** — tracked social invitations via WhatsApp, Facebook, Twitter/X, and email
- **Streak leaderboard** — top 10 friends + self ranked by streak and weekly tasks
- **Real-time updates** — Socket.IO pushes `activity:new` and `reaction:new` events to clients
- **Admin debug panel** — admin-only operational view for email, auth, and webhook events
- **PWA-ready** — manifest + service worker for mobile install
- **Dark / light / sepia themes**

---

## Architecture

### Backend

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | Flask + Flask-SocketIO |
| ORM | Prisma Client Python (sync interface) |
| Database | SQLite on Fly.io persistent volume |
| Event System | Centralized event recording service for activity + notifications |
| Activity Layer | Feature module with feed query + reaction aggregation |
| Real-time | Socket.IO (threading async mode), `activity:new` + `reaction:new` |
| AI | OpenAI `gpt-4o-mini` via `openai` SDK |
| Email | Resend — verified sender domain `aitoptutor.com` |
| Deployment | Docker + Fly.io Machines |

### Project Structure

```
LookatMe/
├── run.py                  # Entrypoint (gunicorn via Docker)
├── Dockerfile
├── fly.toml
├── schema.prisma           # Single source of truth for DB schema
└── app/
    ├── __init__.py         # App factory, blueprint registration, SocketIO setup
    ├── extensions.py       # Shared SocketIO + Babel instances
    ├── features/
    │   └── activity/
    │       ├── routes.py   # /api/activity/feed and /api/activity/react
    │       ├── service.py  # Activity feed queries and reaction aggregation
    │       └── templates/  # Feature-local templates (if needed)
    ├── models/
    │   └── db.py           # All database access (no ORM queries outside this file)
    ├── routes/
    │   ├── auth.py         # Login, register, verify, magic link, password reset
    │   ├── auth_pages.py   # Page routes: /login, /verify/<token>, /reset/<token>
    │   ├── tasks.py        # Task CRUD + completion (emits socket events)
    │   ├── mission.py      # GET /api/mission/today
    │   ├── commitment.py   # Daily Commitment set / complete endpoints
    │   ├── ai.py           # AI endpoints with DB-backed rate limiting
    │   ├── invites.py      # Workspace invite creation and acceptance
    │   ├── workspaces.py   # Workspace management
    │   ├── social.py       # Friend invitations and leaderboard
    │   ├── external.py     # External/news integrations (kept for compatibility)
    │   └── views.py        # Page render routes (dashboard, profile, invitations)
    ├── services/
    │   ├── event_service.py # Centralized event recording + socket emit
    │   ├── ai_service.py   # OpenAI wrapper (test mode support)
    │   └── email_service.py # Resend wrapper (verification, magic link, password reset)
    └── templates/
        ├── dashboard.html  # Main dashboard + activity feed
        ├── activity_feed.html # Feed rendering with reactions
        ├── admin_debug.html # Admin debug event dashboard
        ├── focus.html      # Focus mode with local countdown timer
        ├── invite.html     # Invitation landing page (workspace + social)
        ├── login.html      # Auth page (login, register, magic link, password reset)
        └── invitations.html # Invitation analytics and friends list
```

All database access flows through `app/models/db.py`. Routes call named functions — no raw ORM queries outside that module.

---

## Activity Feed

The activity feed is the main social productivity surface. It aggregates recent user events such as focus completion, reminders, messages, and challenges into a single stream for dashboard visibility.

## Reactions

Activity events support lightweight reactions:

- `like`
- `love`
- `fire`
- `clap`

Reaction counts are returned in feed payloads and updated in real time over Socket.IO.

## Event System

The app uses a centralized event architecture:

- write activity events through a shared event service
- keep event persistence and websocket emission in one place
- broadcast `activity:new` for new feed events
- broadcast `reaction:new` when reactions are added

This keeps feature modules consistent and reduces route-level event duplication.

## Admin Debug Panel

Admin users can inspect recent operational events in:

- `GET /admin/debug`

The panel provides recent email events, auth events, and webhook events to speed up production debugging.

## Experimental Features (Hidden From Primary Navigation)

These are still present in the codebase and routes but are intentionally not part of the core product navigation:

- learning tracker
- news feed
- advanced workspace modules

---

## AI Assistant

Three endpoints, each guarded by a 10-requests/day per-user limit tracked in the `AIUsage` table.

| Endpoint | Description |
|---|---|
| `POST /api/ai/analyze-day` | Summarize pending/completed tasks and notes |
| `POST /api/ai/plan-tomorrow` | Suggest top 3 priorities for tomorrow |
| `POST /api/ai/summarize-notes` | Extract themes and action items from recent notes |

**Test mode:** set `AI_TEST_MODE=true` to return mock responses without calling OpenAI.

Responses are cached per user per day in `AIResponseCache` to avoid duplicate API calls.

---

## Example API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/activity/feed` | Returns activity feed entries and reaction counts |
| `POST` | `/api/activity/react` | Adds a reaction to an activity event (duplicate reactions blocked per user/event) |
| `GET` | `/admin/debug` | Admin-only debug dashboard for operational events |

---

## Daily Mission System

A `DailyMission` record is created automatically on first dashboard load each day.

| Goal | Default | Tracked via |
|---|---|---|
| Tasks | 3 | `task_completed` activity entries |
| Habits | 1 | `habit_completed` logged on first streak update of the day |
| Notes | 1 | `note_created` activity entries |

Progress is computed live from the `Activity` table. The mission is marked `completed = true` once all goals are met.

---

## Installation

**Requirements:** Python 3.11+

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
| `VERIFY_EMAIL_FROM` | Recommended | Sender for verification emails (e.g. `LookatMe <verify@mail.yourdomain.com>`) |
| `SUPPORT_EMAIL_FROM` | Recommended | Sender for magic-link and reset emails |
| `REPLY_TO_EMAIL` | No | Optional reply-to address for transactional emails |
| `EMAIL_FROM` | Backward-compatible | Fallback sender if specific sender vars are not set |
| `APP_BASE_URL` | No | Public URL used in email links (default: `https://lookatme.fly.dev`) |
| `FLASK_ENV` | No | Set `production` to disable debug endpoints |

Set via `.env` locally or `fly secrets set KEY=value -a lookatme` in production.

Local setup:

```bash
cp .env.example .env
# then edit .env and set real secrets (never commit this file)
```

---

## Deployment (Fly.io)

The app runs on a Fly.io Machine with a persistent volume at `/data` for SQLite.

```bash
# Subsequent deploys
fly deploy

# Set secrets
fly secrets set SECRET_KEY=... OPENAI_API_KEY=... RESEND_API_KEY=... EMAIL_FROM="LookatMe <verify@aitoptutor.com>"

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

The SQLite database is never stored inside the container — all writes go to the `/data` volume which persists across deploys.

---

## Development Workflow

| Branch | Purpose |
|---|---|
| `main` | Production — merged only after verification |
| `dev` | Active development |

### Release steps

```bash
# 1. Develop on dev
git checkout dev

# 2. Test locally
python run.py

# 3. Push dev
git push origin dev

# 4. Merge to main and deploy
git checkout main
git pull
git merge dev
git push
fly deploy
```

### Database schema changes

```bash
# After editing schema.prisma:
DATABASE_URL="file:/data/lookatme.db" python -m prisma db push --skip-generate

# Or locally:
DATABASE_URL="file:$(pwd)/lookatme.db" python -m prisma db push --skip-generate
```

---

## Future Roadmap

- Invite analytics dashboard (open/accept rates per method)
- Push notification system for streak reminders
- LinkedIn verification improvements
- Mobile-optimized layout refinements
- Workspace-level leaderboard vs friends leaderboard toggle
