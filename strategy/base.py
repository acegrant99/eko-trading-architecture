from abc import ABC, abstractmethod
from typing import Optional
from data.models import MarketState, Signal, Side

class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, market: MarketState, position=None) -> Signal:
        pass

    def name(self) -> str:
        return self.__class__.__name__
