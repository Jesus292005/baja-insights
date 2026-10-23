import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]
ROOT = AGENTS.parent
for path in (AGENTS, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
