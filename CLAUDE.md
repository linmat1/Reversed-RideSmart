# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

RideSmart is a ride orchestration system for UChicago students that exploits RideSmart shuttle capacity mechanics to obtain free Lyft rides. RideSmart shuttles hold 3-6 passengers; when capacity fills, the service offers Lyft as an alternative. The system uses "filler accounts" to fill shuttle capacity, books the Lyft when it appears, then cancels all filler bookings.

## Running the Project

**Backend (Flask API):**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # then fill in credentials
python api.py         # localhost:5000
```

**Frontend (React):**
```bash
cd frontend
npm install
npm start             # localhost:3000
```

**CLI (standalone, no frontend):**
```bash
cd backend
python main.py
```

**Tests (manual scripts, no test runner configured):**
```bash
cd backend
python test_cross_user.py          # Test if proposals are user-scoped
python test_status_endpoints.py    # Test status API endpoints
```

## Architecture

### Core Orchestration Flow

`backend/src/lyft_orchestrator.py` is the heart of the system. It runs a 5-phase parallel flow using `ThreadPoolExecutor`:

1. **Phase 1**: All 7 filler accounts search simultaneously (~12s vs. sequential ~84s)
2. **Phase 2**: All 7 filler accounts book simultaneously using their proposals
3. **Phase 3**: Original user searches to check if Lyft appeared
4. **Phase 4**: Book Lyft if available
5. **Phase 5**: Cancel all filler bookings simultaneously

`stop_requested` is checked between phases (not between individual calls). In-flight requests finish before abort.

### Via.com API Integration

RideSmart runs on Via.com's backend. The three core operations are in:
- `backend/src/search_ride.py` — POST to `/validate` for ride proposals
- `backend/src/book_ride.py` — POST to `/book` with `proposal_uuid` + `prescheduled_ride_id`
- `backend/src/cancel_ride.py` — cancel a booked ride

Raw original API scripts are archived in `backend/src/original/`.

**Open research question**: Are `proposal_uuid` + `prescheduled_ride_id` user-scoped or global? If global, Phase 1 can be eliminated (one search, all 7 fillers book from same proposals). `test_cross_user.py` was written to answer this.

### Multi-Account System

Credentials live in `backend/.env`. `backend/src/users.py` loads them into a `USERS` dict. `backend/src/config.py` holds global config (auth, passengers, origin/destination defaults). Each user has `AUTH_TOKEN`, `USER_ID`, and display `NAME`.

### Flask API + SSE Streaming

`backend/api.py` (main server) exposes REST endpoints. Live booking status and developer logs are streamed via Server-Sent Events (SSE) — see `backend/src/booking_state.py` and `backend/src/developer_logs.py`. The log backend auto-selects SQLite (`developer_logs_db.py`) or PostgreSQL (`developer_logs_postgres.py`) based on whether `DATABASE_URL`/`POSTGRES_URL` env vars are present.

### Frontend

React app in `frontend/src/`. Key components:
- `LyftBooker.js` — main orchestration UI with SSE subscription
- `DeveloperPanel.js` — admin debug view with real-time logs
- `MapSelector.js` — Leaflet-based interactive location picker
- `BookingStatusPanel.js` — live per-account booking status
- `presetLocations.js` — pre-configured UChicago route pairs

### Deployment

- **Frontend**: Vercel (`backend/vercel.json` + `backend/app.py` as entrypoint)
- **Backend**: Railway (auto-detects Python, serves via Gunicorn)
- **CI/CD**: GitHub Actions (`.github/workflows/deploy.yml`) SSHes into EC2 on push to `main` and runs `/home/ubuntu/deploy.sh`

Set `REACT_APP_API_URL` in Vercel dashboard to point to Railway backend URL.
