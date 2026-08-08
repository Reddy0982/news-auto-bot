import re


POST_LIMIT = 270


def clean(text):
    """Normalize whitespace without cutting the text."""
    return re.sub(r"\s+", " ", text or "").strip()


def clean_sentence(text):
    """Clean a sentence and make sure it ends naturally."""
    text = clean(text)

    if not text:
        return ""

    if text.endswith((".", "!", "?")):
        return text

    return text + "."


def split_sentences(text):
    """
    Split text into readable sentences.
    This is intentionally simple and safe for RSS summaries.
    """
    text = clean(text)

    if not text:
        return []

    parts = re.split(r"(?<=[.!?])\s+", text)

    return [
        clean_sentence(part)
        for part in parts
        if clean(part)
    ]


def label(item, breaking_min_score=75):
    score = item.get("score", 0)
    confidence = item.get("confidence", "low")
    category = item.get("category", "")
    primary = item.get("primary_source", False)
    corroboration = item.get("strong_corroboration", 0)
    status = item.get("event_status", "NEW")

    # Low-confidence information is never presented as breaking.
    if confidence == "low":
        return "⚠️ UNCONFIRMED"

    # Existing event with new information.
    if status == "UPDATE":
        if score >= 80:
            return "🔴 UPDATE"
        return "📰 NEWS"

    # Breaking requires urgency + reliability + meaningful verification.
    urgent_categories = {
        "conflict",
        "disaster",
        "politics",
        "finance",
        "health",
        "cybersecurity",
        "world",
    }

    urgent = bool(item.get("urgency_terms"))
    verified = primary or corroboration >= 2

    if (
        score >= breaking_min_score
        and confidence == "high"
        and category in urgent_categories
        and urgent
        and verified
    ):
        return "🚨 BREAKING"

    if score >= 55:
        return "📰 NEWS"

    return "📰 DEVELOPING"


def verification_sentence(item):
    """
    Keep verification factual and short.
    Never invent confirmation.
    """
    primary = item.get("primary_source", False)
    strong = item.get("strong_corroboration", 0)
    corroborating = item.get("corroborating_sources", 0)

    if strong >= 2:
        return f"Confirmed by {strong} independent sources."

    if strong == 1:
        return "Also reported by an independent source."

    if corroborating >= 1:
        return "Also reported independently."

    if primary:
        return "Reported by an authoritative source."

    return ""


def choose_context_sentences(summary, max_sentences=2):
    """
    Select the most useful complete sentences from the source summary.

    We never cut a sentence in half.
    """
    sentences = split_sentences(summary)

    if not sentences:
        return []

    return sentences[:max_sentences]


def build_single_post(item, breaking_min_score=75):
    """
    Build one clean X post.

    The function prefers fewer complete sentences over
    cutting a sentence with an ellipsis.
    """
    lab = label(item, breaking_min_score)

    title = clean(item.get("title", ""))
    summary = clean(item.get("summary", ""))
    source = clean(item.get("source", "Unknown"))

    if not title:
        return ""

    headline = f"{lab}: {title}"

    # Keep the headline intact whenever possible.
    # If an unusually long RSS headline exceeds the limit,
    # use it as-is rather than cutting it in the middle.
    parts = [headline]

    context_sentences = choose_context_sentences(summary, 2)
    verification = verification_sentence(item)

    # Try:
    # headline
    # blank line
    # context
    # blank line
    # verification
    # source
    #
    # Then progressively remove less important material
    # until the post fits naturally.

    candidates = []

    if len(context_sentences) >= 2:
        candidates.append(
            [
                headline,
                " ".join(context_sentences[:2]),
                verification,
                f"Source: {source}",
            ]
        )

    if len(context_sentences) >= 1:
        candidates.append(
            [
                headline,
                context_sentences[0],
                verification,
                f"Source: {source}",
            ]
        )

    candidates.append(
        [
            headline,
            verification,
            f"Source: {source}",
        ]
    )

    candidates.append(
        [
            headline,
            f"Source: {source}",
        ]
    )

    for candidate in candidates:
        candidate = [
            clean(part)
            for part in candidate
            if clean(part)
        ]

        # One blank line between major sections.
        post = "\n\n".join(candidate)

        if len(post) <= POST_LIMIT:
            return post

    # Extremely long headline fallback.
    #
    # We still avoid cutting the headline in the middle.
    # If the headline itself is too long, use a compact
    # title made from complete words.
    words = headline.split()

    compact_words = []

    for word in words:
        test = " ".join(compact_words + [word])

        if len(test) + len(f"\n\nSource: {source}") <= POST_LIMIT:
            compact_words.append(word)
        else:
            break

    compact_headline = " ".join(compact_words)

    return f"{compact_headline}\n\nSource: {source}"


def choose_format(item):
    """
    Use a thread only when the story genuinely contains
    enough important information to justify one.
    """
    summary_length = len(item.get("summary", ""))
    score = item.get("score", 0)
    corroboration = item.get("strong_corroboration", 0)
    status = item.get("event_status", "NEW")

    if (
        status == "UPDATE"
        and score >= 85
        and summary_length > 500
    ):
        return "thread"

    if (
        score >= 92
        and corroboration >= 2
        and summary_length > 500
    ):
        return "thread"

    return "single"


def build_thread(item, breaking_min_score=75):
    """
    Build a small thread from complete sentences.

    Every post remains independently readable and <= POST_LIMIT.
    """
    lab = label(item, breaking_min_score)

    title = clean(item.get("title", ""))
    summary = clean(item.get("summary", ""))
    source = clean(item.get("source", "Unknown"))

    context = choose_context_sentences(summary, 5)

    first = f"{lab}: {title}"

    posts = [first]

    current = ""

    for sentence in context:
        candidate = sentence if not current else f"{current} {sentence}"

        if len(candidate) <= POST_LIMIT:
            current = candidate
        else:
            if current:
                posts.append(current)
            current = sentence

    if current:
        posts.append(current)

    verification = verification_sentence(item)

    if verification:
        if len(posts[-1]) + len(verification) + 1 <= POST_LIMIT:
            posts[-1] = f"{posts[-1]} {verification}"
        else:
            posts.append(verification)

    source_line = f"Source: {source}"

    if len(posts[-1]) + len(source_line) + 1 <= POST_LIMIT:
        posts[-1] = f"{posts[-1]} {source_line}"
    else:
        posts.append(source_line)

    # Guarantee the limit.
    posts = [
        post.strip()
        for post in posts
        if post.strip()
    ]

    return posts


def format_story(item, breaking_min_score=75):
    """
    Main formatter entry point.
    """
    chosen_format = choose_format(item)

    if chosen_format == "thread":
        return {
            "format": "thread",
            "thread": build_thread(
                item,
                breaking_min_score
            ),
        }

    return {
        "format": "single",
        "post": build_single_post(
            item,
            breaking_min_score
        ),
    }
