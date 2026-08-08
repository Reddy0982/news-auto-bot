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

    Never cut a sentence in half.
    """
    sentences = split_sentences(summary)

    if not sentences:
        return []

    return sentences[:max_sentences]


def make_source_sentence(source):
    """Always make the source a complete sentence."""
    source = clean(source or "Unknown")

    if source.endswith((".", "!", "?")):
        return f"Source: {source}"

    return f"Source: {source}."


def make_headline_sentence(label_text, title):
    """Always make the headline a complete sentence."""
    title = clean(title)

    if title.endswith((".", "!", "?")):
        return f"{label_text}: {title}"

    return f"{label_text}: {title}."


def build_single_post(item, breaking_min_score=75):
    """
    Build one clean X post.

    Target:
        3 to 4 complete sentences.

    Priority:
        1. Headline
        2. Useful source information
        3. Verification when available
        4. Source

    The formatter never cuts a sentence in half.
    """
    lab = label(item, breaking_min_score)

    title = clean(item.get("title", ""))
    summary = clean(item.get("summary", ""))
    source = clean(item.get("source", "Unknown"))

    if not title:
        return ""

    headline = make_headline_sentence(lab, title)
    source_sentence = make_source_sentence(source)
    verification = verification_sentence(item)

    context_sentences = choose_context_sentences(summary, 2)

    # ---------------------------------------------------------
    # Candidate 1:
    # Headline + 2 context sentences + verification + source
    # This gives up to 5 sentences, so only use it when the
    # verification sentence is absent.
    # ---------------------------------------------------------
    if len(context_sentences) >= 2 and not verification:
        candidate = [
            headline,
            context_sentences[0],
            context_sentences[1],
            source_sentence,
        ]

        post = " ".join(candidate)

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Candidate 2:
    # Headline + 2 context sentences + source
    # Exactly 4 sentences.
    # ---------------------------------------------------------
    if len(context_sentences) >= 2:
        candidate = [
            headline,
            context_sentences[0],
            context_sentences[1],
            source_sentence,
        ]

        post = " ".join(candidate)

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Candidate 3:
    # Headline + 1 context sentence + verification + source
    # Exactly 4 sentences when verification exists.
    # ---------------------------------------------------------
    if len(context_sentences) >= 1 and verification:
        candidate = [
            headline,
            context_sentences[0],
            verification,
            source_sentence,
        ]

        post = " ".join(candidate)

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Candidate 4:
    # Headline + 2 context sentences + source
    #
    # Re-check without verification.
    # This is the preferred 4-sentence structure for stories
    # where independent verification wording is unavailable.
    # ---------------------------------------------------------
    if len(context_sentences) >= 2:
        candidate = [
            headline,
            context_sentences[0],
            context_sentences[1],
            source_sentence,
        ]

        post = " ".join(candidate)

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Candidate 5:
    # Headline + 1 context sentence + source
    #
    # This is exactly 3 sentences and is the normal fallback.
    # ---------------------------------------------------------
    if len(context_sentences) >= 1:
        candidate = [
            headline,
            context_sentences[0],
            source_sentence,
        ]

        post = " ".join(candidate)

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Candidate 6:
    # Headline + verification + source
    #
    # This is also 3 sentences when verification exists.
    # ---------------------------------------------------------
    if verification:
        candidate = [
            headline,
            verification,
            source_sentence,
        ]

        post = " ".join(candidate)

        if len(post) <= POST_LIMIT:
            return post

    # ---------------------------------------------------------
    # Extremely long story/title.
    #
    # Preserve complete words and still create a valid
    # 3-sentence post where possible.
    # ---------------------------------------------------------
    available = (
        POST_LIMIT
        - len(headline)
        - len(source_sentence)
        - 2
    )

    if verification:
        available -= len(verification) + 1

    if available > 20 and context_sentences:
        words = context_sentences[0].split()
        shortened = []

        for word in words:
            candidate_text = " ".join(shortened + [word])

            if len(candidate_text) <= available:
                shortened.append(word)
            else:
                break

        if shortened:
            shortened_sentence = clean_sentence(
                " ".join(shortened)
            )

            candidate = [
                headline,
                shortened_sentence,
            ]

            if verification:
                candidate.append(verification)

            candidate.append(source_sentence)

            post = " ".join(candidate)

            if len(post) <= POST_LIMIT:
                return post

    # ---------------------------------------------------------
    # Final fallback.
    #
    # Keep the source and headline. This should only happen for
    # an unusually long headline with no usable summary.
    # ---------------------------------------------------------
    words = headline.split()

    compact_words = []

    for word in words:
        test = " ".join(compact_words + [word])

        if len(test) + 1 + len(source_sentence) <= POST_LIMIT:
            compact_words.append(word)
        else:
            break

    compact_headline = " ".join(compact_words)

    if compact_headline:
        return f"{compact_headline} {source_sentence}"

    return source_sentence


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

    first = make_headline_sentence(lab, title)

    posts = [first]

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
                posts.append(current)

            current = sentence

    if current:
        posts.append(current)

    verification = verification_sentence(item)

    if verification:
        if (
            len(posts[-1]) + len(verification) + 1
            <= POST_LIMIT
        ):
            posts[-1] = f"{posts[-1]} {verification}"
        else:
            posts.append(verification)

    source_line = make_source_sentence(source)

    if (
        len(posts[-1]) + len(source_line) + 1
        <= POST_LIMIT
    ):
        posts[-1] = f"{posts[-1]} {source_line}"
    else:
        posts.append(source_line)

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
                breaking_min_score,
            ),
        }

    return {
        "format": "single",
        "post": build_single_post(
            item,
            breaking_min_score,
        ),
    }
