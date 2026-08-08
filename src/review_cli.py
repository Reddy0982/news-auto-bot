import sys
from src.review import set_review

if len(sys.argv)<3:
    print("Usage: python -m src.review_cli STORY_ID APPROVE|REJECT|HOLD [note]")
    raise SystemExit(1)

story_id=sys.argv[1]
decision=sys.argv[2].upper()
note=" ".join(sys.argv[3:]) if len(sys.argv)>3 else ""
set_review(story_id,decision,note)
print(f"{story_id}: {decision}")
