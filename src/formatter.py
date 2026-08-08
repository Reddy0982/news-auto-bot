import re

def clean(text,limit=230):
    text=re.sub(r"\s+"," ",text or "").strip()
    return text if len(text)<=limit else text[:limit].rsplit(" ",1)[0]+"…"

def fit(text,limit=280):
    text=re.sub(r"\s+"," ",text or "").strip()
    if len(text)<=limit:return text
    parts=re.split(r"(?<=[.!?])\s+",text)
    out=""
    for p in parts:
        candidate=(out+" "+p).strip()
        if len(candidate)>limit:break
        out=candidate
    return out or text[:limit-1].rstrip()+"…"

def label(item,breaking_min_score=75):
    if item.get("event_status")=="UPDATE": return "🔴 UPDATE"
    if item.get("confidence")=="high" and item.get("score",0)>=breaking_min_score: return "🚨 BREAKING"
    if item.get("confidence")=="low": return "⚠️ UNCONFIRMED"
    return "📰 DEVELOPING"

def choose_format(item):
    if item.get("event_status")=="UPDATE" and item.get("score",0)>=85 and len(item.get("summary",""))>350:return "thread"
    if item.get("score",0)>=92 and item.get("strong_corroboration",0)>=2 and len(item.get("summary",""))>380:return "thread"
    return "single"

def format_story(item,breaking_min_score=75):
    lab=label(item,breaking_min_score)
    s=clean(item.get("summary",""))
    if item.get("primary_source"):
        verification="An authoritative source is reporting this development."
    elif item.get("strong_corroboration",0)>=2:
        verification=f"Independent reporting from {item['strong_corroboration']} strong sources corroborates the development."
    elif item.get("corroborating_sources",0)>=1:
        verification="At least one independent source is also reporting the development."
    else:
        verification="The report is not yet independently corroborated."

    sentences=[
        f"{lab}: {item['title'].rstrip('.')}.",
        s if s.endswith((".","!","?")) else s+".",
        verification,
        f"Source: {item['source']} — {item['url']}"
    ]
    sentences=[x for x in sentences if x!="."]
    if choose_format(item)=="single":
        return {"format":"single","post":fit(" ".join(sentences))}
    return {"format":"thread","thread":[fit(x) for x in sentences[:5]]}
