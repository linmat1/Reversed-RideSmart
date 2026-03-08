# RideSmart

A web app that automates getting free Lyft rides through the University of Chicago's RideSmart shuttle service. It fills shuttle capacity using multiple accounts to trigger Lyft as an alternative, then books the Lyft for the original user and cancels all filler bookings.

## How It Works

RideSmart vehicles are shared shuttles holding 3-6 passengers. When enough seats are filled, the service offers a Lyft instead. The orchestrator exploits this by:

1. **Phase 1** — Search for available rides across all filler accounts simultaneously
2. **Phase 2** — Book all filler accounts in parallel (fills shuttle capacity)
3. **Phase 3** — Search as the original user to check if Lyft appeared
4. **Phase 4** — Book the Lyft if available
5. **Phase 5** — Cancel all filler bookings simultaneously

Running all phases in parallel reduces total time from ~4.5 minutes (sequential) to ~60 seconds.

## Tech Stack

- **Backend**: Python, Flask, SQLite/PostgreSQL
- **Frontend**: React, Leaflet (interactive maps)
- **Deployment**: Vercel (frontend), Railway (backend)

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- 2–7 RideSmart accounts with auth tokens

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in credentials (see Configuration below)
python api.py
# Runs on http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
npm start
# Runs on http://localhost:3000
```

### CLI (no frontend needed)

```bash
cd backend
python main.py
```

## Configuration

Copy `backend/.env.example` to `backend/.env` and fill in your credentials:

```env
DEFAULT_USER=matthew

USER_MATTHEW_NAME=Matthew
USER_MATTHEW_AUTH_TOKEN=<token from RideSmart app>
USER_MATTHEW_USER_ID=<your user ID>

USER_TOMAS_NAME=Tomas
USER_TOMAS_AUTH_TOKEN=<token>
USER_TOMAS_USER_ID=<id>

# Add up to 7 users total (1 original + 6 fillers)
```

Auth tokens can be extracted from the RideSmart mobile app using a proxy or browser DevTools.

### Routes

Preset routes are defined in `backend/src/destination_config.py`. The default route is I-House → Cathey Dining Commons. Add routes by defining origin/destination lat-lng pairs.

### Global Settings

Edit `backend/src/config.py` to adjust:

```python
n_passengers = 2        # Number of passengers to book for
charging = False        # Whether device is charging (sent to API)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/users` | List configured users |
| `GET` | `/api/routes` | List available routes |
| `POST` | `/api/search` | Search for available rides |
| `POST` | `/api/book` | Book a ride |
| `POST` | `/api/cancel` | Cancel a ride |
| `GET` | `/api/status` | Current booking status (all users) |
| `GET` | `/api/status/stream` | SSE stream of booking status |
| `POST` | `/api/lyft/run` | Run the Lyft orchestrator (SSE stream) |
| `POST` | `/api/lyft/check` | Check if Lyft is currently available |
| `GET` | `/api/developer/stream` | SSE stream of developer logs |
| `GET` | `/api/developer/snapshot` | Snapshot of developer logs |

## Deployment

### Frontend (Vercel)

```bash
cd frontend
vercel
```

Set environment variable in Vercel dashboard:
```
REACT_APP_API_URL=https://your-backend.railway.app
```

### Backend (Railway)

```bash
cd backend
railway login
railway init
railway up
```

Railway auto-detects Python and serves via Gunicorn.

### Database

By default, developer logs are stored in SQLite (`backend/data/`). For persistent storage on Railway or Vercel, provision a PostgreSQL database and set:

```env
DATABASE_URL=postgresql://...
```

The backend auto-detects and uses Postgres when available.

## Project Structure

```
backend/
├── api.py                      # Flask API server
├── main.py                     # Standalone CLI
├── src/
│   ├── lyft_orchestrator.py    # Core orchestration logic
│   ├── search_ride.py          # Via.com search API
│   ├── book_ride.py            # Via.com booking API
│   ├── cancel_ride.py          # Via.com cancel API
│   ├── users.py                # Credential loading
│   ├── destination_config.py   # Route definitions
│   ├── developer_logs.py       # Real-time log streaming
│   └── booking_state.py        # Live booking state tracking
frontend/
├── src/
│   ├── App.js                  # App shell
│   ├── LyftBooker.js           # Lyft orchestration UI
│   ├── DeveloperPanel.js       # Admin/developer view
│   ├── MapSelector.js          # Map-based location picker
│   └── BookingStatusPanel.js   # Live booking status
```

## Notes

- Each API call to the RideSmart backend takes ~10–15 seconds. The parallel approach is essential for reasonable UX.
- The `.env` file contains sensitive auth tokens — never commit it (already in `.gitignore`).
- All filler bookings are always cancelled at the end, whether or not a Lyft was found.
- The "stop" button lets you abort mid-orchestration; in-flight requests finish before cleanup begins.


