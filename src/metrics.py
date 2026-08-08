import json, sqlite3
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data/news.db"
QUEUE=ROOT/"data/queue.json"
OUT=ROOT/"data/metrics.json"

def main():
    metrics={
        "stories_seen":0,"new_events":0,"updates":0,"duplicates":0,
        "held":0,"ready":0,"quality_failures":0,"translation_held":0,
        "priority":Counter(),"confidence":Counter(),"categories":Counter(),
        "sources":Counter(),"source_errors":0
    }

    if DB.exists():
        con=sqlite3.connect(DB)
        rows=con.execute("SELECT category,event_status,confidence,source FROM stories").fetchall()
        metrics["stories_seen"]=len(rows)
        for category,status,confidence,source in rows:
            metrics["categories"][category]+=1
            metrics["sources"][source]+=1
            if status=="NEW":metrics["new_events"]+=1
            elif status=="UPDATE":metrics["updates"]+=1
            elif status=="DUPLICATE":metrics["duplicates"]+=1
            metrics["confidence"][confidence]+=1
        con.close()

    if QUEUE.exists():
        q=json.loads(QUEUE.read_text())
        metrics["ready"]=q.get("count",0)
        metrics["held"]=q.get("held_count",0)
        for s in q.get("stories",[]):
            metrics["priority"][s.get("priority_level","UNKNOWN")]+=1
        for s in q.get("held",[]):
            reason=s.get("hold_reason","")
            if "translation" in reason.lower():metrics["translation_held"]+=1
            if "quality" in reason.lower():metrics["quality_failures"]+=1

    metrics={k:(dict(v) if isinstance(v,Counter) else v) for k,v in metrics.items()}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(metrics,indent=2,ensure_ascii=False))
    print(json.dumps(metrics,indent=2,ensure_ascii=False))

if __name__=="__main__":main()
