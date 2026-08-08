import re
from collections import Counter
from src.source_reliability import reliability_bonus, get_tier

URGENT_TERMS = {
    "earthquake","tsunami","hurricane","cyclone","tornado","wildfire",
    "volcano","eruption","evacuation","missile","airstrike","invasion",
    "explosion","plane crash","train crash","bridge collapse","coup",
    "market crash","bank failure","default","state of emergency",
    "data breach","cyberattack","terror attack"
}

CATEGORY_TERMS = {
    "finance": {"bank","stocks","stock market","bond","inflation","interest rate","central bank",
                "economy","economic","tariff","trade","earnings","revenue","ipo","debt","default"},
    "politics": {"president","prime minister","government","election","parliament","senate",
                 "minister","vote","coalition","sanctions","diplomatic"},
    "disaster": {"earthquake","tsunami","hurricane","cyclone","tornado","flood","wildfire",
                 "volcano","eruption","landslide","evacuation","disaster"},
    "conflict": {"war","attack","airstrike","missile","invasion","ceasefire","coup","military"},
    "technology": {"technology","ai","artificial intelligence","chip","semiconductor","software",
                   "cybersecurity","cyberattack","data breach","robot"},
    "science": {"science","research","study","space","nasa","esa","astronomy"},
    "health": {"health","disease","virus","outbreak","hospital","who","vaccine","pandemic"},
    "industry": {"company","factory","manufacturing","oil","gas","energy","automotive","aviation",
                 "shipping","industry","production"},
}

def _words(text):
    return set(re.findall(r"[a-z0-9][a-z0-9'-]*", (text or "").lower()))

def _category(text, source_category):
    raw = (source_category or "").lower()
    if raw in CATEGORY_TERMS:
        return raw
    lower = (text or "").lower()
    scores = {cat: sum(1 for term in terms if term in lower) for cat, terms in CATEGORY_TERMS.items()}
    return max(scores, key=scores.get) if max(scores.values(), default=0) else (raw or "world")

def classify(title, summary, source_category, item=None):
    item = item or {}
    text = f"{title} {summary}".lower()
    category = _category(text, source_category)
    urgency_hits = [term for term in URGENT_TERMS if term in text]
    base = 35 + min(25, len(urgency_hits) * 8)
    base += reliability_bonus(item)
    if item.get("primary_source"):
        base += 10
    if len(summary or "") >= 180:
        base += 5
    score = max(0, min(100, base))
    confidence = "high" if item.get("primary_source") else ("medium" if get_tier(item) <= 2 else "low")
    return {
        "category": category,
        "score": score,
        "confidence": confidence,
        "urgency_terms": urgency_hits,
    }

def _tokens(text):
    return _words(text)

def _similarity(a, b):
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))

def verify(item, all_items):
    title = item.get("title","")
    summary = item.get("summary","")
    matches = []
    for other in all_items:
        if other.get("id") == item.get("id"):
            continue
        sim = _similarity(title, other.get("title",""))
        if sim >= 0.38:
            matches.append((sim, other))
    matches.sort(reverse=True, key=lambda x: x[0])
    corroborating = []
    strong = []
    seen_sources = set()
    for sim, other in matches:
        src = other.get("source")
        if not src or src in seen_sources:
            continue
        seen_sources.add(src)
        corroborating.append(other)
        if other.get("tier", 4) <= 2:
            strong.append(other)
    return {
        "corroborating_sources": len(corroborating),
        "strong_corroboration": len(strong),
        "corroborating_source_names": [x.get("source") for x in strong[:5]],
        "verified_match_count": len(matches),
    }
