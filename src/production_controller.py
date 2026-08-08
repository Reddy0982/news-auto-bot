import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta


ROOT = Path(__file__).resolve().parents[1]

HEALTH = ROOT / "data" / "health.json"
QUEUE = ROOT / "data" / "queue.json"
STATE = ROOT / "data" / "production_state.json"


def load(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text()
        )
    except Exception:
        return default


def save(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        )
    )


def controller():
    health = load(
        HEALTH,
        {"status": "RED"}
    )

    queue = load(
        QUEUE,
        {
            "stories": [],
            "count": 0
        }
    )

    state = load(
        STATE,
        {
            "live_enabled": False,
            "kill_switch": True,
            "daily_post_count": 0,
            "last_reset_date": None,
            "recent_post_times": []
        }
    )

    now = datetime.now(
        timezone.utc
    )

    today = now.date().isoformat()

    # ---------------------------------------------------------
    # SAFETY LIMITS
    # ---------------------------------------------------------

    daily_limit = int(
        os.getenv(
            "X_DAILY_POST_LIMIT",
            "40"
        )
    )

    half_hour_limit = int(
        os.getenv(
            "X_HALF_HOUR_POST_LIMIT",
            "3"
        )
    )

    # ---------------------------------------------------------
    # DAILY RESET
    # ---------------------------------------------------------

    if (
        state.get("last_reset_date")
        != today
    ):
        state["daily_post_count"] = 0
        state["last_reset_date"] = today

        # Old timestamps are no longer
        # useful after a new UTC day.
        state["recent_post_times"] = []

    # ---------------------------------------------------------
    # CLEAN OLD POST TIMESTAMPS
    #
    # Keep only posts from the last 30 minutes.
    # ---------------------------------------------------------

    recent_post_times = []

    for value in state.get(
        "recent_post_times",
        []
    ):

        try:
            timestamp = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

            age = (
                now - timestamp
            ).total_seconds()

            if (
                0 <= age < 1800
            ):
                recent_post_times.append(
                    timestamp.isoformat()
                )

        except Exception:
            continue

    state["recent_post_times"] = (
        recent_post_times
    )

    # ---------------------------------------------------------
    # ENVIRONMENT CONTROLS
    # ---------------------------------------------------------

    live_requested = (
        os.getenv(
            "X_PUBLISH_ENABLED",
            "false"
        ).lower()
        == "true"
    )

    kill_switch = (
        os.getenv(
            "X_KILL_SWITCH",
            "true"
        ).lower()
        == "true"
    )

    reasons = []

    # ---------------------------------------------------------
    # SAFETY CHECKS
    # ---------------------------------------------------------

    if not live_requested:
        reasons.append(
            "live publishing is disabled"
        )

    if kill_switch:
        reasons.append(
            "kill switch is active"
        )

    if health.get("status") == "RED":
        reasons.append(
            "health gate is RED"
        )

    if daily_limit <= 0:
        reasons.append(
            "daily post limit is zero"
        )

    if (
        state.get(
            "daily_post_count",
            0
        )
        >= daily_limit
    ):
        reasons.append(
            "daily post limit reached"
        )

    half_hour_count = len(
        state.get(
            "recent_post_times",
            []
        )
    )

    if half_hour_limit <= 0:
        reasons.append(
            "30-minute post limit is zero"
        )

    if (
        half_hour_count
        >= half_hour_limit
    ):
        reasons.append(
            "30-minute post limit reached"
        )

    # ---------------------------------------------------------
    # FINAL DECISION
    # ---------------------------------------------------------

    allowed = not reasons

    result = {
        "checked_at": now.isoformat(),

        "live_requested":
            live_requested,

        "kill_switch":
            kill_switch,

        "health":
            health.get(
                "status"
            ),

        "daily_limit":
            daily_limit,

        "daily_post_count":
            state.get(
                "daily_post_count",
                0
            ),

        "half_hour_limit":
            half_hour_limit,

        "half_hour_post_count":
            half_hour_count,

        "ready_count":
            queue.get(
                "count",
                0
            ),

        "allowed":
            allowed,

        "reasons":
            reasons,
    }

    # ---------------------------------------------------------
    # STORE CONTROLLER STATE
    # ---------------------------------------------------------

    state["live_enabled"] = allowed
    state["kill_switch"] = kill_switch

    save(
        STATE,
        state
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )

    return result


if __name__ == "__main__":
    controller()
