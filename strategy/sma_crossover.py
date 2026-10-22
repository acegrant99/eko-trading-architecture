from data.models import MarketState, Signal, Side
from strategy.base import Strategy

class SMACrossover(Strategy):
    def generate_signal(self, market: MarketState, position=None) -> Signal:
        return Signal(side=Side.HOLD, reason="SMA placeholder")
