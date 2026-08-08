import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
q=ROOT/"data/queue.json"

if not q.exists():
    print("No queue has been generated yet.")
    raise SystemExit(0)

data=json.loads(q.read_text())
print("Generated:",data.get("generated_at"))
print("Stories ready:",data.get("count",0))
print("Held:",data.get("held_count",0))
for s in data.get("stories",[]):
    print(f"- {s.get('priority_level','NORMAL')} | {s.get('format')} | {s.get('title')}")
