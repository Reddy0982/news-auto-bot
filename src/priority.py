import re
from datetime import datetime, timezone

IMMEDIATE_TERMS = {
    "earthquake":35,"tsunami":40,"major earthquake":45,
    "hurricane":32,"cyclone":32,"tornado":30,"flood":25,"wildfire":25,
    "volcano":30,"eruption":30,"evacuation":25,
    "missile":35,"airstrike":35,"invasion":40,"attack":28,"explosion":30,
    "plane crash":45,"train crash":30,"bridge collapse":30,
    "war":35,"ceasefire":25,"coup":35,
    "market crash":40,"stock market crash":40,"bank failure":38,
    "bankruptcy":30,"default":30,"emergency rate":30,
    "interest rate":20,"central bank":18,
    "resignation":18,"election result":25,"state of emergency":30,
    "data breach":25,"cyberattack":30,"internet outage":20
}

WATCH_TERMS = {
    "warning":18,"alert":18,"developing":15,"breaking":20,"urgent":18,
    "deadline":12,"sanctions":15,"tariff":15,"recall":15,"outbreak":20
}

def priority(item):
    text=(item.get("title","")+" "+item.get("summary","")).lower()
    immediate=sum(v for k,v in IMMEDIATE_TERMS.items() if k in text)
    watch=sum(v for k,v in WATCH_TERMS.items() if k in text)

    score=item.get("score",0)+immediate+watch
    if item.get("primary_source"):
        score+=15
    if item.get("strong_corroboration",0)>=2:
        score+=15
    elif item.get("strong_corroboration",0)>=1:
        score+=8

    score=max(0,min(100,score))

    if immediate>=30 and (item.get("primary_source") or item.get("strong_corroboration",0)>=1):
        level="IMMEDIATE"
        max_delay=5
    elif score>=75:
        level="URGENT"
        max_delay=15
    elif score>=60:
        level="HIGH"
        max_delay=30
    else:
        level="NORMAL"
        max_delay=60

    return {
        "priority_score":score,
        "priority_level":level,
        "max_delay_minutes":max_delay
    }

def should_interrupt_queue(item):
    return item.get("priority_level")=="IMMEDIATE"
