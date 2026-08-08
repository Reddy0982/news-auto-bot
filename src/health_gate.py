import json
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]

Q = ROOT / "data" / "queue.json"
M = ROOT / "data" / "metrics.json"
H = ROOT / "data" / "source_health.json"
OUT = ROOT / "data" / "health.json"


# =========================================================
# HELPERS
# =========================================================

def load_json(path, default):
    """
    Safely load a JSON file.

    If the file does not exist or is invalid,
    return the supplied default.
    """

    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return default


def source_recent_entries(source):
    """
    Read the number of usable/recent entries.

    New collector format:
        recent_entries

    Older collector format:
        entries
    """

    value = source.get(
        "recent_entries"
    )

    if value is None:
        value = source.get(
            "entries",
            0
        )

    try:
        return int(
            value or 0
        )

    except Exception:
        return 0


def current_quality_failures(queue):
    """
    Count quality failures in the CURRENT queue.

    These stories are already held and therefore
    should NOT block valid stories from continuing.

    A quality failure is treated as a per-story problem,
    not a system-wide RED condition.
    """

    count = 0

    for item in queue.get(
        "held",
        []
    ):

        reason = str(
            item.get(
                "hold_reason",
                ""
            )
        ).lower()

        if (
            "quality check failed"
            in reason
        ):
            count += 1

    return count


# =========================================================
# MAIN HEALTH GATE
# =========================================================

def main():

    reasons = []
    warnings = []

    # -----------------------------------------------------
    # Load current run data
    # -----------------------------------------------------

    metrics = load_json(
        M,
        {}
    )

    queue = load_json(
        Q,
        {
            "stories": [],
            "count": 0,
            "held_count": 0,
            "held": []
        }
    )

    source = load_json(
        H,
        {
            "sources": []
        }
    )

    # -----------------------------------------------------
    # Source health
    # -----------------------------------------------------

    sources = source.get(
        "sources",
        []
    )

    if not sources:

        reasons.append(
            "no source-health results"
        )

    else:

        unusable = 0

        for item in sources:

            recent_entries = (
                source_recent_entries(
                    item
                )
            )

            status = item.get(
                "status"
            )

            # A source is unusable only when:
            #
            # 1. It returned no usable entries
            # AND
            # 2. It did not return a normal HTTP success.

            if (
                recent_entries == 0
                and status not in (
                    200,
                    304
                )
            ):
                unusable += 1

        unusable_ratio = (
            unusable
            / max(
                1,
                len(sources)
            )
        )

        # More than 60% unavailable = RED.
        if unusable_ratio > 0.60:

            reasons.append(
                "more than 60% of sources "
                "returned no usable entries"
            )

        # More than 30% but <= 60% = YELLOW.
        elif unusable_ratio > 0.30:

            warnings.append(
                "more than 30% of sources "
                "returned no usable entries"
            )

    # -----------------------------------------------------
    # Queue statistics
    # -----------------------------------------------------

    ready = int(
        queue.get(
            "count",
            0
        )
        or 0
    )

    held = int(
        queue.get(
            "held_count",
            len(
                queue.get(
                    "held",
                    []
                )
            )
        )
        or 0
    )

    # -----------------------------------------------------
    # Current quality failures
    # -----------------------------------------------------

    current_quality_failures_count = (
        current_quality_failures(
            queue
        )
    )

    # -----------------------------------------------------
    # IMPORTANT CHANGE
    #
    # Quality failures are NOT RED anymore.
    #
    # A failed story is held and ignored.
    # Other valid stories can continue.
    # -----------------------------------------------------

    if current_quality_failures_count > 0:

        warnings.append(
            f"{current_quality_failures_count} "
            "story/stories held because of quality failure"
        )

    # -----------------------------------------------------
    # Translation
    # -----------------------------------------------------

    translation_hold = int(
        metrics.get(
            "translation_held",
            0
        )
        or 0
    )

    if translation_hold > 50:

        warnings.append(
            "large translation backlog"
        )

    # -----------------------------------------------------
    # Stories seen
    # -----------------------------------------------------

    seen = int(
        metrics.get(
            "stories_seen",
            0
        )
        or 0
    )

    # -----------------------------------------------------
    # Hold-rate warning
    # -----------------------------------------------------

    if (
        seen >= 20
        and held / seen > 0.90
    ):

        warnings.append(
            "very high hold rate"
        )

    # -----------------------------------------------------
    # Publishable-story rate
    # -----------------------------------------------------

    if (
        seen >= 20
        and ready / seen > 0.50
    ):

        reasons.append(
            "unusually high publishable-story rate"
        )

    # -----------------------------------------------------
    # No ready stories
    #
    # IMPORTANT:
    #
    # This is NOT RED.
    #
    # Having zero ready stories simply means there
    # is nothing to publish during this run.
    # The next collection cycle can try again.
    # -----------------------------------------------------

    if ready == 0:

        warnings.append(
            "no stories are currently ready"
        )

    # -----------------------------------------------------
    # Determine health status
    # -----------------------------------------------------

    if reasons:

        status = "RED"

    elif warnings:

        status = "YELLOW"

    else:

        status = "GREEN"

    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "status": status,

        "checked_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "reasons": reasons,

        "warnings": warnings,

        "ready": ready,

        "held": held,

        "stories_seen": seen,

        "current_quality_failures": (
            current_quality_failures_count
        ),

        # Keep historical failures visible for diagnostics.
        #
        # They DO NOT determine the current health status.
        "historical_quality_failures": (
            int(
                metrics.get(
                    "quality_failures",
                    0
                )
                or 0
            )
        ),

        "source_count": len(
            sources
        ),

        "translation_held": (
            translation_hold
        )
    }

    # =====================================================
    # SAVE
    # =====================================================

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # =====================================================
    # DISPLAY
    # =====================================================

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )

    # =====================================================
    # CI SAFETY
    #
    # Only genuine system-wide RED conditions fail CI.
    #
    # Individual quality failures do NOT fail CI.
    # =====================================================

    if status == "RED":

        raise SystemExit(2)


if __name__ == "__main__":
    main()
