import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/"data/queue.json"
M=ROOT/"data/metrics.json"
H=ROOT/"data/source_health.json"
OUT=ROOT/"data/health.json"

def main():
    reasons=[]; warnings=[]
    metrics=json.loads(M.read_text()) if M.exists() else {}
    queue=json.loads(Q.read_text()) if Q.exists() else {}
    source=json.loads(H.read_text()) if H.exists() else {"sources":[]}

    sources=source.get("sources",[])
    if not sources:
        reasons.append("no source-health results")

    dead=sum(1 for s in sources if s.get("entries",0)==0 and s.get("status") not in (200,304))
    if sources and dead/max(1,len(sources))>0.60:
        reasons.append("more than 60% of sources returned no usable entries")
    elif sources and dead/max(1,len(sources))>0.30:
        warnings.append("more than 30% of sources returned no usable entries")

    ready=int(queue.get("count",0))
    held=int(queue.get("held_count",0))
    quality_fail=int(metrics.get("quality_failures",0))
    translation_hold=int(metrics.get("translation_held",0))
    seen=int(metrics.get("stories_seen",0))

    if quality_fail>0:
        reasons.append("quality failures detected")
    if seen>=20 and held/seen>0.90:
        warnings.append("very high hold rate")
    if seen>=20 and ready/seen>0.50:
        reasons.append("unusually high publishable-story rate")
    if translation_hold>50:
        warnings.append("large translation backlog")

    status="RED" if reasons else ("YELLOW" if warnings else "GREEN")
    result={
        "status":status,
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "reasons":reasons,
        "warnings":warnings,
        "ready":ready,
        "held":held,
        "stories_seen":seen
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if status=="RED":
        raise SystemExit(2)

if __name__=="__main__":
    main()
