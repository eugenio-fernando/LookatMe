import json
import os
import random
from datetime import datetime, timedelta

import anthropic
import feedparser
import requests
from flask import Blueprint, jsonify, request, send_from_directory, session

from ..extensions import socketio
from ..models import db

external_bp = Blueprint("external", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Use the persistent volume in production, fall back to project root locally
_DATA_DIR = "/data" if os.path.isdir("/data") else BASE_DIR

FEEDS = {
    "all": [
        ("BBC",        "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("CNN",        "http://rss.cnn.com/rss/edition_world.rss"),
        ("Guardian",   "https://www.theguardian.com/world/rss"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("NPR",        "https://feeds.npr.org/1004/rss.xml"),
    ],
    "world": [
        ("BBC",        "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Guardian",   "https://www.theguardian.com/world/rss"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ],
    "tech": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge",  "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica","https://feeds.arstechnica.com/arstechnica/index"),
    ],
    "science": [
        ("BBC",          "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("NPR",          "https://feeds.npr.org/1007/rss.xml"),
        ("New Scientist","https://www.newscientist.com/feed/home/"),
    ],
    "health": [
        ("BBC", "http://feeds.bbci.co.uk/news/health/rss.xml"),
        ("NPR", "https://feeds.npr.org/1128/rss.xml"),
    ],
    "business": [
        ("BBC",     "http://feeds.bbci.co.uk/news/business/rss.xml"),
        ("NPR",     "https://feeds.npr.org/1006/rss.xml"),
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
    ],
    "sports": [
        ("BBC",        "http://feeds.bbci.co.uk/news/sport/rss.xml"),
        ("Sky Sports", "https://www.skysports.com/rss/12040"),
        ("ESPN",       "https://www.espn.com/espn/rss/news"),
    ],
}


@external_bp.route("/api/timer")
def timer():
    timer_file = os.path.join(_DATA_DIR, "timer_start.json")
    # Create on first access so the 180-day countdown starts from now
    if not os.path.exists(timer_file):
        with open(timer_file, "w") as f:
            json.dump({"start_time": datetime.now().isoformat()}, f)
    try:
        with open(timer_file) as f:
            data = json.load(f)
        start = datetime.fromisoformat(data["start_time"])
        end = start + timedelta(days=180)
        now = datetime.now()

        total_seconds = (end - start).total_seconds()
        elapsed_seconds = (now - start).total_seconds()
        remaining_seconds = max(0, (end - now).total_seconds())
        progress = min(100.0, (elapsed_seconds / total_seconds) * 100)

        rem = int(remaining_seconds)
        days = rem // 86400
        hours = (rem % 86400) // 3600
        minutes = (rem % 3600) // 60
        secs = rem % 60

        return jsonify({
            "progress":  round(progress, 2),
            "remaining": f"{days:03d}d {hours:02d}h {minutes:02d}m {secs:02d}s",
            "days_left": days,
            "end_date":  end.strftime("%B %d, %Y"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@external_bp.route("/api/streak")
def streak():
    return jsonify(db.get_streak())


@external_bp.route("/api/news")
def news():
    category = request.args.get("category", "all").lower()
    feeds = FEEDS.get(category, FEEDS["all"])

    items = []
    for source, url in feeds:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:5]:
                items.append({
                    "source":      source,
                    "title":       entry.title,
                    "link":        entry.get("link", "#"),
                    "description": entry.get("summary", ""),
                    "category":    category,
                })
        except Exception:
            continue

    random.shuffle(items)
    return jsonify(items[:10])


@external_bp.route("/api/summarize", methods=["POST"])
def summarize():
    body = request.get_json(silent=True) or {}
    title = body.get("title", "").strip()
    description = body.get("description", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "AI summarization is not configured"}), 503

    content = f"Headline: {title}"
    if description:
        content += f"\nDescription: {description}"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": (
                    "Summarize this news article in exactly 2 sentences. "
                    "Be factual and concise.\n\n" + content
                ),
            }],
        )
        return jsonify({"summary": message.content[0].text.strip()})
    except Exception:
        return jsonify({"error": "Failed to generate summary"}), 503


@external_bp.route("/api/notes")
def get_notes():
    notes_file = os.path.join(_DATA_DIR, "daily_notes.json")
    try:
        with open(notes_file) as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify([])


@external_bp.route("/api/notes", methods=["POST"])
def save_note():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()
    notes_file = os.path.join(_DATA_DIR, "daily_notes.json")
    try:
        with open(notes_file) as f:
            notes = json.load(f)
    except Exception:
        notes = []
    notes.append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": text})
    with open(notes_file, "w") as f:
        json.dump(notes, f, indent=2)
    uid = session.get("user_id")
    if uid:
        preview = text[:60] + ("…" if len(text) > 60 else "")
        activity = db.log_activity(uid, "note_created", f"Note: {preview}")
        socketio.emit("activity_created", {"activity": activity}, to=f"user_{uid}")
    return jsonify({"ok": True})


@external_bp.route("/api/verse")
def verse():
    try:
        resp = requests.get(
            "https://labs.bible.org/api/?passage=random&type=json", timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()[0]
            return jsonify({
                "text":      data["text"],
                "reference": f"{data['bookname']} {data['chapter']}:{data['verse']}",
            })
    except Exception:
        pass
    return jsonify({
        "text":      "The Lord is my shepherd; I shall not want.",
        "reference": "Psalm 23:1",
    })
