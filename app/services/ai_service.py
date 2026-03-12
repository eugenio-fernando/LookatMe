"""
AI Productivity Assistant — OpenAI-powered insights.

Set AI_TEST_MODE=true to return mock responses without calling OpenAI.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ------------------------------------------------
# Mock responses (used when AI_TEST_MODE=true)
# ------------------------------------------------

_MOCK = {
    "summary": "Mock AI response",
    "suggestions": [
        "Complete your most important task first",
        "Maintain your habit streak",
        "Plan tomorrow tonight",
    ],
    "focus": "Finish one meaningful task before switching contexts."
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

# ------------------------------------------------
# Helpers
# ------------------------------------------------

def _test_mode() -> bool:
    return os.environ.get("AI_TEST_MODE", "").lower() == "true"


def _openai_client():
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
        messages=[
            {
                "role": "system",
                "content": "You are a concise productivity coach helping users improve focus and planning."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"},
        max_tokens=400,
        temperature=0.6,
    )

    return json.loads(response.choices[0].message.content)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%A, %B %d %Y")


def build_productivity_context(tasks: list, notes: list) -> dict:
    """
    Build structured productivity signals for prompt grounding.
    This avoids sending raw task lists to the model.
    """
    tasks_completed = sum(1 for t in tasks if t.get("completed"))
    tasks_pending = sum(1 for t in tasks if not t.get("completed"))
    notes_written = sum(1 for n in notes if n.get("text"))
    high_priority_tasks = [
        t.get("text", "")
        for t in tasks
        if not t.get("completed") and t.get("priority") == "high"
    ][:3]
    return {
        "tasks_completed": tasks_completed,
        "tasks_pending": tasks_pending,
        "notes_written": notes_written,
        "high_priority_tasks": high_priority_tasks,
    }


# ------------------------------------------------
# Daily analysis
# ------------------------------------------------

def analyze_day(tasks: list, notes: list) -> dict:
    """Combined AI call: summary + suggestions + focus."""
    
    if _test_mode():
        return _MOCK

    ctx = build_productivity_context(tasks, notes)

    prompt = f"""
Today is {_today()}.

User productivity snapshot:

Tasks completed: {ctx["tasks_completed"]}
Tasks remaining: {ctx["tasks_pending"]}
Notes written: {ctx["notes_written"]}
High priority tasks pending: {ctx["high_priority_tasks"] if ctx["high_priority_tasks"] else "none"}

Respond ONLY with JSON using this structure:

{{
"summary": "One short sentence summarizing today's productivity",
"suggestions": [
"Suggestion under 15 words",
"Suggestion under 15 words",
"Suggestion under 15 words"
],
"focus": "One concrete next action the user should focus on"
}}

Guidelines:
- Be concise
- Avoid repeating the numbers above
- Focus on actionable advice
"""

    return _chat(prompt)


# ------------------------------------------------
# Tomorrow planning
# ------------------------------------------------

def plan_tomorrow(tasks: list, notes: list) -> dict:

    if _test_mode():
        return _MOCK

    ctx = build_productivity_context(tasks, notes)

    prompt = f"""
You are planning tomorrow for a productivity-focused user.

Today's context:

Tasks still pending: {ctx["tasks_pending"]}
High priority tasks: {ctx["high_priority_tasks"] if ctx["high_priority_tasks"] else "none"}
Notes written today: {ctx["notes_written"]}

Respond ONLY with JSON:

{{
"top_3_priorities": [
"priority task idea",
"priority task idea",
"priority task idea"
],
"preparation_tip": "one concrete preparation step tonight",
"mindset": "short productivity mindset for tomorrow"
}}

Guidelines:
- Priorities should be realistic
- Keep suggestions short
"""

    return _chat(prompt)


# ------------------------------------------------
# Weekly report
# ------------------------------------------------

def weekly_report(stats: dict, tasks: list | None = None, notes: list | None = None) -> dict:

    if _test_mode():
        return _MOCK_WEEKLY

    context = build_productivity_context(tasks or [], notes or [])

    prompt = f"""
You are analyzing a user's productivity over the past week.

Week period: {stats['week_start']} to {stats['week_end']}

Metrics:
Tasks completed: {stats['tasks_completed']}
Habits completed: {stats['habits_completed']}
Notes written: {stats['notes_written']}

Current productivity signals:
Tasks pending now: {context['tasks_pending']}
High-priority tasks pending now: {context['high_priority_tasks'] if context['high_priority_tasks'] else "none"}
Notes created now: {context['notes_written']}

Respond ONLY with JSON:

{{
"summary": "2 sentence overview of the week",
"insights": [
"insight",
"insight",
"insight"
],
"suggestions": [
"suggestion",
"suggestion",
"suggestion"
]
}}

Focus on patterns and improvement ideas.
"""

    return _chat(prompt)


# ------------------------------------------------
# Notes summarization
# ------------------------------------------------

def summarize_notes(notes: list) -> dict:

    if _test_mode():
        return _MOCK

    texts = [n.get("text", "")[:120] for n in notes if n.get("text")]

    if not texts:
        return {
            "summary": "No notes found.",
            "key_themes": [],
            "action_items": []
        }

    limited = texts[:5]

    prompt = f"""
These are recent productivity notes from a user:

{chr(10).join(f"- {t}" for t in limited)}

Respond ONLY with JSON:

{{
"summary": "2 sentence synthesis",
"key_themes": [
"theme",
"theme",
"theme"
],
"action_items": [
"action",
"action",
"action"
]
}}

Focus on extracting meaning and concrete actions.
"""

    return _chat(prompt)


def ask_assistant(prompt_text: str, tasks: list, notes: list) -> dict:
    """Free-form assistant answer grounded in structured productivity context."""
    if _test_mode():
        return {"answer": "Mock answer: start with one high-impact task and review progress tonight."}

    context = build_productivity_context(tasks, notes)
    prompt = f"""
You are a practical productivity assistant.

User question:
{prompt_text}

User context signals:
- Tasks completed: {context['tasks_completed']}
- Tasks pending: {context['tasks_pending']}
- Notes written: {context['notes_written']}
- High priority pending: {context['high_priority_tasks'] if context['high_priority_tasks'] else "none"}

Respond ONLY as JSON:
{{
  "answer": "A concise helpful answer with concrete next steps"
}}
"""
    return _chat(prompt)
