import re


POST_LIMIT = 270


# =========================================================
# BASIC CLEANING
# =========================================================

def clean(text):
    """
    Normalize whitespace without cutting text.
    """
    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


def remove_rss_junk(text):
    """
    Remove common RSS/article-page fragments that should
    never appear in a public X post.
    """

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
        r"\bRead more\b",
        r"\bRead more:\b",
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
# SENTENCE HANDLING
# =========================================================

def clean_sentence(text):
    """
    Clean a sentence and make sure it ends naturally.
    """

    text = remove_rss_junk(text)

    if not text:
        return ""

    if text.endswith(
        (".", "!", "?")
    ):
        return text

    return text + "."


def split_sentences(text):
    """
    Split source text into complete readable sentences.

    We never intentionally create fragments.
    """

    text = remove_rss_junk(text)

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    result = []

    for part in parts:
        part = clean_sentence(part)

        if not part:
            continue

        result.append(part)

    return result


def usable_sentences(text):
    """
    Return only complete sentences that can fit into
    an X post.

    A sentence longer than POST_LIMIT is rejected rather
    than being cut.
    """

    sentences = split_sentences(
        text
    )

    return [
        sentence
        for sentence in sentences
        if len(sentence) <= POST_LIMIT
    ]


# =========================================================
# PUBLIC LABEL
# =========================================================

def label(
    item,
    breaking_min_score=75
):
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

    # Breaking requires urgency + reliability
    # + meaningful verification.
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
# CONTEXT SELECTION
# =========================================================

def choose_context_sentences(
    summary,
    max_sentences=2
):
    """
    Select useful complete sentences.

    Never cut a sentence.
    Never return a sentence over POST_LIMIT.
    """

    sentences = usable_sentences(
        summary
    )

    if not sentences:
        return []

    return sentences[
        :max_sentences
    ]


# =========================================================
# SOURCE
# =========================================================

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


# =========================================================
# HEADLINE
# =========================================================

def make_headline_sentence(
    label_text,
    title
):
    """
    Always make the headline a complete sentence.
    """

    title = clean(title)

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
# SAFE HEADLINE COMPACTION
# =========================================================

def compact_headline(
    headline,
    source_sentence
):
    """
    Compact an unusually long headline using complete
    words only.

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


# =========================================================
# SINGLE POST
# =========================================================

def build_single_post(
    item,
    breaking_min_score=75
):
    """
    Build one clean X post.

    Required public structure:

        Headline.
        Context.
        Source.

    Preferred:

        Headline.
        Context.
        Additional context.
        Source.

    IMPORTANT:

    If there is not enough useful source context to
    produce at least 3 complete sentences, return ""
    instead of creating a weak headline-only post.

    We NEVER invent missing information.
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

    context_sentences = choose_context_sentences(
        summary,
        2
    )

    # -----------------------------------------------------
    # BEST:
    #
    # Headline + 2 context sentences + source
    #
    # 4 complete sentences.
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # SAFE FALLBACK:
    #
    # Headline + 1 context sentence + source
    #
    # Exactly 3 complete sentences.
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # IMPORTANT CHANGE
    #
    # DO NOT return:
    #
    #     Headline + Source
    #
    # That creates only 2 sentences and will fail quality.
    #
    # Returning an empty post causes the quality gate to
    # hold the story safely.
    # -----------------------------------------------------

    return ""


# =========================================================
# THREAD DECISION
# =========================================================

def choose_format(item):
    """
    Decide whether the story should be a single post
    or a thread.

    Single post is the DEFAULT.

    A thread is reserved for genuinely substantial stories.

    Thread conditions:

    1. Existing important UPDATE:
       score >= 85 AND summary > 500 characters

    OR

    2. Very high-scoring NEW story:
       score >= 92 AND strong corroboration >= 2
       AND summary > 500 characters

    Everything else stays SINGLE.
    """

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

    summary_length = len(
        summary
    )

    # -----------------------------------------------------
    # Important update
    # -----------------------------------------------------

    if (
        status == "UPDATE"
        and score >= 85
        and summary_length > 500
    ):
        return "thread"

    # -----------------------------------------------------
    # Extremely important, strongly corroborated story
    # -----------------------------------------------------

    if (
        score >= 92
        and corroboration >= 2
        and summary_length > 500
    ):
        return "thread"

    # -----------------------------------------------------
    # DEFAULT
    # -----------------------------------------------------

    return "single"


# =========================================================
# THREAD SENTENCE PACKING
# =========================================================

def pack_sentences_into_posts(
    sentences
):
    """
    Pack complete sentences into posts.

    CRITICAL RULE:

    A sentence is NEVER cut.

    If a sentence itself exceeds POST_LIMIT,
    it is skipped rather than truncated.
    """

    posts = []

    current = ""

    for sentence in sentences:

        sentence = clean_sentence(
            sentence
        )

        if not sentence:
            continue

        # Never publish an oversized sentence.
        if len(sentence) > POST_LIMIT:
            continue

        if not current:

            current = sentence

            continue

        candidate = (
            f"{current} {sentence}"
        )

        if len(candidate) <= POST_LIMIT:

            current = candidate

        else:

            posts.append(
                current
            )

            current = sentence

    if current:
        posts.append(
            current
        )

    return posts


# =========================================================
# THREAD
# =========================================================

def build_thread(
    item,
    breaking_min_score=75
):
    """
    Build a small thread from complete sentences.

    Every post:

        - <= POST_LIMIT
        - complete
        - no RSS junk
        - never truncated

    The source is placed on the final post whenever
    possible.

    If there is insufficient useful context, return []
    so the quality gate can safely hold the story.
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
        return []

    # -----------------------------------------------------
    # Context
    # -----------------------------------------------------

    context = choose_context_sentences(
        summary,
        5
    )

    # A thread without useful context is not useful.
    if not context:
        return []

    # -----------------------------------------------------
    # First post: headline
    # -----------------------------------------------------

    first = make_headline_sentence(
        lab,
        title
    )

    if not first:
        return []

    # -----------------------------------------------------
    # If headline is too long, compact it using
    # complete words only.
    # -----------------------------------------------------

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

    if not first:
        return []

    posts = [
        first
    ]

    # -----------------------------------------------------
    # Context posts
    # -----------------------------------------------------

    context_posts = pack_sentences_into_posts(
        context
    )

    if not context_posts:
        return []

    posts.extend(
        context_posts
    )

    # -----------------------------------------------------
    # Source
    # -----------------------------------------------------

    source_sentence = make_source_sentence(
        source
    )

    # Add source to final post if possible.
    candidate = (
        f"{posts[-1]} "
        f"{source_sentence}"
    )

    if len(candidate) <= POST_LIMIT:

        posts[-1] = candidate

    else:

        if len(source_sentence) <= POST_LIMIT:

            posts.append(
                source_sentence
            )

        else:

            return []

    # -----------------------------------------------------
    # Final safety validation.
    #
    # NEVER truncate an oversized post.
    # -----------------------------------------------------

    final_posts = []

    for post in posts:

        post = clean(
            post
        )

        if not post:
            continue

        if len(post) > POST_LIMIT:
            continue

        final_posts.append(
            post
        )

    # A useful thread must contain at least:
    #
    # 1. headline
    # 2. context
    # 3. source
    #
    if len(final_posts) < 2:
        return []

    return final_posts[:7]


# =========================================================
# MAIN FORMATTER
# =========================================================

def format_story(
    item,
    breaking_min_score=75
):
    """
    Main formatter entry point.

    A story with insufficient content returns an empty
    post/thread. The quality gate then holds it rather than
    allowing a weak public post.
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
