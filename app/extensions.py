"""
Shared Flask extensions — imported by the app factory and by blueprints that
need to emit socket events without triggering circular imports.
"""

from flask_socketio import SocketIO

socketio = SocketIO()
