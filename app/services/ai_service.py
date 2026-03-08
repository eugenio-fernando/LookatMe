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
    if _test_mode():
        return _MOCK
    today_tasks = [t for t in tasks if not t.get("completed")]
    done_tasks  = [t for t in tasks if t.get("completed")]
    note_texts  = [n.get("text", "") for n in notes if n.get("text")]

    prompt = f"""Today is {_today()}.

Tasks pending: {[t.get('text', '') for t in today_tasks]}
Tasks completed: {[t.get('text', '') for t in done_tasks]}
Notes written today: {note_texts[:5]}

Respond with a JSON object with these exact keys:
- "summary": 1-2 sentence summary of the day so far
- "focus_areas": list of 2-3 things to focus on next
- "momentum": a short motivational sentence based on progress"""

    return _chat(prompt)


def plan_tomorrow(tasks: list, notes: list) -> dict:
    if _test_mode():
        return _MOCK
    upcoming   = [t for t in tasks if not t.get("completed")]
    note_texts = [n.get("text", "") for n in notes if n.get("text")]

    prompt = f"""Today is {_today()}.

Upcoming tasks: {[t.get('text', '') for t in upcoming[:10]]}
Recent notes: {note_texts[:3]}

Respond with a JSON object with these exact keys:
- "top_3_priorities": list of 3 task suggestions for tomorrow
- "preparation_tip": one concrete thing to do tonight to be ready
- "mindset": a short focus intention for tomorrow"""

    return _chat(prompt)


def summarize_notes(notes: list) -> dict:
    if _test_mode():
        return _MOCK

    texts = [n.get("text", "") for n in notes if n.get("text")]

    if not texts:
        return {"summary": "No notes found.", "key_themes": [], "action_items": []}

    prompt = f"""Here are recent notes:

{chr(10).join(f'- {t}' for t in texts[:10])}

Respond with a JSON object with these exact keys:
- "summary": 2-3 sentence synthesis of the notes
- "key_themes": list of 3-5 recurring themes or topics
- "action_items": list of up to 3 actionable next steps extracted from the notes"""

    return _chat(prompt)
