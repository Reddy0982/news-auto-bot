from src.dashboard import build
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
(ROOT/"data/dashboard.html").write_text(build(),encoding="utf-8")
print(ROOT/"data/dashboard.html")
