"""Eko Controller — the autonomous brain that ties everything together.

Natural-language style commands + continuous risk-aware decision loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from data.live_data import LiveDataProvider
from data.models import Signal, Side
from strategy.sma_crossover import SMACrossover
from risk.risk_manager import RiskManager, RiskConfig
from execution.paper_executor import PaperExecutor


class EkoController:
    """Superior controller that analyzes the system and acts."""

    def __init__(self):
        self.data = LiveDataProvider()
        self.strategy = SMACrossover(fast=5, slow=15)
        self.risk = RiskManager(RiskConfig(), equity=10_000.0)
        self.executor = PaperExecutor(starting_equity=10_000.0)
        self.memory: List[str] = []
        self.last_market = None
        self.last_signal: Optional[Signal] = None
        self.last_action: Dict[str, Any] = {}
        self.running = False

    async def tick(self, symbol: str = "BTC-USD") -> dict:
        """One full cycle: data → strategy → risk → (maybe) execute."""
        market = await self.data.get_market_state(symbol)
        self.last_market = market

        signal = self.strategy.generate_signal(market)
        self.last_signal = signal

        allowed, reason = self.risk.check(signal, market)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market": market.to_dict(),
            "signal": signal.to_dict(),
            "risk_allowed": allowed,
            "risk_reason": reason,
        }

        if allowed and signal.side != Side.HOLD:
            exec_result = self.executor.execute(signal, market)
            result["execution"] = exec_result
            self.last_action = exec_result
            # keep risk manager in sync
            self.risk.open_positions = self.executor.positions
            self.risk.update_equity(self.executor.equity)
        else:
            result["execution"] = {"status": "skipped", "reason": reason}

        return result

    def remember(self, note: str):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        self.memory.append(f"[{ts}] {note}")
        if len(self.memory) > 100:
            self.memory = self.memory[-100:]

    def recall(self, limit: int = 10) -> List[str]:
        return self.memory[-limit:]

    async def handle_command(self, text: str) -> dict:
        """Simple natural-language command router."""
        text = (text or "").strip().lower()

        if not text or text in ("status", "how are you", "eko status"):
            return await self._status()

        if "kill switch" in text or text == "kill":
            on = "on" in text or "activate" in text or "enable" in text
            off = "off" in text or "deactivate" in text or "disable" in text
            if off:
                self.risk.set_kill_switch(False)
                return {"ok": True, "message": "Kill switch DEACTIVATED. Trading resumed."}
            else:
                self.risk.set_kill_switch(True)
                return {"ok": True, "message": "Kill switch ACTIVATED. All trading halted."}

        if text.startswith("force buy") or text.startswith("buy"):
            return await self._force_trade(Side.BUY, text)

        if text.startswith("force sell") or text.startswith("sell"):
            return await self._force_trade(Side.SELL, text)

        if text.startswith("remember "):
            note = text[9:].strip()
            self.remember(note)
            return {"ok": True, "message": f"Remembered: {note}"}

        if text in ("recall", "memory", "what do you remember"):
            notes = self.recall()
            return {"ok": True, "memory": notes or ["(empty)"]}

        if text.startswith("search "):
            query = text[7:].strip()
            results = await self.data.search_coingecko(query)
            return {"ok": True, "results": results}

        if text.startswith("market memory") or text.startswith("ticker"):
            parts = text.split()
            symbol = parts[-1].upper() if len(parts) > 1 else "BTC-USD"
            if "-" not in symbol:
                symbol = f"{symbol}-USD"
            market = await self.data.get_market_state(symbol)
            return {"ok": True, "market": market.to_dict()}

        return {
            "ok": False,
            "message": "Unknown command. Try: status · kill switch · force buy · remember ... · recall · search solana · market memory BTC",
        }

    async def _status(self) -> dict:
        market = None
        if self.last_market:
            market = self.last_market.to_dict()
        else:
            m = await self.data.get_market_state("BTC-USD")
            market = m.to_dict()

        return {
            "ok": True,
            "message": "Eko online",
            "market": market,
            "signal": self.last_signal.to_dict() if self.last_signal else None,
            "risk": self.risk.status(),
            "portfolio": self.executor.status(),
            "memory_count": len(self.memory),
            "last_action": self.last_action,
        }

    async def _force_trade(self, side: Side, text: str) -> dict:
        symbol = "BTC-USD"
        for token in text.upper().split():
            if "-" in token or token in ("BTC", "ETH", "SOL"):
                symbol = token if "-" in token else f"{token}-USD"
                break

        market = await self.data.get_market_state(symbol)
        signal = Signal(
            side=side,
            size=0.005,
            confidence=0.9,
            reason="Forced by user command",
            symbol=symbol,
        )
        allowed, reason = self.risk.check(signal, market)
        if not allowed:
            return {"ok": False, "message": f"Risk blocked: {reason}"}

        result = self.executor.execute(signal, market)
        self.risk.open_positions = self.executor.positions
        self.risk.update_equity(self.executor.equity)
        return {"ok": True, "execution": result}

    async def close(self):
        await self.data.close()
