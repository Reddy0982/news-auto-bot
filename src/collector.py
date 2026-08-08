import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed

def clean(t):
    import re
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",t or "")).strip()

def fetch_one(feed, limit=25):
    try:
        parsed=feedparser.parse(feed["url"])
        rows=[]
        for e in parsed.entries[:limit]:
            title=clean(e.get("title",""))
            url=e.get("link","")
            summary=clean(e.get("summary","") or e.get("description",""))
            if title and url:
                rows.append({
                    "title":title,
                    "url":url,
                    "source":feed["name"],
                    "source_category":feed["category"],
                    "primary_source":feed.get("primary",False),
                    "tier":feed.get("tier",4),
                    "region":feed.get("region"),
                    "discovery":feed.get("discovery",False),
                    "summary":summary[:700]
                })
        return rows
    except Exception as exc:
        return [{"_source_error":feed["name"],"error":str(exc)}]

def collect(feeds, limit=25, workers=12):
    out=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs=[pool.submit(fetch_one,f,limit) for f in feeds]
        for job in as_completed(jobs):
            out.extend(job.result())
    return out
