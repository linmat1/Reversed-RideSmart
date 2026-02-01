"""
Vercel Flask entrypoint at repo root.
Vercel looks for api/app.py; this file loads the app from backend/api.py.
"""
import sys
from pathlib import Path

# Ensure backend is on the path so backend/api.py and backend/src/* can be imported
_backend = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_backend))

from api import app
