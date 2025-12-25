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

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
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

