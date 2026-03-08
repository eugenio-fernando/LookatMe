import random
import re


_MALE_NICKS = [
    "captain chaos",
    "handsome silly monkey",
    "legend in training",
    "mister sparkle-brain",
]

_FEMALE_NICKS = [
    "queen chaos",
    "crazy lady",
    "sunshine tornado",
    "boss butterfly",
]

_NEUTRAL_NICKS = [
    "chaos comet",
    "focus wizard",
    "sparkle gremlin",
    "productivity ninja",
]

_OPENERS_1 = [
    "Welcome back, {name}!",
    "Hey {name}, you made it back.",
    "Good to see you again, {name}.",
]

_OPENERS_2 = [
    "Round two today, {name}.",
    "Back again, {name}. I respect it.",
    "{name}, this comeback energy is elite.",
]

_OPENERS_3 = [
    "Third login today, {name}. Certified commitment.",
    "{name}, hat trick login achieved.",
    "You again, {name}. I like your discipline.",
]

_FUN_TAILS = [
    "Now go make Future You proud.",
    "Let's collect another win today.",
    "Time to turn effort into streaks.",
    "Try not to overthink it. Just start.",
]


def _clean_name(name: str) -> str:
    raw = (name or "").strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw[:40] if raw else "there"


def _pick_nickname(gender: str) -> str:
    g = (gender or "").strip().lower()
    if g == "male":
        return random.choice(_MALE_NICKS)
    if g == "female":
        return random.choice(_FEMALE_NICKS)
    return random.choice(_NEUTRAL_NICKS)


def build_fun_welcome(display_name: str, gender: str, login_count_today: int) -> str:
    """Generate a playful welcome text for first 3 logins in a day."""
    name = _clean_name(display_name)
    nick = _pick_nickname(gender)

    if login_count_today <= 1:
        opener = random.choice(_OPENERS_1)
    elif login_count_today == 2:
        opener = random.choice(_OPENERS_2)
    else:
        opener = random.choice(_OPENERS_3)

    tail = random.choice(_FUN_TAILS)
    return f"{opener.format(name=name)} Hello {nick}. {tail}"
