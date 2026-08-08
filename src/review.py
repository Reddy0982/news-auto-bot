import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"data/queue.json"
REVIEWS=ROOT/"data/reviews.json"

def load():
    return json.loads(REVIEWS.read_text()) if REVIEWS.exists() else {"reviews":{}}

def save(data):
    REVIEWS.write_text(json.dumps(data,indent=2,ensure_ascii=False))

def set_review(story_id, decision, note=""):
    if decision not in {"APPROVE","REJECT","HOLD"}:
        raise ValueError("decision must be APPROVE, REJECT, or HOLD")
    data=load()
    data["reviews"][story_id]={
        "decision":decision,
        "note":note,
        "reviewed_at":datetime.now(timezone.utc).isoformat()
    }
    save(data)

def main():
    data=json.loads(QUEUE.read_text()) if QUEUE.exists() else {"stories":[]}
    reviews=load()["reviews"]
    print("HUMAN REVIEW MODE")
    for i,item in enumerate(data.get("stories",[]),1):
        sid=item.get("id")
        review=reviews.get(sid,{"decision":"PENDING"})
        print(f"[{i}] {sid} | {review['decision']} | {item.get('title')}")

if __name__=="__main__":
    main()
