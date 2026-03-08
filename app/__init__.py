"""
Write it Down — Flask application factory.
"""

import logging
import math
import os
import struct
import zlib

from dotenv import load_dotenv
from flask import Flask, session # type: ignore

load_dotenv()  # no-op if .env is absent or vars are already set

from flask_socketio import join_room, leave_room # type: ignore

from .extensions import socketio
from .models.db import migrate_from_json_if_needed
from .routes.activity import activity_bp
from .routes.auth import auth_api_bp, auth_bp
from .routes.debug import debug_bp
from .routes.external import external_bp
from .routes.learning import learning_bp
from .routes.messages import messages_bp
from .routes.profile import profile_bp
from .routes.tasks import tasks_bp
from .routes.views import views_bp
from .routes.ai import ai_bp
from .routes.invites import invites_bp
from .routes.commitment import commitment_bp
from .routes.linkedin import linkedin_bp
from .routes.mission import mission_bp
from .routes.workspaces import workspaces_bp


def create_app() -> Flask:
    # Resolve DATABASE_URL if not already set (local dev fallback).
    # Production: entrypoint.sh exports this before gunicorn starts.
    if not os.environ.get("DATABASE_URL"):
        if os.path.isdir("/data"):
            os.environ["DATABASE_URL"] = "file:/data/lookatme.db"
        else:
            _db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "lookatme.db",
            )
            os.environ["DATABASE_URL"] = f"file:{_db_path}"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # Initialise SocketIO with threading async mode (no extra dependencies)
    socketio.init_app(
        app,
        async_mode="threading",
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    app.register_blueprint(activity_bp)
    app.register_blueprint(auth_bp)                              # page routes: /login, /verify/<token>, etc.
    app.register_blueprint(auth_api_bp, url_prefix="/api/auth")  # API routes: /api/auth/login, etc.
    app.register_blueprint(views_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(learning_bp)
    app.register_blueprint(external_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(workspaces_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(invites_bp)
    app.register_blueprint(commitment_bp)
    app.register_blueprint(linkedin_bp)
    app.register_blueprint(mission_bp)
    if os.environ.get("FLASK_ENV", "development") != "production":
        app.register_blueprint(debug_bp, url_prefix="/api/debug")

    # ── Socket event handlers ──────────────────────────────────────────
    @socketio.on("connect")
    def on_connect():
        user_id = session.get("user_id")
        if user_id:
            join_room(f"user_{user_id}")

    @socketio.on("disconnect")
    def on_disconnect():
        user_id = session.get("user_id")
        if user_id:
            leave_room(f"user_{user_id}")

    migrate_from_json_if_needed()
    _ensure_icons(os.path.join(app.static_folder, "icons"))

    return app


def _ensure_icons(icons_dir: str) -> None:
    """Generate 192×192 and 512×512 PNG icons if they don't already exist."""
    os.makedirs(icons_dir, exist_ok=True)

    def _png(size: int) -> bytes:
        BG = (0x1C, 0x1C, 0x1E)
        FG = (0x00, 0x7A, 0xFF)
        cx = cy = (size - 1) / 2
        radius = size * 0.38
        raw = bytearray()
        for y in range(size):
            raw.append(0)
            for x in range(size):
                raw.extend(FG if math.hypot(x - cx, y - cy) <= radius else BG)

        def chunk(tag: bytes, data: bytes) -> bytes:
            crc = zlib.crc32(tag + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

        ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )

    for size in (192, 512):
        path = os.path.join(icons_dir, f"icon-{size}.png")
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(_png(size))
