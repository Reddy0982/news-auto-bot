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

    parts = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    return [
        clean_sentence(part)
        for part in parts
        if clean(part)
    ]


def label(item, breaking_min_score=75):
    score = item.get("score", 0)
    confidence = item.get(
        "confidence",
        "low"
    )
    category = item.get(
        "category",
        ""
    )
    primary = item.get(
        "primary_source",
        False
    )
    corroboration = item.get(
        "strong_corroboration",
        0
    )
    status = item.get(
        "event_status",
        "NEW"
    )

    # Low-confidence information is never presented as breaking.
    if confidence == "low":
        return "⚠️ UNCONFIRMED"

    # Existing event with new information.
    if status == "UPDATE":
        if score >= 80:
            return "🔴 UPDATE"

        return "📰 NEWS"

    # Breaking requires urgency + reliability +
    # meaningful verification.
    urgent_categories = {
        "conflict",
        "disaster",
        "politics",
        "finance",
        "health",
        "cybersecurity",
        "world",
    }

    urgent = bool(
        item.get("urgency_terms")
    )

    verified = (
        primary
        or corroboration >= 2
    )

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


def choose_context_sentences(
    summary,
    max_sentences=2
):
    """
    Select the most useful complete sentences
    from the source summary.

    Never cut a sentence in half.
    """
    sentences = split_sentences(
        summary
    )

    if not sentences:
        return []

    return sentences[
        :max_sentences
    ]


def make_source_sentence(source):
    """Always make the source a complete sentence."""
    source = clean(
        source or "Unknown"
    )

    if source.endswith(
        (".", "!", "?")
    ):
        return f"Source: {source}"

    return f"Source: {source}."


def make_headline_sentence(
    label_text,
    title
):
    """Always make the headline a complete sentence."""
    title = clean(title)

    if title.endswith(
        (".", "!", "?")
    ):
        return f"{label_text}: {title}"

    return f"{label_text}: {title}."


def build_single_post(
    item,
    breaking_min_score=75
):
    """
    Build one clean X post.

    Target:
        3 to 4 complete sentences.

    Public post contains ONLY:
        1. News label + headline
        2. Useful context
        3. Additional useful context when available
        4. Source

    Internal verification information is NOT included
    in the public X post.
    """

    lab = label(
        item,
        breaking_min_score
    )

    title = clean(
        item.get("title", "")
    )

    summary = clean(
        item.get("summary", "")
    )

    source = clean(
        item.get("source", "Unknown")
    )

    if not title:
        return ""

    headline = make_headline_sentence(
        lab,
        title
    )

    source_sentence = make_source_sentence(
        source
    )

    context_sentences = choose_context_sentences(
        summary,
        2
    )

    # ---------------------------------------------------------
    # Candidate 1
    #
    # Headline + 2 useful context sentences + source
    #
    # Preferred format: 4 sentences.
    # ---------------------------------------------------------
    if len(context_sentences) >= 2:

        candidate = [
            headline,
            context_sentences[0],
            context_sentences[1],
            source_sentence,
        ]

        post = " ".join(
            candidate
        )

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Candidate 2
    #
    # Headline + 1 useful context sentence + source
    #
    # Exactly 3 sentences.
    # ---------------------------------------------------------
    if len(context_sentences) >= 1:

        candidate = [
            headline,
            context_sentences[0],
            source_sentence,
        ]

        post = " ".join(
            candidate
        )

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Candidate 3
    #
    # Headline + source.
    #
    # Only used when the headline/context combination
    # cannot fit within the X character limit.
    # ---------------------------------------------------------
    candidate = [
        headline,
        source_sentence,
    ]

    post = " ".join(
        candidate
    )

    if len(post) <= POST_LIMIT:
        return post

    # ---------------------------------------------------------
    # Extremely long title fallback.
    #
    # Preserve complete words and always keep the source.
    # ---------------------------------------------------------
    available = (
        POST_LIMIT
        - len(source_sentence)
        - 1
    )

    words = headline.split()
    compact_words = []

    for word in words:

        test = " ".join(
            compact_words + [word]
        )

        if len(test) <= available:
            compact_words.append(
                word
            )
        else:
            break

    compact_headline = " ".join(
        compact_words
    )

    if compact_headline:
        return (
            f"{compact_headline} "
            f"{source_sentence}"
        )

    return source_sentence


def choose_format(item):
    """
    Use a thread only when the story genuinely contains
    enough important information to justify one.
    """

    summary_length = len(
        item.get(
            "summary",
            ""
        )
    )

    score = item.get(
        "score",
        0
    )

    corroboration = item.get(
        "strong_corroboration",
        0
    )

    status = item.get(
        "event_status",
        "NEW"
    )

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


def build_thread(
    item,
    breaking_min_score=75
):
    """
    Build a small thread from complete sentences.

    Every post remains independently readable
    and <= POST_LIMIT.

    Verification metadata is NOT published.
    """

    lab = label(
        item,
        breaking_min_score
    )

    title = clean(
        item.get("title", "")
    )

    summary = clean(
        item.get("summary", "")
    )

    source = clean(
        item.get(
            "source",
            "Unknown"
        )
    )

    context = choose_context_sentences(
        summary,
        5
    )

    first = make_headline_sentence(
        lab,
        title
    )

    posts = [
        first
    ]

    current = ""

    for sentence in context:

        candidate = (
            sentence
            if not current
            else f"{current} {sentence}"
        )

        if len(candidate) <= POST_LIMIT:
            current = candidate

        else:
            if current:
                posts.append(
                    current
                )

            current = sentence

    if current:
        posts.append(
            current
        )

    source_line = make_source_sentence(
        source
    )

    # Add source to the final thread post
    # when it fits.
    if (
        len(posts[-1])
        + len(source_line)
        + 1
        <= POST_LIMIT
    ):
        posts[-1] = (
            f"{posts[-1]} "
            f"{source_line}"
        )
    else:
        posts.append(
            source_line
        )

    posts = [
        post.strip()
        for post in posts
        if post.strip()
    ]

    return posts


def format_story(
    item,
    breaking_min_score=75
):
    """
    Main formatter entry point.
    """

    chosen_format = choose_format(
        item
    )

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
