"""Nickname generation helpers for user profiles."""

from __future__ import annotations

import random

# Curated nickname parts requested by product spec.
ADJECTIVES = [
    "Strategic",
    "Relentless",
    "Silent",
    "Curious",
    "Focused",
    "Bold",
    "Persistent",
    "Visionary",
]

ROLES = [
    "Builder",
    "Architect",
    "Explorer",
    "Strategist",
    "Creator",
    "Optimizer",
    "Planner",
]


def generate_nickname() -> str:
    """Return a random nickname in the format: "Adjective Role"."""
    return f"{random.choice(ADJECTIVES)} {random.choice(ROLES)}"
