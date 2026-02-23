# Deployment Guide for RideSmart

## Frontend Deployment (Vercel)

### Framework Selection
**Select: "Create React App"** (or "React" - Vercel will auto-detect)

### Steps:

1. **Install Vercel CLI** (optional, for local testing):
   ```bash
   npm i -g vercel
   ```

2. **Deploy from frontend directory:**
   ```bash
   cd frontend
   vercel
   ```
   
   Or connect your GitHub repo to Vercel dashboard and point it to the `frontend/` directory.

3. **Environment Variables:**
   - Set `REACT_APP_API_URL` to your backend API URL (e.g., `https://your-backend.railway.app`)

4. **Update API Base URL:**
   The frontend currently defaults to `http://localhost:5000`. You'll need to either:
   - Set the environment variable `REACT_APP_API_URL` in Vercel
   - Or update `frontend/src/App.js` line 4 to use your production backend URL

### Vercel Configuration
The `frontend/vercel.json` file is already configured for Create React App.

---

## Backend Deployment Options

Vercel doesn't support Flask directly. Here are your options:

### Option 1: Railway (Recommended - Easy Flask Deployment)

1. **Install Railway CLI:**
   ```bash
   npm i -g @railway/cli
   ```

2. **Deploy:**
   ```bash
   cd backend
   railway login
   railway init
   railway up
   ```

3. **Set Environment Variables** (if needed):
   - Railway will auto-detect Python and install from `requirements.txt`

4. **Update Start Command:**
   - Railway will need to know to run `python api.py`
   - This is usually auto-detected, but you can set it in Railway dashboard

### Option 2: Render

1. **Create a new Web Service** on Render
2. **Connect your GitHub repo**
3. **Settings:**
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python api.py`
   - **Environment:** Python 3

### Option 3: Fly.io

1. **Install Fly CLI:**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Create `backend/fly.toml`:**
   ```toml
   app = "your-app-name"
   primary_region = "iad"
   
   [build]
   
   [http_service]
     internal_port = 5000
     force_https = true
     auto_stop_machines = true
     auto_start_machines = true
     min_machines_running = 0
   
   [[services]]
     protocol = "tcp"
     internal_port = 5000
   ```

3. **Deploy:**
   ```bash
   cd backend
   fly launch
   fly deploy
   ```

### Option 4: Convert to Vercel Serverless Functions

If you want everything on Vercel, you'd need to convert Flask endpoints to Vercel serverless functions. This requires restructuring the backend.

**Example structure for Vercel:**
```
api/
  search.py      # Serverless function
  book.py        # Serverless function
  cancel.py      # Serverless function
  routes.py      # Serverless function
```

Each would be a separate serverless function instead of Flask routes.

---

## Recommended Setup

**Frontend:** Vercel (Create React App)
**Backend:** Railway or Render (Flask)

### Why This Works Best:
- ✅ Vercel excels at frontend hosting
- ✅ Railway/Render handle Flask/Python well
- ✅ Easy to set up and maintain
- ✅ Good free tiers for both

### After Deployment:

1. **Update Frontend API URL:**
   - In Vercel dashboard, set environment variable:
     - `REACT_APP_API_URL=https://your-backend-url.com`

2. **Update CORS in Backend:**
   - In `backend/api.py`, update CORS to allow your Vercel domain:
   ```python
   CORS(app, origins=["https://your-frontend.vercel.app"])
   ```

3. **Test the connection:**
   - Visit your Vercel frontend URL
   - It should connect to your backend API

---

## Quick Start (Railway + Vercel)

### Backend (Railway):
```bash
cd backend
railway login
railway init
railway up
# Note the URL Railway gives you (e.g., https://your-app.railway.app)
```

### Frontend (Vercel):
```bash
cd frontend
vercel
# When prompted, set REACT_APP_API_URL to your Railway URL
```

That's it! Your app should be live.

