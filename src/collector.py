import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parents[1]
HEALTH = ROOT / "data" / "source_health.json"


def clean(t):
    return re.sub(r"\\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()


def fetch_one(feed, limit=25):
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        parsed = feedparser.parse(feed["url"])
        rows = []
        for e in parsed.entries[:limit]:
            title = clean(e.get("title", ""))
            url = e.get("link", "")
            summary = clean(e.get("summary", "") or e.get("description", ""))
            if title and url:
                rows.append({
                    "title": title,
                    "url": url,
                    "source": feed["name"],
                    "source_category": feed["category"],
                    "primary_source": feed.get("primary", False),
                    "tier": feed.get("tier", 4),
                    "region": feed.get("region"),
                    "discovery": feed.get("discovery", False),
                    "summary": summary[:700],
                })
        status = getattr(parsed, "status", None)
        if status is None:
            status = 200 if rows else 0
        health = {
            "name": feed["name"],
            "url": feed["url"],
            "status": status,
            "entries": len(rows),
            "error": None,
            "checked_at": checked_at,
        }
        return rows, health
    except Exception as exc:
        return [], {
            "name": feed["name"],
            "url": feed["url"],
            "status": 0,
            "entries": 0,
            "error": str(exc),
            "checked_at": checked_at,
        }


def collect(feeds, limit=25, workers=12):
    out = []
    health = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(fetch_one, f, limit) for f in feeds]
        for job in as_completed(jobs):
            rows, result = job.result()
            out.extend(rows)
            health.append(result)

    health.sort(key=lambda x: x["name"].lower())
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": health,
    }, indent=2, ensure_ascii=False))
    return out
