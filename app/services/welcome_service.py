import random
import re


_OPENERS_1 = [
    "Welcome back, {name}!",
    "Hey {name}, you survived the internet.",
    "Good to see you, {name}. Coffee secured?",
]

_OPENERS_2 = [
    "Round two today, {name}. Respect.",
    "{name} is back for another lap.",
    "Back again, {name}. The streak committee approves.",
]

_OPENERS_3 = [
    "Third login today, {name}. Quiet dedication.",
    "{name}, hat trick achieved.",
    "You again, {name}. This is getting productive.",
]

_FUN_TAILS = [
    "Let's ship one useful thing.",
    "Tiny progress still counts as progress.",
    "Start messy, fix later.",
    "Less scrolling, more finishing.",
]


def _clean_name(name: str) -> str:
    raw = (name or "").strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw[:40] if raw else "there"


def build_fun_welcome(display_name: str, gender: str, login_count_today: int) -> str:
    """Generate a playful welcome text for first 3 logins in a day."""
    name = _clean_name(display_name)
    _ = gender  # keep signature stable; tone is not gendered now

    if login_count_today <= 1:
        opener = random.choice(_OPENERS_1)
    elif login_count_today == 2:
        opener = random.choice(_OPENERS_2)
    else:
        opener = random.choice(_OPENERS_3)

    tail = random.choice(_FUN_TAILS)
    return f"{opener.format(name=name)} {tail}"
