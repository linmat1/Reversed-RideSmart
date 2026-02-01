"""
Vercel entrypoint: expose the Flask app from api.py so Vercel finds it.
Set Vercel project Root Directory to "backend" so this file is at the app root.
"""
from api import app
