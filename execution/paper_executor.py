from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from data.models import Signal, MarketState, Position, Trade
from execution.trade_logger import append_trade_log


class PaperExecutor:
    """Simple paper trading engine with position tracking."""

    def __init__(self, starting_equity: float = 10_000.0):
        self.cash = starting_equity
        self.equity = starting_equity
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []

    def execute(self, signal: Signal, market: MarketState) -> dict:
        if signal.side.value == "HOLD" or signal.size <= 0:
            return {"status": "skipped", "reason": "HOLD or zero size"}

        price = market.last or 0.0
        if price <= 0:
            return {"status": "error", "reason": "Invalid market price"}

        symbol = signal.symbol
        side = signal.side.value
        size = signal.size

        trade_id = str(uuid.uuid4())[:8]
        ts = datetime.now(timezone.utc).isoformat()

        if side == "BUY":
            cost = size * price
            if cost > self.cash:
                size = self.cash / price * 0.99  # leave a tiny buffer
                cost = size * price
            if size <= 0:
                return {"status": "error", "reason": "Insufficient cash"}

            self.cash -= cost
            pos = self.positions.get(symbol)
            if pos and pos.size > 0:
                # average in
                total_size = pos.size + size
                pos.entry_price = (pos.entry_price * pos.size + price * size) / total_size
                pos.size = total_size
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side="LONG",
                    size=size,
                    entry_price=price,
                )

            trade = Trade(
                id=trade_id,
                symbol=symbol,
                side="BUY",
                size=size,
                price=price,
                timestamp=ts,
                reason=signal.reason,
            )

        elif side == "SELL":
            pos = self.positions.get(symbol)
            if not pos or pos.size <= 0:
                return {"status": "error", "reason": "No position to sell"}

            sell_size = min(size, pos.size)
            proceeds = sell_size * price
            pnl = (price - pos.entry_price) * sell_size
            self.cash += proceeds
            pos.size -= sell_size
            pos.realized_pnl += pnl

            if pos.size <= 1e-12:
                del self.positions[symbol]

            trade = Trade(
                id=trade_id,
                symbol=symbol,
                side="SELL",
                size=sell_size,
                price=price,
                timestamp=ts,
                reason=signal.reason,
                pnl=pnl,
            )
        else:
            return {"status": "skipped", "reason": "Unknown side"}

        self.trades.append(trade)
        append_trade_log(trade.to_dict())

        # Mark-to-market equity
        self._mark_to_market(market)

        return {
            "status": "filled",
            "trade": trade.to_dict(),
            "cash": round(self.cash, 2),
            "equity": round(self.equity, 2),
        }

    def _mark_to_market(self, market: MarketState):
        pos_value = 0.0
        for sym, pos in self.positions.items():
            px = market.last if sym == market.symbol else pos.entry_price
            pos.unrealized_pnl = (px - pos.entry_price) * pos.size
            pos_value += pos.size * px
        self.equity = self.cash + pos_value

    def status(self) -> dict:
        return {
            "cash": round(self.cash, 2),
            "equity": round(self.equity, 2),
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "trade_count": len(self.trades),
            "recent_trades": [t.to_dict() for t in self.trades[-5:]],
        }
