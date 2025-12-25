# RideSmart Architecture Explanation

## Overview

RideSmart is a full-stack web application with a **React frontend** and a **Flask (Python) backend**. The frontend runs in the browser and communicates with the backend via HTTP REST API calls.

```
┌─────────────────┐         HTTP REST API         ┌─────────────────┐
│                 │  ───────────────────────────>  │                 │
│  React Frontend │  <───────────────────────────  │  Flask Backend  │
│  (Port 3000)     │         JSON Responses        │  (Port 5000)    │
│                 │                                 │                 │
└─────────────────┘                                 └─────────────────┘
                                                           │
                                                           │
                                                           ▼
                                              ┌───────────────────────┐
                                              │  External RideSmart   │
                                              │  API (Via.com)        │
                                              └───────────────────────┘
```

---

## Frontend Architecture (React)

### 1. **Entry Point** (`frontend/src/index.js`)

```javascript
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

**What it does:**
- Renders the React app into the HTML element with id="root"
- `React.StrictMode` enables additional checks and warnings during development
- This is the first file that runs when the app loads

### 2. **Main Component** (`frontend/src/App.js`)

The `App` component is a **functional component** using React Hooks for state management.

#### **State Management (useState Hooks)**

The app manages 9 pieces of state:

```javascript
const [proposals, setProposals] = useState([]);           // List of available rides
const [loading, setLoading] = useState(false);             // Loading state for searches
const [error, setError] = useState(null);                  // Error messages
const [selectedProposal, setSelectedProposal] = useState(null);  // Currently booking proposal
const [bookedRide, setBookedRide] = useState(null);        // Successfully booked ride
const [booking, setBooking] = useState(false);            // Loading state for booking
const [cancelling, setCancelling] = useState(false);       // Loading state for cancellation
const [routes, setRoutes] = useState([]);                 // Available routes from backend
const [selectedRoute, setSelectedRoute] = useState(null); // Currently selected route
const [loadingRoutes, setLoadingRoutes] = useState(true); // Loading state for routes
```

**Why useState?**
- React components re-render when state changes
- `useState` returns `[currentValue, setterFunction]`
- Calling the setter triggers a re-render with new state

#### **API Base URL**

```javascript
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000';
```

- Uses environment variable if set, otherwise defaults to `http://localhost:5000`
- This is where all API calls are sent

### 3. **Component Lifecycle (useEffect)**

```javascript
useEffect(() => {
  const fetchRoutes = async () => {
    // Fetch routes from backend
  };
  fetchRoutes();
}, []);
```

**What it does:**
- Runs **once** when component mounts (empty dependency array `[]`)
- Fetches available routes from `/api/routes`
- Sets the first route as selected by default
- This happens automatically when the page loads

### 4. **API Communication Functions**

#### **A. Fetch Routes** (`fetchRoutes` inside useEffect)

```javascript
const response = await fetch(`${API_BASE}/api/routes`);
const data = await response.json();
setRoutes(data.routes || []);
```

**Flow:**
1. Makes GET request to `http://localhost:5000/api/routes`
2. Backend returns JSON with routes array
3. Updates `routes` state
4. Selects first route automatically

#### **B. Search Rides** (`searchRides`)

```javascript
const searchRides = async () => {
  setLoading(true);  // Show loading indicator
  setError(null);    // Clear previous errors
  
  const response = await fetch(`${API_BASE}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ route_id: selectedRoute })
  });
  
  const data = await response.json();
  setProposals(data.proposals || []);
  setLoading(false);
};
```

**Flow:**
1. Validates that a route is selected
2. Sets loading state (shows "Searching..." message)
3. Sends POST request with `route_id` in JSON body
4. Backend uses route to get origin/destination
5. Backend calls external RideSmart API
6. Returns proposals array
7. Updates `proposals` state → triggers re-render → shows ride cards

#### **C. Book Ride** (`bookRide`)

```javascript
const bookRide = async (proposal) => {
  const currentRoute = routes.find(r => r.id === selectedRoute);
  
  const response = await fetch(`${API_BASE}/api/book`, {
    method: 'POST',
    body: JSON.stringify({
      prescheduled_ride_id: proposal.prescheduled_ride_id,
      proposal_uuid: proposal.proposal_uuid,
      origin: currentRoute?.origin.data,
      destination: currentRoute?.destination.data
    })
  });
  
  setBookedRide({ ...proposal, bookingResponse: data });
};
```

**Flow:**
1. Finds current route data
2. Sends booking request with proposal IDs and route data
3. Backend calls external API to book the ride
4. Updates `bookedRide` state → shows success message

#### **D. Cancel Ride** (`cancelRide`)

```javascript
const cancelRide = async (rideId) => {
  const response = await fetch(`${API_BASE}/api/cancel`, {
    method: 'POST',
    body: JSON.stringify({ ride_id: rideId })
  });
  
  setBookedRide(null);  // Clear booked ride
};
```

**Flow:**
1. Sends cancellation request with ride ID
2. Backend calls external API to cancel
3. Clears booked ride state → returns to search screen

### 5. **Conditional Rendering**

The UI changes based on state using conditional rendering:

```javascript
{!proposals.length && !loading && !bookedRide && (
  // Show route selector and search button
)}

{loading && (
  // Show loading message
)}

{proposals.length > 0 && !bookedRide && (
  // Show list of ride cards
)}

{bookedRide && (
  // Show booking success and cancel button
)}
```

**Why this works:**
- React only renders JSX that evaluates to truthy
- Different states show different UI sections
- Only one section is visible at a time

### 6. **Data Flow in Frontend**

```
User Action
    │
    ├─> Click "Search for Rides"
    │       │
    │       ├─> searchRides() called
    │       │       │
    │       │       ├─> setLoading(true)
    │       │       ├─> POST /api/search
    │       │       ├─> Backend responds with proposals
    │       │       ├─> setProposals(data.proposals)
    │       │       └─> setLoading(false)
    │       │
    │       └─> Component re-renders
    │               │
    │               └─> Shows ride cards (proposals.length > 0)
    │
    ├─> Click "Book This Ride"
    │       │
    │       ├─> bookRide(proposal) called
    │       │       │
    │       │       ├─> setBooking(true)
    │       │       ├─> POST /api/book
    │       │       ├─> Backend responds with booking confirmation
    │       │       ├─> setBookedRide(proposal)
    │       │       └─> setBooking(false)
    │       │
    │       └─> Component re-renders
    │               │
    │               └─> Shows success message (bookedRide !== null)
    │
    └─> Click "Cancel This Ride"
            │
            ├─> cancelRide(rideId) called
            │       │
            │       ├─> setCancelling(true)
            │       ├─> POST /api/cancel
            │       ├─> Backend responds
            │       ├─> setBookedRide(null)
            │       └─> setCancelling(false)
            │
            └─> Component re-renders
                    │
                    └─> Returns to search screen
```

---

## Backend Architecture (Flask)

### 1. **Flask Application Setup** (`backend/api.py`)

```python
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allows React (port 3000) to call API (port 5000)
```

**What it does:**
- Creates Flask web server
- `CORS(app)` enables Cross-Origin Resource Sharing
  - Without this, browser would block requests from `localhost:3000` to `localhost:5000`
  - This is a security feature that prevents unauthorized cross-origin requests

### 2. **API Endpoints**

#### **A. GET /api/routes**

```python
@app.route('/api/routes', methods=['GET'])
def get_routes():
    routes = []
    for route_name, route_data in LOCATIONS.items():
        routes.append({
            "id": route_name,
            "name": route_name.replace("_", " ").title(),
            "origin": {...},
            "destination": {...}
        })
    return jsonify({"routes": routes})
```

**What it does:**
- Reads routes from `src/destination_config.py`
- Formats them for frontend consumption
- Returns JSON array of routes

**Request:** `GET http://localhost:5000/api/routes`
**Response:**
```json
{
  "routes": [
    {
      "id": "i_house_to_cathey",
      "name": "I House To Cathey",
      "origin": {
        "name": "I-House.",
        "data": { "latlng": {...}, "geocoded_addr": "I-House." }
      },
      "destination": {
        "name": "Cathey Dining Commons.",
        "data": { "latlng": {...}, "geocoded_addr": "Cathey Dining Commons." }
      }
    }
  ]
}
```

#### **B. POST /api/search**

```python
@app.route('/api/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    
    if 'route_id' in data:
        origin, destination = get_location_pair(data['route_id'])
    
    response = search_ride(origin, destination)
    return jsonify(response)
```

**What it does:**
1. Receives `route_id` from frontend
2. Looks up origin/destination from `destination_config.py`
3. Calls `search_ride(origin, destination)` from `src/search_ride.py`
4. `search_ride()` makes HTTP request to external RideSmart API
5. Filters out public transport proposals
6. Returns proposals to frontend

**Request:**
```json
POST http://localhost:5000/api/search
{
  "route_id": "i_house_to_cathey"
}
```

**Response:**
```json
{
  "proposals": [
    {
      "proposal_uuid": "abc123",
      "prescheduled_ride_id": 12345,
      "ride_info": {
        "pickup": {...},
        "dropoff": {...},
        "ride_cost": 0
      }
    }
  ]
}
```

#### **C. POST /api/book**

```python
@app.route('/api/book', methods=['POST'])
def book():
    data = request.get_json()
    prescheduled_ride_id = data.get('prescheduled_ride_id')
    proposal_uuid = data.get('proposal_uuid')
    origin = data.get('origin')
    destination = data.get('destination')
    
    response = book_ride(prescheduled_ride_id, proposal_uuid, origin, destination)
    return jsonify(response)
```

**What it does:**
1. Receives proposal IDs and route data from frontend
2. Calls `book_ride()` from `src/book_ride.py`
3. `book_ride()` makes HTTP request to external RideSmart API
4. Returns booking confirmation

**Request:**
```json
POST http://localhost:5000/api/book
{
  "prescheduled_ride_id": 12345,
  "proposal_uuid": "abc123",
  "origin": { "latlng": {...}, "geocoded_addr": "I-House." },
  "destination": { "latlng": {...}, "geocoded_addr": "Cathey Dining Commons." }
}
```

#### **D. POST /api/cancel**

```python
@app.route('/api/cancel', methods=['POST'])
def cancel():
    data = request.get_json()
    ride_id = data.get('ride_id')
    
    response = cancel_ride(ride_id)
    return jsonify(response)
```

**What it does:**
1. Receives ride ID from frontend
2. Calls `cancel_ride()` from `src/cancel_ride.py`
3. Makes HTTP request to external RideSmart API
4. Returns cancellation confirmation

### 3. **Python Module Structure**

```
src/
├── search_ride.py      # Makes HTTP request to external API
├── book_ride.py        # Makes HTTP request to external API
├── cancel_ride.py      # Makes HTTP request to external API
├── config.py           # Global config (auth token, battery level)
└── destination_config.py  # Route definitions (origin/destination pairs)
```

**How they work:**
- Each module contains functions that make HTTP requests using the `requests` library
- They format data according to RideSmart API requirements
- They return JSON responses or None on error

---

## Complete Data Flow

### Example: User Searches for Rides

```
1. User opens browser → React app loads (localhost:3000)
   │
   ├─> index.js renders App component
   │
   └─> useEffect runs → fetchRoutes()
           │
           └─> GET http://localhost:5000/api/routes
                   │
                   └─> Flask receives request
                           │
                           └─> Reads LOCATIONS from destination_config.py
                                   │
                                   └─> Returns JSON with routes
                                           │
                                           └─> Frontend sets routes state
                                                   │
                                                   └─> Shows route selector

2. User selects route and clicks "Search for Rides"
   │
   ├─> searchRides() called
   │       │
   │       ├─> setLoading(true) → Shows "Searching..." message
   │       │
   │       └─> POST http://localhost:5000/api/search
   │               │
   │               └─> Body: { "route_id": "i_house_to_cathey" }
   │                       │
   │                       └─> Flask receives request
   │                               │
   │                               ├─> Extracts route_id
   │                               │
   │                               ├─> Calls get_location_pair("i_house_to_cathey")
   │                               │       │
   │                               │       └─> Returns origin and destination objects
   │                               │
   │                               └─> Calls search_ride(origin, destination)
   │                                       │
   │                                       └─> search_ride.py makes POST request
   │                                               │
   │                                               └─> To: https://router-ucaca.live.ridewithvia.com/...
   │                                                       │
   │                                                       └─> External API responds with proposals
   │                                                               │
   │                                                               └─> search_ride() filters proposals
   │                                                                       │
   │                                                                       └─> Returns filtered proposals
   │                                                                               │
   │                                                                               └─> Flask returns JSON
   │                                                                                       │
   │                                                                                       └─> Frontend receives response
   │                                                                                               │
   │                                                                                               ├─> setProposals(data.proposals)
   │                                                                                               │
   │                                                                                               └─> setLoading(false)
   │                                                                                                       │
   │                                                                                                       └─> Component re-renders
   │                                                                                                               │
   │                                                                                                               └─> Shows ride cards
```

### Example: User Books a Ride

```
1. User clicks "Book This Ride" on a proposal
   │
   ├─> bookRide(proposal) called
   │       │
   │       ├─> setBooking(true) → Button shows "Booking..."
   │       │
   │       └─> POST http://localhost:5000/api/book
   │               │
   │               └─> Body: {
   │                       "prescheduled_ride_id": 12345,
   │                       "proposal_uuid": "abc123",
   │                       "origin": {...},
   │                       "destination": {...}
   │                   }
   │                       │
   │                       └─> Flask receives request
   │                               │
   │                               └─> Calls book_ride(prescheduled_ride_id, proposal_uuid, origin, destination)
   │                                       │
   │                                       └─> book_ride.py makes POST request
   │                                               │
   │                                               └─> To: https://router-ucaca.live.ridewithvia.com/.../book
   │                                                       │
   │                                                       └─> External API books the ride
   │                                                               │
   │                                                               └─> Returns booking confirmation
   │                                                                       │
   │                                                                       └─> Flask returns JSON
   │                                                                               │
   │                                                                               └─> Frontend receives response
   │                                                                                       │
   │                                                                                       ├─> setBookedRide(proposal)
   │                                                                                       │
   │                                                                                       └─> setBooking(false)
   │                                                                                               │
   │                                                                                               └─> Component re-renders
   │                                                                                                       │
   │                                                                                                       └─> Shows success message
```

---

## Key Concepts

### 1. **Separation of Concerns**

- **Frontend (React):** Handles UI, user interactions, state management
- **Backend (Flask):** Handles API calls, data processing, business logic
- **External API:** Actual RideSmart service

### 2. **Asynchronous Operations**

- All API calls use `async/await` or `.then()`
- Prevents UI from freezing during network requests
- Loading states provide user feedback

### 3. **State-Driven UI**

- UI is a function of state
- Changing state triggers re-render
- Conditional rendering shows/hides sections based on state

### 4. **REST API Pattern**

- GET: Retrieve data (routes)
- POST: Create/perform actions (search, book, cancel)
- JSON: Data format for requests and responses

### 5. **Error Handling**

- Try/catch blocks handle network errors
- Error state displays messages to user
- Backend returns error JSON with status codes

---

## File Structure Summary

```
Reversed-RideSmart/
├── frontend/                    # React frontend
│   ├── public/
│   │   └── index.html           # HTML template
│   ├── src/
│   │   ├── index.js             # React entry point
│   │   ├── index.css            # Global styles
│   │   ├── App.js               # Main component (all logic)
│   │   └── App.css              # Component styles
│   └── package.json             # Dependencies
│
├── backend/                     # Python backend
│   ├── src/                     # Python backend modules
│   │   ├── search_ride.py       # Search functionality
│   │   ├── book_ride.py         # Booking functionality
│   │   ├── cancel_ride.py       # Cancellation functionality
│   │   ├── config.py            # Global config
│   │   └── destination_config.py # Route definitions
│   ├── api.py                   # Flask API server
│   ├── main.py                  # CLI version (not used by frontend)
│   └── requirements.txt         # Python dependencies
```

---

## How to Run

1. **Start Backend:**
   ```bash
   cd backend
   python api.py
   # Runs on http://localhost:5000
   ```

2. **Start Frontend:**
   ```bash
   cd frontend
   npm install  # First time only
   npm start
   # Runs on http://localhost:3000
   ```

3. **Browser:**
   - Opens automatically to `http://localhost:3000`
   - Frontend makes requests to `http://localhost:5000`

---

## Summary

The architecture follows a **client-server model**:

- **Client (React):** Single-page application that manages UI and user interactions
- **Server (Flask):** REST API that processes requests and communicates with external services
- **Communication:** HTTP requests with JSON payloads
- **State Management:** React hooks (useState) for local component state
- **Data Flow:** Unidirectional (user action → API call → state update → UI re-render)

This separation allows the frontend and backend to be developed, tested, and deployed independently.

