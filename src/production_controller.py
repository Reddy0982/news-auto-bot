import json, os
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
HEALTH=ROOT/"data/health.json"
QUEUE=ROOT/"data/queue.json"
STATE=ROOT/"data/production_state.json"

def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default

def controller():
    health=load(HEALTH,{"status":"RED"})
    queue=load(QUEUE,{"stories":[],"count":0})
    state=load(STATE,{
        "live_enabled":False,
        "kill_switch":True,
        "daily_post_count":0,
        "last_reset_date":None
    })

    today=datetime.now(timezone.utc).date().isoformat()
    if state.get("last_reset_date")!=today:
        state["daily_post_count"]=0
        state["last_reset_date"]=today

    live_requested=os.getenv("X_PUBLISH_ENABLED","false").lower()=="true"
    kill_switch=os.getenv("X_KILL_SWITCH","true").lower()=="true"
    daily_limit=int(os.getenv("X_DAILY_POST_LIMIT","20"))

    reasons=[]
    if not live_requested: reasons.append("live publishing is disabled")
    if kill_switch: reasons.append("kill switch is active")
    if health.get("status")=="RED": reasons.append("health gate is RED")
    if daily_limit<=0: reasons.append("daily post limit is zero")
    if state.get("daily_post_count",0)>=daily_limit: reasons.append("daily post limit reached")

    allowed=not reasons
    result={
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "live_requested":live_requested,
        "kill_switch":kill_switch,
        "health":health.get("status"),
        "daily_limit":daily_limit,
        "daily_post_count":state.get("daily_post_count",0),
        "ready_count":queue.get("count",0),
        "allowed":allowed,
        "reasons":reasons
    }
    state["live_enabled"]=allowed
    state["kill_switch"]=kill_switch
    STATE.write_text(json.dumps(state,indent=2))
    print(json.dumps(result,indent=2))
    return result

if __name__=="__main__":
    controller()
