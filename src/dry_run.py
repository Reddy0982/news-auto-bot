import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
queue=ROOT/"data/queue.json"

if not queue.exists():
    print("No queue file found.")
    raise SystemExit(0)

data=json.loads(queue.read_text())
print("="*72)
print("X PUBLISHER DRY RUN — NOTHING WILL BE POSTED")
print("="*72)

for i,item in enumerate(data.get("stories",[]),1):
    print(f"\n[{i}] {item.get('priority_level')} | {item.get('format')} | {item.get('title')}")
    if item.get("format")=="single":
        print(item.get("post",""))
    else:
        for n,p in enumerate(item.get("thread",[]),1):
            print(f"  {n}. {p}")
    print(f"Quality pass: {item.get('quality_pass')}")
    print(f"Source: {item.get('url')}")
