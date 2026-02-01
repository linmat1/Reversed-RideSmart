# RideSmart Backend

This directory contains all backend files for the RideSmart application.

## Structure

```
backend/
├── src/                    # Python modules
│   ├── search_ride.py     # Search for available rides
│   ├── book_ride.py       # Book a ride
│   ├── cancel_ride.py     # Cancel a booked ride
│   ├── config.py          # Global configuration
│   └── destination_config.py  # Route definitions
├── api.py                 # Flask REST API server
├── main.py                # CLI version (standalone script)
└── requirements.txt       # Python dependencies
```

## Deploying to Vercel

1. In the Vercel project **Settings → Build and Deployment → Root Directory**, set **Root Directory** to `backend` (so Vercel uses this folder as the app root).
2. Vercel will then find the Flask entrypoint at `app.py` (which exposes the app from `api.py`) and the build should succeed.

## Database (developer logs)

Developer logs (ride status log + user access log) are stored in SQLite by default. On Vercel the filesystem is read-only, so logs are ephemeral unless you use a hosted database.

**To persist developer logs on Vercel:**

1. In the Vercel dashboard, open your **backend** project.
2. Go to **Storage** (or **Integrations** / **Marketplace**) and create a **Postgres** database (e.g. Neon or another Postgres provider). Connect it to the backend project.
3. Vercel will add a `POSTGRES_URL` or `DATABASE_URL` environment variable to the project automatically.
4. Redeploy the backend. The app will use Postgres for developer logs when that variable is set; otherwise it uses SQLite (or `/tmp` on Vercel, which is ephemeral).

No code changes are required: the backend checks for `POSTGRES_URL` or `DATABASE_URL` and uses Postgres when present.

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Configure user credentials:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and fill in your actual auth tokens and user IDs
   - **Important**: Never commit `.env` to version control - it contains sensitive credentials
   - The `.env` file is already in `.gitignore` for your safety

3. Environment variable format:
   ```
   USER_USERNAME_NAME=Display Name
   USER_USERNAME_AUTH_TOKEN=your_auth_token_here
   USER_USERNAME_USER_ID=1234567
   ```
   
   Example:
   ```
   USER_MATTHEW_NAME=Matthew
   USER_MATTHEW_AUTH_TOKEN=2|1:0|10:1766628685|4:user|16:...
   USER_MATTHEW_USER_ID=3922267
   ```

## Running the API Server

Start the Flask API server:
```bash
python api.py
```

The API will run on `http://localhost:5000`

## Running the CLI Version

Run the standalone command-line interface:
```bash
python main.py
```

## API Endpoints

- `GET /api/routes` - Get all available routes
- `POST /api/search` - Search for available rides
- `POST /api/book` - Book a ride
- `POST /api/cancel` - Cancel a booked ride
- `GET /api/config` - Get default origin/destination

## Notes

- The API server must be running for the React frontend to work
- All imports use relative paths from the `backend/` directory
- Run commands from the `backend/` directory

