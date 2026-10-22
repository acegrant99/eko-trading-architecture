from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class MarketState:
    symbol: str = "BTC-USD"
    last: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    spread_bps: float = 0.0
    timestamp: datetime = None
    extra: Dict[str, Any] = None

@dataclass
class Signal:
    side: Side = Side.HOLD
    size: float = 0.0
    confidence: float = 0.0
    reason: str = ""
