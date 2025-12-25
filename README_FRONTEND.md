# RideSmart React Frontend

This is a React frontend that provides the same functionality as `main.py` through a web interface.

## Setup

### Backend (Flask API)

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Start the Flask API server:
```bash
python api.py
```

The API will run on `http://localhost:5000`

### Frontend (React)

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the React development server:
```bash
npm start
```

The React app will open in your browser at `http://localhost:3000`

## Usage

1. Make sure the Flask API is running (`cd backend && python api.py`)
2. Start the React app (`npm start` in the frontend directory)
3. Click "Search for Rides" to search for available rides
4. Select a ride from the list and click "Book This Ride"
5. After booking, you can cancel the ride or start a new search

## Features

- Search for available rides using default origin/destination
- Display ride proposals with pickup, dropoff, ETA, and cost
- Book selected rides
- Cancel booked rides
- Modern, responsive UI

