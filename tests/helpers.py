import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
MOCKS = ROOT / "mocks"
DATA = ROOT / "data"
CONTRACTS = ROOT / "contracts"


def load(path):
    text = Path(path).read_text(encoding="utf-8")
    if text.lstrip().startswith(("[", "{")) and not str(path).endswith(".jsonl"):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@lru_cache(maxsize=None)
def roster():
    from baja_insights.roster import Roster
    return Roster.load(MOCKS / "teams.json")


def validator(name):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return None
    return Draft202012Validator(load(CONTRACTS / f"{name}.schema.json"))
