from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Optional
from data.models import Signal, MarketState, Position


@dataclass
class RiskConfig:
    max_position_pct: float = 0.05          # max 5% of equity per trade
    kill_switch: bool = False
    max_daily_loss_pct: float = 0.02        # 2% daily loss limit
    max_open_positions: int = 3
    min_confidence: float = 0.55


class RiskManager:
    """Risk-first gate. Conscience layer enforces capital protection."""

    def __init__(self, config: Optional[RiskConfig] = None, equity: float = 10_000.0):
        self.config = config or RiskConfig()
        self.equity = equity
        self.daily_pnl = 0.0
        self.open_positions: dict[str, Position] = {}

    def set_kill_switch(self, active: bool):
        self.config.kill_switch = active

    def update_equity(self, equity: float):
        self.equity = equity

    def check(self, signal: Signal, market: MarketState) -> Tuple[bool, str]:
        """Return (allowed, reason)."""
        if self.config.kill_switch:
            return False, "Kill switch is ACTIVE — all trading halted"

        if signal.side.value == "HOLD":
            return True, "Hold — no risk"

        if signal.confidence < self.config.min_confidence:
            return False, f"Confidence {signal.confidence:.2f} below minimum {self.config.min_confidence}"

        # Daily loss limit
        if self.daily_pnl < 0 and abs(self.daily_pnl) / self.equity >= self.config.max_daily_loss_pct:
            return False, f"Daily loss limit reached ({self.config.max_daily_loss_pct*100:.1f}%)"

        # Position size check
        notional = signal.size * (market.last or 0)
        if notional > self.equity * self.config.max_position_pct:
            return False, f"Position size exceeds {self.config.max_position_pct*100:.1f}% of equity"

        # Max open positions
        if signal.side.value == "BUY" and len(self.open_positions) >= self.config.max_open_positions:
            if signal.symbol not in self.open_positions:
                return False, f"Max open positions ({self.config.max_open_positions}) reached"

        return True, "Risk check passed"

    def status(self) -> dict:
        return {
            "kill_switch": self.config.kill_switch,
            "equity": self.equity,
            "daily_pnl": self.daily_pnl,
            "open_positions": {k: v.to_dict() for k, v in self.open_positions.items()},
            "max_position_pct": self.config.max_position_pct,
            "max_daily_loss_pct": self.config.max_daily_loss_pct,
        }
