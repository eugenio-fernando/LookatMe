"""
Write it Down — entry point.

Development:
    python run.py

Production (gunicorn + gthread):
    gunicorn "run:app" -k gthread --threads 4 -w 1 --bind 0.0.0.0:8080

Then open: http://localhost:8080
"""

from dotenv import load_dotenv

load_dotenv()  # loads .env when present; no-op in production if vars are set by the environment

from app import create_app          # noqa: E402  (import after load_dotenv)
from app.extensions import socketio  # noqa: E402

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    print(f"Write it Down running at http://localhost:{port}")
    socketio.run(app, debug=False, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)

