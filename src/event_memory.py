import hashlib
import re
from datetime import datetime, timezone


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
    return set(
        re.findall(
            r"[a-z0-9][a-z0-9'-]*",
            (text or "").lower()
        )
    )


def _sim(a, b):
    aa, bb = _tokens(a), _tokens(b)

    if not aa or not bb:
        return 0.0

    return len(aa & bb) / max(1, len(aa | bb))


def _new_id(title):
    return hashlib.sha256(
        title.strip().lower().encode()
    ).hexdigest()[:24]


def _same_event_source(conn, event_id, source):
    """
    Check whether this source has already produced a story
    belonging to this event.
    """
    if not source:
        return False

    row = conn.execute(
        """
        SELECT 1
        FROM stories
        WHERE event_id=? AND source=?
        LIMIT 1
        """,
        (event_id, source)
    ).fetchone()

    return row is not None


def decide(
    conn,
    item,
    memory_hours=48,
    major_memory_hours=168
):
    now = datetime.now(timezone.utc)

    rows = conn.execute(
        """
        SELECT
            event_id,
            canonical_title,
            first_seen,
            last_seen,
            major,
            queued_count
        FROM events
        """
    ).fetchall()

    best = None
    best_sim = 0.0

    for row in rows:
        (
            event_id,
            canonical,
            first_seen,
            last_seen,
            major,
            queued_count,
        ) = row

        try:
            last = datetime.fromisoformat(
                last_seen.replace("Z", "+00:00")
            )
        except Exception:
            continue

        hours = (
            major_memory_hours
            if major
            else memory_hours
        )

        if (
            now - last
        ).total_seconds() > hours * 3600:
            continue

        sim = _sim(
            item.get("title", ""),
            canonical
        )

        if sim > best_sim:
            best_sim = sim
            best = row

    # No sufficiently similar recent event.
    if not best or best_sim < 0.42:
        event_id = _new_id(
            item.get("title", "")
            + "|"
            + item.get("source", "")
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO events(
                event_id,
                canonical_title,
                category,
                first_seen,
                last_seen,
                major,
                queued_count
            )
            VALUES(?,?,?,?,?,?,0)
            """,
            (
                event_id,
                item.get("title", ""),
                item.get("category", "world"),
                now.isoformat(),
                now.isoformat(),
                int(
                    item.get(
                        "priority_score",
                        item.get("score", 0)
                    ) >= 85
                ),
            )
        )

        return "NEW", event_id, 1.0

    (
        event_id,
        canonical,
        first_seen,
        last_seen,
        major,
        queued_count,
    ) = best

    source = item.get("source", "")

    # Same event AND same source means this is a duplicate
    # of coverage we have already seen.
    if _same_event_source(
        conn,
        event_id,
        source
    ):
        conn.execute(
            """
            UPDATE events
            SET last_seen=?,
                major=MAX(major,?)
            WHERE event_id=?
            """,
            (
                now.isoformat(),
                int(
                    item.get(
                        "priority_score",
                        item.get("score", 0)
                    ) >= 85
                ),
                event_id,
            )
        )

        return "DUPLICATE", event_id, best_sim

    # Same event from another source.
    # Keep it as an UPDATE so independent coverage can
    # provide additional information.
    conn.execute(
        """
        UPDATE events
        SET last_seen=?,
            major=MAX(major,?)
        WHERE event_id=?
        """,
        (
            now.isoformat(),
            int(
                item.get(
                    "priority_score",
                    item.get("score", 0)
                ) >= 85
            ),
            event_id,
        )
    )

    return "UPDATE", event_id, best_sim


def mark_queued(conn, event_id):
    conn.execute(
        """
        UPDATE events
        SET queued_count=queued_count+1
        WHERE event_id=?
        """,
        (event_id,)
    )
