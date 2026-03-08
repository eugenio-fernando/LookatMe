"""
AI Productivity Assistant — OpenAI-powered insights.

Set AI_TEST_MODE=true to return mock responses without calling OpenAI.
"""
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_MOCK = {
    "summary":     "Mock AI response",
    "suggestions": [
        "Complete your most important task first",
        "Maintain your habit streak",
        "Plan tomorrow tonight",
    ],
}

_MOCK_WEEKLY = {
    "summary": "Strong week overall. You completed tasks consistently and maintained your daily habits.",
    "insights": [
        "You completed the most tasks on weekday mornings",
        "Note-taking correlated with higher task completion on the same days",
        "Your habit streak is building solid momentum",
    ],
    "suggestions": [
        "Plan your top 3 tasks the night before to hit the ground running",
        "Write a brief end-of-day note to close loops and reflect",
        "Aim to complete at least 3 tasks before noon for peak output",
    ],
}


def _test_mode() -> bool:
    return os.environ.get("AI_TEST_MODE", "").lower() == "true"


def _openai_client():
    import os
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed")
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key)


def _chat(prompt: str) -> dict:
    client = _openai_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=512,
        temperature=0.7,
    )
    return json.loads(response.choices[0].message.content)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%A, %B %d %Y")


def analyze_day(tasks: list, notes: list) -> dict:
    """Single combined call: day summary + 3 suggestions + focus sentence."""
    if _test_mode():
        return _MOCK
    done_count    = sum(1 for t in tasks if t.get("completed"))
    pending_count = sum(1 for t in tasks if not t.get("completed"))
    notes_count   = sum(1 for n in notes if n.get("text"))
    high_pri      = [t.get("text", "") for t in tasks
                     if not t.get("completed") and t.get("priority") == "high"][:3]

    prompt = f"""You are a productivity coach. Today is {_today()}.

User summary:
Tasks completed: {done_count}
Tasks remaining: {pending_count}
Notes written: {notes_count}
High-priority pending: {high_pri if high_pri else 'none'}

Respond with a JSON object with these exact keys:
- "summary": 1-2 sentence overview of the day so far
- "suggestions": list of exactly 3 actionable next steps
- "focus": one short motivational sentence"""

    return _chat(prompt)


def plan_tomorrow(tasks: list, notes: list) -> dict:
    if _test_mode():
        return _MOCK
    pending_count = sum(1 for t in tasks if not t.get("completed"))
    high_pri      = [t.get("text", "") for t in tasks
                     if not t.get("completed") and t.get("priority") == "high"][:3]
    notes_count   = sum(1 for n in notes if n.get("text"))

    prompt = f"""You are a productivity coach. Today is {_today()}.

User summary:
Tasks remaining: {pending_count}
High-priority pending: {high_pri if high_pri else 'none'}
Notes written today: {notes_count}

Respond with a JSON object with these exact keys:
- "top_3_priorities": list of 3 task suggestions for tomorrow
- "preparation_tip": one concrete thing to do tonight to be ready
- "mindset": a short focus intention for tomorrow"""

    return _chat(prompt)


def weekly_report(stats: dict) -> dict:
    if _test_mode():
        return _MOCK_WEEKLY

    prompt = f"""You are a productivity coach analyzing a user's weekly performance.

Week: {stats['week_start']} to {stats['week_end']}
Tasks completed: {stats['tasks_completed']}
Habits completed: {stats['habits_completed']}
Notes written: {stats['notes_written']}

Respond with a JSON object with these exact keys:
- "summary": 2-3 sentence overview of the week's performance
- "insights": list of exactly 3 specific observations about the user's patterns
- "suggestions": list of exactly 3 concrete improvement suggestions for next week"""

    return _chat(prompt)


def summarize_notes(notes: list) -> dict:
    if _test_mode():
        return _MOCK

    # Truncate each note to 120 chars to keep the prompt compact
    texts = [n.get("text", "")[:120] for n in notes if n.get("text")]

    if not texts:
        return {"summary": "No notes found.", "key_themes": [], "action_items": []}

    prompt = f"""You are a productivity coach. Here are {len(texts[:5])} recent notes:

{chr(10).join(f'- {t}' for t in texts[:5])}

Respond with a JSON object with these exact keys:
- "summary": 2-3 sentence synthesis of the notes
- "key_themes": list of 3-5 recurring themes or topics
- "action_items": list of up to 3 actionable next steps extracted from the notes"""

    return _chat(prompt)
