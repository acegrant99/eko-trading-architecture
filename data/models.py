from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

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
    timestamp: datetime = field(default_factory=datetime.utcnow)
    extra: dict = field(default_factory=dict)

@dataclass
class Signal:
    side: Side = Side.HOLD
    size: float = 0.0
    confidence: float = 0.0
    reason: str = ""
