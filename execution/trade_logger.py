import json
from pathlib import Path
from datetime import datetime
from typing import Any


def append_trade_log(entry: dict, path: str = "data/trade_log.jsonl"):
    """Append a trade record as a JSON line."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_trade_log(path: str = "data/trade_log.jsonl", limit: int = 50) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    trades = []
    for line in lines[-limit:]:
        try:
            trades.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return trades
