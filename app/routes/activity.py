"""Compatibility shim for activity routes.

The activity feature blueprint now lives in app.features.activity.routes.
"""

from ..features.activity.routes import activity_bp

__all__ = ["activity_bp"]
