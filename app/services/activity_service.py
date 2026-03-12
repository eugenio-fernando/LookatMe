"""Compatibility shim for activity service.

The activity feature service now lives in app.features.activity.service.
"""

from ..features.activity.service import get_feed_for_user, record_event

__all__ = ["record_event", "get_feed_for_user"]
