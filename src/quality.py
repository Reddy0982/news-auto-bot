import re


POST_LIMIT = 270


def sentence_count(text):
    text = (text or "").strip()

    if not text:
        return 0

    return len(re.findall(r"(?<=[.!?])\s+", text)) + 1


def has_source(text):
    return "Source:" in (text or "")


def quality_check(item):
    errors = []
    warnings = []

    fmt = item.get("format")

    if fmt == "single":
        post = item.get("post", "").strip()

        if not post:
            errors.append("empty post")

        if len(post) > POST_LIMIT:
            errors.append(
                f"single post exceeds {POST_LIMIT} characters"
            )

        # Normal single posts should contain
        # 3 to 4 useful sentences.
        if post:
            count = sentence_count(post)

            if count < 3:
                errors.append(
                    "single post has fewer than 3 sentences"
                )

            if count > 4:
                errors.append(
                    "single post has more than 4 sentences"
                )

        if post and not has_source(post):
            errors.append("single post missing source")

    elif fmt == "thread":
        thread = item.get("thread", [])

        if not thread:
            errors.append("empty thread")

        if len(thread) > 7:
            errors.append("thread too long")

        for i, post in enumerate(thread, 1):
            post = (post or "").strip()

            if not post:
                errors.append(
                    f"thread post {i} is empty"
                )
                continue

            if len(post) > POST_LIMIT:
                errors.append(
                    f"thread post {i} exceeds {POST_LIMIT} characters"
                )

        if thread and not has_source(thread[-1]):
            errors.append("thread missing source")

    else:
        errors.append("unknown format")

    # Final language check.
    if item.get("language_status") not in (
        "ENGLISH",
        "TRANSLATED_TO_ENGLISH",
    ):
        errors.append("final language is not English")

    # Source URL must be valid.
    if not item.get("url", "").startswith(
        ("http://", "https://")
    ):
        errors.append("invalid source URL")

    # Low-confidence stories can be warned about,
    # but must never claim confirmation.
    if item.get("confidence") == "low":
        warnings.append("low-confidence story")

    text_to_check = ""

    if fmt == "single":
        text_to_check = item.get("post", "")

    elif fmt == "thread":
        text_to_check = " ".join(
            item.get("thread", [])
        )

    if (
        re.search(
            r"\bconfirmed\b",
            text_to_check.lower()
        )
        and item.get("confidence") == "low"
    ):
        errors.append(
            "low-confidence story uses confirmed wording"
        )

    return {
        "quality_pass": not errors,
        "quality_errors": errors,
        "quality_warnings": warnings,
    }
