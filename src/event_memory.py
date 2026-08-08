import hashlib
import re
from datetime import datetime, timezone, timedelta

def init_events(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS events(
        event_id TEXT PRIMARY KEY,
        canonical_title TEXT NOT NULL,
        category TEXT,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        major INTEGER DEFAULT 0,
        queued_count INTEGER DEFAULT 0
    )
    """)
    conn.commit()

def _tokens(text):
    return set(re.findall(r"[a-z0-9][a-z0-9'-]*", (text or "").lower()))

def _sim(a, b):
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))

def _new_id(title):
    return hashlib.sha256(title.strip().lower().encode()).hexdigest()[:24]

def decide(conn, item, memory_hours=48, major_memory_hours=168):
    now = datetime.now(timezone.utc)
    rows = conn.execute(
        "SELECT event_id,canonical_title,first_seen,last_seen,major FROM events"
    ).fetchall()
    best = None
    best_sim = 0.0
    for row in rows:
        event_id, canonical, first_seen, last_seen, major = row
        try:
            last = datetime.fromisoformat(last_seen.replace("Z","+00:00"))
        except Exception:
            continue
        hours = memory_hours if not major else major_memory_hours
        if (now - last).total_seconds() > hours * 3600:
            continue
        sim = _sim(item.get("title",""), canonical)
        if sim > best_sim:
            best_sim, best = sim, row

    if best and best_sim >= 0.42:
        event_id, canonical, first_seen, last_seen, major = best
        conn.execute(
            "UPDATE events SET last_seen=?, major=MAX(major,?) WHERE event_id=?",
            (now.isoformat(), int(item.get("priority_score", item.get("score",0)) >= 85), event_id)
        )
        status = "UPDATE"
        return status, event_id, best_sim

    event_id = _new_id(item.get("title","") + "|" + item.get("source",""))
    conn.execute(
        "INSERT OR REPLACE INTO events(event_id,canonical_title,category,first_seen,last_seen,major,queued_count) VALUES(?,?,?,?,?,?,0)",
        (
            event_id,
            item.get("title",""),
            item.get("category","world"),
            now.isoformat(),
            now.isoformat(),
            int(item.get("priority_score", item.get("score",0)) >= 85),
        )
    )
    return "NEW", event_id, 1.0

def mark_queued(conn, event_id):
    conn.execute(
        "UPDATE events SET queued_count=queued_count+1 WHERE event_id=?",
        (event_id,)
    )
