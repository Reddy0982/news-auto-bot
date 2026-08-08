import re


POST_LIMIT = 270


# =========================================================
# BASIC CLEANING
# =========================================================

def clean(text):
    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


def remove_rss_junk(text):
    text = clean(text)

    if not text:
        return ""

    junk_patterns = [
        r"\bContinue reading\.\.\.",
        r"\bContinue reading\b",
        r"\bGet our breaking news email\b[^.]*\.?",
        r"\bfree app or daily news podcast\b",
        r"\bGet the Guardian's\b[^.]*\.?",
        r"\bSign up to our newsletter\b[^.]*\.?",
        r"\bSubscribe to our newsletter\b[^.]*\.?",
        r"\bRead more:\b",
        r"\bRead more\b",
        r"\bFollow us on\b[^.]*\.?",
        r"\bDownload our app\b[^.]*\.?",
        r"\bListen to our podcast\b[^.]*\.?",
    ]

    for pattern in junk_patterns:
        text = re.sub(
            pattern,
            " ",
            text,
            flags=re.IGNORECASE
        )

    return clean(text)


# =========================================================
# RSS SENTENCE NORMALIZATION
# =========================================================

def normalize_rss_boundaries(text):
    """
    Some RSS feeds concatenate complete sentences without
    punctuation.

    Example:

        "... taken over When Sir Demis Hassabis said..."

    We safely restore boundaries before a small set of
    common sentence-opening words.

    This does NOT invent information.
    It only restores punctuation between existing text.
    """

    text = clean(text)

    if not text:
        return ""

    boundary_words = [
        "When",
        "This",
        "That",
        "The",
        "He",
        "She",
        "It",
        "They",
        "Officials",
        "Authorities",
        "According",
        "Meanwhile",
        "However",
        "But",
        "And",
        "As",
        "After",
        "Before",
        "During",
        "With",
        "In",
        "On",
    ]

    words = "|".join(
        re.escape(word)
        for word in boundary_words
    )

    # Only insert a boundary when the preceding
    # character is a lowercase letter, digit, quote,
    # or closing punctuation.
    #
    # We deliberately do NOT split every lowercase ->
    # uppercase transition because that would break names
    # such as "Google DeepMind".
    pattern = (
        r'(?<=[a-z0-9"”’])'
        r'\s+'
        r'(?=('
        + words +
        r')\b)'
    )

    text = re.sub(
        pattern,
        ". ",
        text
    )

    return clean(text)


def clean_sentence(text):
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
    Convert source summary text into complete sentences.

    Handles both:
      1. normally punctuated RSS
      2. RSS summaries where sentence boundaries are
         accidentally concatenated.
    """

    text = remove_rss_junk(
        text
    )

    text = normalize_rss_boundaries(
        text
    )

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    result = []

    for part in parts:

        sentence = clean_sentence(
            part
        )

        if not sentence:
            continue

        # Do not accept RSS junk as context.
        if sentence.lower().startswith(
            "continue reading"
        ):
            continue

        result.append(
            sentence
        )

    return result


def usable_sentences(text):
    sentences = split_sentences(
        text
    )

    return [
        sentence
        for sentence in sentences
        if (
            sentence
            and len(sentence) <= POST_LIMIT
        )
    ]


# =========================================================
# LABEL
# =========================================================

def label(
    item,
    breaking_min_score=75
):
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

    if confidence == "low":
        return "⚠️ UNCONFIRMED"

    if status == "UPDATE":

        if score >= 80:
            return "🔴 UPDATE"

        return "📰 NEWS"

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


# =========================================================
# CONTEXT
# =========================================================

def choose_context_sentences(
    summary,
    max_sentences=2
):
    sentences = usable_sentences(
        summary
    )

    return sentences[
        :max_sentences
    ]


# =========================================================
# SOURCE
# =========================================================

def make_source_sentence(source):
    source = clean(
        source or "Unknown"
    )

    if source.endswith(
        (".", "!", "?")
    ):
        return f"Source: {source}"

    return f"Source: {source}."


# =========================================================
# HEADLINE
# =========================================================

def make_headline_sentence(
    label_text,
    title
):
    title = clean(
        title
    )

    if not title:
        return ""

    if title.endswith(
        (".", "!", "?")
    ):
        return (
            f"{label_text}: {title}"
        )

    return (
        f"{label_text}: {title}."
    )


# =========================================================
# SINGLE POST
# =========================================================

def build_single_post(
    item,
    breaking_min_score=75
):
    """
    Preferred:

        Headline.
        Context.
        Context.
        Source.

    Minimum:

        Headline.
        Context.
        Source.

    If sufficient context does not exist, return an empty
    post so the quality gate safely holds the story.
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

    summary = remove_rss_junk(
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

    context = choose_context_sentences(
        summary,
        2
    )

    # -----------------------------------------------------
    # 4 SENTENCES
    # -----------------------------------------------------

    if len(context) >= 2:

        candidate = " ".join([
            headline,
            context[0],
            context[1],
            source_sentence,
        ])

        if len(candidate) <= POST_LIMIT:
            return candidate

    # -----------------------------------------------------
    # 3 SENTENCES
    # -----------------------------------------------------

    if len(context) >= 1:

        candidate = " ".join([
            headline,
            context[0],
            source_sentence,
        ])

        if len(candidate) <= POST_LIMIT:
            return candidate

    # -----------------------------------------------------
    # SAFETY
    #
    # Never publish headline + source only.
    # -----------------------------------------------------

    return ""


# =========================================================
# FORMAT DECISION
# =========================================================

def choose_format(item):

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

    summary = remove_rss_junk(
        item.get(
            "summary",
            ""
        )
    )

    if (
        status == "UPDATE"
        and score >= 85
        and len(summary) > 500
    ):
        return "thread"

    if (
        score >= 92
        and corroboration >= 2
        and len(summary) > 500
    ):
        return "thread"

    return "single"


# =========================================================
# THREAD
# =========================================================

def build_thread(
    item,
    breaking_min_score=75
):
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

    summary = remove_rss_junk(
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
        return []

    context = choose_context_sentences(
        summary,
        5
    )

    if not context:
        return []

    first = make_headline_sentence(
        lab,
        title
    )

    if not first:
        return []

    if len(first) > POST_LIMIT:
        return []

    posts = [
        first
    ]

    current = ""

    for sentence in context:

        if len(sentence) > POST_LIMIT:
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

    source_sentence = make_source_sentence(
        source
    )

    if (
        len(posts[-1])
        + len(source_sentence)
        + 1
        <= POST_LIMIT
    ):
        posts[-1] = (
            f"{posts[-1]} "
            f"{source_sentence}"
        )

    elif len(source_sentence) <= POST_LIMIT:
        posts.append(
            source_sentence
        )

    else:
        return []

    # Final safety check.
    posts = [
        clean(post)
        for post in posts
        if (
            clean(post)
            and len(clean(post)) <= POST_LIMIT
        )
    ]

    if len(posts) < 2:
        return []

    return posts[:7]


# =========================================================
# MAIN ENTRY POINT
# =========================================================

def format_story(
    item,
    breaking_min_score=75
):
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
