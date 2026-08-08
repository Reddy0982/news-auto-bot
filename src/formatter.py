import re


POST_LIMIT = 270


def clean(text):
    """
    Normalize whitespace without cutting the text.
    """
    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


def clean_sentence(text):
    """
    Clean a sentence and make sure it ends naturally.
    """
    text = clean(text)

    if not text:
        return ""

    if text.endswith(
        (".", "!", "?")
    ):
        return text

    return text + "."


def split_sentences(text):
    """
    Split text into readable complete sentences.

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
    """
    Decide the public news label.
    """

    score = item.get(
        "score",
        0
    )

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

    # Low-confidence information is never
    # presented as breaking.
    if confidence == "low":
        return "⚠️ UNCONFIRMED"

    # Existing event with new information.
    if status == "UPDATE":

        if score >= 80:
            return "🔴 UPDATE"

        return "📰 NEWS"

    # Breaking requires:
    # urgency + reliability + meaningful verification.
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
        item.get(
            "urgency_terms"
        )
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
    """
    Always make the source a complete sentence.
    """

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
    """
    Always make the headline a complete sentence.
    """

    title = clean(title)

    if title.endswith(
        (".", "!", "?")
    ):
        return (
            f"{label_text}: {title}"
        )

    return (
        f"{label_text}: {title}."
    )


def compact_headline(
    headline,
    source_sentence
):
    """
    Compact an unusually long headline using
    complete words only.

    Never cut a word in half.
    """

    available = (
        POST_LIMIT
        - len(source_sentence)
        - 1
    )

    if available <= 0:
        return ""

    words = headline.split()

    compact_words = []

    for word in words:

        candidate = " ".join(
            compact_words + [word]
        )

        if len(candidate) <= available:
            compact_words.append(
                word
            )
        else:
            break

    return " ".join(
        compact_words
    ).strip()


def build_single_post(
    item,
    breaking_min_score=75
):
    """
    Build one clean X post.

    Preferred format:

        1. News headline
        2. Useful context
        3. Source

    If a second useful context sentence also fits:

        1. News headline
        2. Context
        3. Additional context
        4. Source

    Target:
        3 to 4 complete sentences.

    The public post contains only:
        - label/headline
        - useful context
        - source

    Internal verification information is NOT published.
    """

    lab = label(
        item,
        breaking_min_score
    )

    title = clean(
        item.get(
            "title",
            ""
        )
    )

    summary = clean(
        item.get(
            "summary",
            ""
        )
    )

    source = clean(
        item.get(
            "source",
            "Unknown"
        )
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
    # Headline + 2 context sentences + source
    #
    # Four complete sentences.
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
    # Headline + 1 context sentence + source
    #
    # Three complete sentences.
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
    # This is NOT preferred.
    #
    # It is kept only as a safe fallback for the formatter.
    # choose_format() will normally select a thread when
    # a 3-sentence single post cannot fit.
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
    # Extremely long headline fallback.
    #
    # Preserve complete words.
    # Always keep the source.
    # ---------------------------------------------------------

    compact = compact_headline(
        headline,
        source_sentence
    )

    if compact:
        return (
            f"{compact} "
            f"{source_sentence}"
        )

    return source_sentence


def choose_format(item):
    """
    Choose single or thread based on whether a valid
    3-sentence single post can actually be produced.

    A proper single post requires:

        1. Headline
        2. At least one useful context sentence
        3. Source

    If that cannot fit within POST_LIMIT,
    use a thread.

    This prevents the formatter from silently producing
    a low-information two-sentence post.
    """

    title = clean(
        item.get(
            "title",
            ""
        )
    )

    summary = clean(
        item.get(
            "summary",
            ""
        )
    )

    if not title:
        return "single"

    breaking_min_score = item.get(
        "breaking_min_score",
        75
    )

    lab = label(
        item,
        breaking_min_score
    )

    headline = make_headline_sentence(
        lab,
        title
    )

    source_sentence = make_source_sentence(
        item.get(
            "source",
            "Unknown"
        )
    )

    context_sentences = choose_context_sentences(
        summary,
        2
    )

    # ---------------------------------------------------------
    # First choice:
    #
    # Try a proper 3-sentence single post.
    # ---------------------------------------------------------

    if context_sentences:

        candidate = " ".join([
            headline,
            context_sentences[0],
            source_sentence,
        ])

        if len(candidate) <= POST_LIMIT:
            return "single"

    # ---------------------------------------------------------
    # If useful context exists but the single post does
    # not fit, use a thread.
    # ---------------------------------------------------------

    if context_sentences:
        return "thread"

    # ---------------------------------------------------------
    # No usable context.
    #
    # Keep it single only if headline + source fit.
    # Otherwise use a thread so the thread builder can
    # safely handle the long headline.
    # ---------------------------------------------------------

    fallback = " ".join([
        headline,
        source_sentence,
    ])

    if len(fallback) <= POST_LIMIT:
        return "single"

    return "thread"


def build_thread(
    item,
    breaking_min_score=75
):
    """
    Build a small thread from complete sentences.

    Every post remains:
        - complete
        - readable
        - <= POST_LIMIT

    Verification metadata is NOT published.
    """

    lab = label(
        item,
        breaking_min_score
    )

    title = clean(
        item.get(
            "title",
            ""
        )
    )

    summary = clean(
        item.get(
            "summary",
            ""
        )
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

    # ---------------------------------------------------------
    # Guarantee that the first post is <= POST_LIMIT.
    # ---------------------------------------------------------

    if len(first) > POST_LIMIT:

        words = first.split()

        compact_words = []

        for word in words:

            candidate = " ".join(
                compact_words + [word]
            )

            if len(candidate) <= POST_LIMIT:
                compact_words.append(
                    word
                )
            else:
                break

        first = " ".join(
            compact_words
        ).strip()

    posts = []

    if first:
        posts.append(
            first
        )

    current = ""

    # ---------------------------------------------------------
    # Add complete context sentences.
    # ---------------------------------------------------------

    for sentence in context:

        sentence = clean_sentence(
            sentence
        )

        if not sentence:
            continue

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

    # ---------------------------------------------------------
    # Add source to final post when possible.
    # ---------------------------------------------------------

    source_sentence = make_source_sentence(
        source
    )

    if not posts:
        posts.append(
            source_sentence
        )

    elif (
        len(posts[-1])
        + len(source_sentence)
        + 1
        <= POST_LIMIT
    ):

        posts[-1] = (
            f"{posts[-1]} "
            f"{source_sentence}"
        )

    else:

        posts.append(
            source_sentence
        )

    # ---------------------------------------------------------
    # Final safety cleanup.
    # ---------------------------------------------------------

    cleaned_posts = []

    for post in posts:

        post = clean(post)

        if not post:
            continue

        # Every thread post must stay within
        # the hard limit.
        if len(post) > POST_LIMIT:

            words = post.split()

            compact_words = []

            for word in words:

                candidate = " ".join(
                    compact_words + [word]
                )

                if len(candidate) <= POST_LIMIT:
                    compact_words.append(
                        word
                    )
                else:
                    break

            post = " ".join(
                compact_words
            ).strip()

        if post:
            cleaned_posts.append(
                post
            )

    # Maximum thread length.
    return cleaned_posts[:7]


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
