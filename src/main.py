import json,re,sqlite3,hashlib
from datetime import datetime,timezone
from pathlib import Path
import feedparser
from src.intelligence import classify,verify
from src.event_memory import init_events,decide,mark_queued
from src.formatter import format_story
from src.language import check_item
from src.translator import translate_to_english,TranslationError
from src.source_reliability import is_discovery
from src.collector import collect
from src.quality import quality_check
from src.priority import priority

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/"config.json").read_text())
DB=ROOT/CONFIG["database"];QUEUE=ROOT/CONFIG["queue_file"]

def clean(t): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",t or "")).strip()
def sid(u,t): return hashlib.sha256((u.split("?")[0]+"|"+t.lower()).encode()).hexdigest()

def db():
    DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS stories(
      id TEXT PRIMARY KEY,title TEXT,url TEXT,source TEXT,category TEXT,summary TEXT,
      score INTEGER,confidence TEXT,event_id TEXT,event_status TEXT,first_seen TEXT
    )""")
    init_events(c);return c


def fetch():
    raw=collect(CONFIG["feeds"],CONFIG.get("max_feed_entries_per_source",25),12)
    out=[]
    for item in raw:
        if "_source_error" in item:
            continue
        t=item["title"];u=item["url"];s=item["summary"]
        out.append({
            "id":sid(u,t),"title":t,"url":u,"source":item["source"],
            "source_category":item["source_category"],
            "primary_source":item["primary_source"],
            "tier":item["tier"],"region":item["region"],
            "discovery":item["discovery"],"summary":s
        })
    return out

def translate_candidate(x):
    result=translate_to_english(x["title"]+"\n\n"+x["summary"])
    parts=result["text"].split("\n",1)
    x["title"]=clean(parts[0]);x["summary"]=clean(parts[1] if len(parts)>1 else "")
    x["translated_from"]=result.get("detected_language")
    x["translation_endpoint"]=result.get("endpoint")
    x["language_status"]="TRANSLATED_TO_ENGLISH"
    return x

def main():
    c=db();now=datetime.now(timezone.utc).isoformat();items=fetch();q=[];held=[]

    for x in items:
        if c.execute("SELECT 1 FROM stories WHERE id=?",(x["id"],)).fetchone():continue

        x["language_status"]=check_item(x)
        x.update(classify(x["title"],x["summary"],x["source_category"],x))
        x.update(verify(x,items))
        x.update(priority(x))

        if CONFIG.get("english_only",True) and x["language_status"]!="ENGLISH":
            if not CONFIG.get("translate_non_english",True) or x["score"]<CONFIG.get("translation_min_score",55):
                x["hold_reason"]="Translation required";held.append(x);continue
            try:x=translate_candidate(x)
            except TranslationError as exc:
                x["hold_reason"]="Translation unavailable";x["translation_error"]=str(exc);held.append(x);continue
            x.update(classify(x["title"],x["summary"],x["source_category"],x))
            x.update(priority(x))

        status,eid,_=decide(c,x,CONFIG["event_memory_hours"],CONFIG["major_event_memory_hours"])
        x["event_status"]=status;x["event_id"]=eid
        c.execute("INSERT INTO stories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (x["id"],x["title"],x["url"],x["source"],x["category"],x["summary"],x["score"],x["confidence"],eid,status,now))

        if status=="DUPLICATE":continue

        # Discovery feeds are leads, not proof. Require stronger evidence and a higher score.
        min_score=CONFIG["discovery_min_score"] if is_discovery(x) else CONFIG["min_score_to_queue"]
        if x["score"]<min_score:continue
        if is_discovery(x) and x.get("strong_corroboration",0)<1 and not x.get("primary_source"):
            x["hold_reason"]="Discovery lead awaiting independent confirmation"
            held.append(x);continue
        if x["confidence"]=="low" and x["tier"]>=3:continue

        x.update(format_story(x,CONFIG["breaking_min_score"]))
        x.update(quality_check(x))
        if not x["quality_pass"]:
            x["hold_reason"]="Quality check failed"; held.append(x); continue
        q.append(x);mark_queued(c,eid)

    c.commit();c.close()
    q.sort(key=lambda x:(x.get("priority_level")=="IMMEDIATE",x.get("priority_score",0),x["event_status"]=="UPDATE",x["confidence"]=="high"),reverse=True)
    q=q[:CONFIG["max_stories_per_run"]]

    QUEUE.parent.mkdir(parents=True,exist_ok=True)
    QUEUE.write_text(json.dumps({"generated_at":now,"count":len(q),"held_count":len(held),"stories":q,"held":held[:30]},indent=2,ensure_ascii=False))
    for x in q:print(f"[{x['priority_level']} | {x['event_status']} | {x['format']} | {x['region']} | {x['priority_score']}] {x['title']}")
    print("Held:",len(held))

if __name__=="__main__":main()
