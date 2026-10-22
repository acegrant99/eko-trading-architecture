from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional
from data.models import Signal, MarketState, Position


@dataclass
class RiskConfig:
    max_position_pct: float = 0.05
    kill_switch: bool = False
    max_daily_loss_pct: float = 0.02
    max_open_positions: int = 3
    min_confidence: float = 0.55
    # Live-only tighter defaults applied by controller
    max_notional_usd: float = 500.0      # hard USD cap per order
    require_limit_in_live: bool = False  # if True, reject market orders in live


class RiskManager:
    """Risk-first gate. Conscience layer enforces capital protection."""

    def __init__(self, config: Optional[RiskConfig] = None, equity: float = 10_000.0):
        self.config = config or RiskConfig()
        self.equity = equity
        self.daily_pnl = 0.0
        self.open_positions: dict[str, Position] = {}
        self.is_live_mode: bool = False

    def set_kill_switch(self, active: bool):
        self.config.kill_switch = active

    def set_live_mode(self, live: bool):
        self.is_live_mode = live
        if live:
            # Automatically tighten when entering live
            self.config.max_position_pct = min(self.config.max_position_pct, 0.015)
            self.config.max_daily_loss_pct = min(self.config.max_daily_loss_pct, 0.01)
            self.config.min_confidence = max(self.config.min_confidence, 0.65)
            self.config.max_open_positions = min(self.config.max_open_positions, 2)
            self.config.max_notional_usd = min(self.config.max_notional_usd, 250.0)

    def update_equity(self, equity: float):
        self.equity = max(equity, 1.0)

    def sync_positions(self, positions: dict[str, Position]):
        self.open_positions = positions or {}

    def check(self, signal: Signal, market: MarketState) -> Tuple[bool, str]:
        if self.config.kill_switch:
            return False, "Kill switch is ACTIVE — all trading halted"

        if signal.side.value == "HOLD":
            return True, "Hold — no risk"

        if signal.confidence < self.config.min_confidence:
            return False, f"Confidence {signal.confidence:.2f} below minimum {self.config.min_confidence}"

        # Daily loss limit
        if self.equity > 0 and self.daily_pnl < 0:
            if abs(self.daily_pnl) / self.equity >= self.config.max_daily_loss_pct:
                return False, f"Daily loss limit reached ({self.config.max_daily_loss_pct*100:.1f}%)"

        price = market.last or 0.0
        notional = signal.size * price

        # Hard USD notional cap (especially important in live)
        if notional > self.config.max_notional_usd:
            return False, f"Order notional ${notional:.2f} exceeds hard cap ${self.config.max_notional_usd:.2f}"

        # Position % of equity
        if notional > self.equity * self.config.max_position_pct:
            return False, f"Position size exceeds {self.config.max_position_pct*100:.1f}% of equity"

        # Max open positions
        if signal.side.value == "BUY" and len(self.open_positions) >= self.config.max_open_positions:
            if signal.symbol not in self.open_positions:
                return False, f"Max open positions ({self.config.max_open_positions}) reached"

        # Live-only: optionally require limit orders
        if self.is_live_mode and self.config.require_limit_in_live:
            if signal.order_type.value == "MARKET":
                return False, "Live mode requires LIMIT orders (require_limit_in_live=True)"

        # Live-only: reject absurdly wide limit prices
        if signal.order_type.value == "LIMIT" and signal.limit_price and price > 0:
            deviation = abs(signal.limit_price - price) / price
            if deviation > 0.05:  # >5% away from market
                return False, f"Limit price too far from market ({deviation*100:.1f}%)"

        return True, "Risk check passed"

    def status(self) -> dict:
        return {
            "kill_switch": self.config.kill_switch,
            "is_live_mode": self.is_live_mode,
            "equity": round(self.equity, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "open_positions": {k: v.to_dict() for k, v in self.open_positions.items()},
            "max_position_pct": self.config.max_position_pct,
            "max_daily_loss_pct": self.config.max_daily_loss_pct,
            "max_notional_usd": self.config.max_notional_usd,
            "min_confidence": self.config.min_confidence,
            "require_limit_in_live": self.config.require_limit_in_live,
        }
