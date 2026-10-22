from __future__ import annotations

from collections import deque
from typing import Optional

from data.models import MarketState, Signal, Side
from strategy.base import Strategy


class SMACrossover(Strategy):
    """Simple moving-average crossover with a short memory of prices."""

    def __init__(self, fast: int = 5, slow: int = 15):
        self.fast = fast
        self.slow = slow
        self.prices: deque[float] = deque(maxlen=slow + 5)

    def generate_signal(self, market: MarketState, position=None) -> Signal:
        if market.last is None or market.last <= 0:
            return Signal(side=Side.HOLD, reason="No price data", symbol=market.symbol)

        self.prices.append(market.last)

        if len(self.prices) < self.slow:
            return Signal(
                side=Side.HOLD,
                reason=f"Warming up ({len(self.prices)}/{self.slow})",
                symbol=market.symbol,
            )

        prices = list(self.prices)
        sma_fast = sum(prices[-self.fast :]) / self.fast
        sma_slow = sum(prices[-self.slow :]) / self.slow

        # Very simple logic
        if sma_fast > sma_slow * 1.001:
            return Signal(
                side=Side.BUY,
                size=0.01,  # small size for paper
                confidence=0.62,
                reason=f"SMA{self.fast} ({sma_fast:.2f}) > SMA{self.slow} ({sma_slow:.2f})",
                symbol=market.symbol,
            )
        elif sma_fast < sma_slow * 0.999:
            return Signal(
                side=Side.SELL,
                size=0.01,
                confidence=0.60,
                reason=f"SMA{self.fast} ({sma_fast:.2f}) < SMA{self.slow} ({sma_slow:.2f})",
                symbol=market.symbol,
            )

        return Signal(
            side=Side.HOLD,
            reason=f"No crossover (fast={sma_fast:.2f}, slow={sma_slow:.2f})",
            symbol=market.symbol,
        )
