import re

def clean(text, limit=180):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"

def fit_sentences(sentences, limit=280):
    """Keep a compact 4-sentence post when possible, always staying <= 280 chars."""
    sentences = [re.sub(r"\s+", " ", s or "").strip() for s in sentences if (s or "").strip()]
    if not sentences:
        return ""
    # Reserve space for all four sentences. Shorten the summary first.
    if len(sentences) >= 4:
        prefix = " ".join(sentences[:1])
        tail = " ".join(sentences[2:4])
        available = limit - len(prefix) - len(tail) - 2
        if available > 30:
            sentences[1] = clean(sentences[1], available)
    text = " ".join(sentences[:4])
    if len(text) <= limit:
        return text
    # Last-resort compacting: preserve title, verification and source.
    if len(sentences) >= 4:
        available = limit - len(sentences[0]) - len(sentences[2]) - len(sentences[3]) - 3
        sentences[1] = clean(sentences[1], max(20, available))
        text = " ".join(sentences[:4])
    return text if len(text) <= limit else text[:limit-1].rstrip() + "…"

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

    # Important but not breaking.
    if score >= 55:
        return "📰 NEWS"

    return "📰 DEVELOPING"

def choose_format(item):
    if item.get("event_status") == "UPDATE" and item.get("score", 0) >= 85 and len(item.get("summary", "")) > 350:
        return "thread"
    if item.get("score", 0) >= 92 and item.get("strong_corroboration", 0) >= 2 and len(item.get("summary", "")) > 380:
        return "thread"
    return "single"

def format_story(item, breaking_min_score=75):
    lab = label(item, breaking_min_score)
    summary = clean(item.get("summary", ""), 150)

    if item.get("primary_source"):
        verification = "An authoritative source is reporting this."
    elif item.get("strong_corroboration", 0) >= 2:
        verification = f"{item['strong_corroboration']} independent strong sources corroborate it."
    elif item.get("corroborating_sources", 0) >= 1:
        verification = "At least one independent source is also reporting it."
    else:
        verification = "Independent confirmation is not yet available."

    source = f"Source: {item.get('source', 'Unknown')} — {item.get('url', '')}"
    sentences = [
        f"{lab}: {item['title'].rstrip('.')}.",
        summary if summary.endswith((".", "!", "?")) else summary + ".",
        verification,
        source,
    ]

    if choose_format(item) == "single":
        return {"format": "single", "post": fit_sentences(sentences)}

    return {"format": "thread", "thread":[s[:280].rstrip() for s in sentences[:5]]}
