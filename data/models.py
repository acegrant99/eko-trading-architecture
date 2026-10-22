from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class MarketState:
    symbol: str = "BTC-USD"
    last: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    spread_bps: float = 0.0
    timestamp: Optional[datetime] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.timestamp:
            d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class Signal:
    side: Side = Side.HOLD
    size: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    symbol: str = "BTC-USD"
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None  # required for LIMIT

    def to_dict(self) -> dict:
        return {
            "side": self.side.value,
            "size": self.size,
            "confidence": self.confidence,
            "reason": self.reason,
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
        }


@dataclass
class Position:
    symbol: str
    side: str                  # "LONG" or "FLAT"
    size: float = 0.0
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    currency: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Trade:
    id: str
    symbol: str
    side: str
    size: float
    price: float
    timestamp: str
    reason: str = ""
    pnl: float = 0.0
    order_type: str = "MARKET"
    live: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
