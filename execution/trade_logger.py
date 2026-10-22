import json
from pathlib import Path
from datetime import datetime

def append_trade_log(entry: dict, path: str = "trade_log.jsonl"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
