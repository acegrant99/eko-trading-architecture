"""Eko Controller — autonomous brain with paper + live modes.

Live features:
- Limit + market orders
- Position / balance sync from Coinbase
- Tighter live-only risk rules
- Cancel-all support
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from data.live_data import LiveDataProvider
from data.models import Signal, Side, OrderType
from strategy.sma_crossover import SMACrossover
from risk.risk_manager import RiskManager, RiskConfig
from execution.paper_executor import PaperExecutor
from execution.live_executor import LiveExecutor


class EkoController:
    def __init__(self):
        self.data = LiveDataProvider()
        self.strategy = SMACrossover(fast=5, slow=15)

        # Base (paper) risk config — still conservative
        risk_cfg = RiskConfig(
            max_position_pct=0.03,
            max_daily_loss_pct=0.02,
            min_confidence=0.58,
            max_open_positions=3,
            max_notional_usd=1000.0,
            require_limit_in_live=False,
        )
        self.risk = RiskManager(risk_cfg, equity=10_000.0)

        self.paper = PaperExecutor(starting_equity=10_000.0)
        self.live = LiveExecutor()

        self.mode = "paper"
        self.prefer_limit = True          # prefer limit orders when possible
        self.memory: List[str] = []
        self.last_market = None
        self.last_signal: Optional[Signal] = None
        self.last_action: Dict[str, Any] = {}

    @property
    def executor(self):
        return self.live if self.mode == "live" else self.paper

    def set_mode(self, mode: str) -> dict:
        mode = mode.lower().strip()
        if mode == "live":
            if not self.live.is_ready():
                return {
                    "ok": False,
                    "message": "Cannot enable LIVE mode: set COINBASE_API_KEY and COINBASE_API_SECRET first.",
                }
            # Sync real balances before enabling
            sync = self.live.sync_positions()
            if "error" in sync:
                return {"ok": False, "message": f"Failed to sync positions: {sync['error']}"}

            self.mode = "live"
            self.risk.set_live_mode(True)
            if self.live.equity_usd > 0:
                self.risk.update_equity(self.live.equity_usd)
            self.risk.sync_positions(self.live.positions)
            self.remember("Switched to LIVE trading mode")
            return {
                "ok": True,
                "message": "⚠️ LIVE MODE ENABLED. Real orders will be sent. Kill switch available. Positions synced.",
                "mode": "live",
                "sync": sync,
            }
        else:
            self.mode = "paper"
            self.risk.set_live_mode(False)
            self.risk.sync_positions(self.paper.positions)
            self.risk.update_equity(self.paper.equity)
            self.remember("Switched back to PAPER mode")
            return {"ok": True, "message": "Paper mode active. No real orders.", "mode": "paper"}

    def _build_signal(self, raw: Signal, market) -> Signal:
        """Optionally convert strategy signal into a limit order."""
        if not self.prefer_limit or raw.side == Side.HOLD:
            return raw

        last = market.last or 0
        if last <= 0:
            return raw

        # Slightly passive limit: buy below, sell above
        if raw.side == Side.BUY:
            limit_price = round(last * 0.9995, 2)
        else:
            limit_price = round(last * 1.0005, 2)

        return Signal(
            side=raw.side,
            size=raw.size,
            confidence=raw.confidence,
            reason=raw.reason + " [limit]",
            symbol=raw.symbol,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
        )

    async def tick(self, symbol: str = "BTC-USD") -> dict:
        market = await self.data.get_market_state(symbol)
        self.last_market = market

        raw_signal = self.strategy.generate_signal(market)
        signal = self._build_signal(raw_signal, market) if self.mode == "live" else raw_signal
        self.last_signal = signal

        allowed, reason = self.risk.check(signal, market)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode,
            "market": market.to_dict(),
            "signal": signal.to_dict(),
            "risk_allowed": allowed,
            "risk_reason": reason,
        }

        if allowed and signal.side != Side.HOLD:
            if self.mode == "live":
                # Extra hard size cap for autonomous live ticks
                signal.size = min(signal.size, 0.0015)

            exec_result = self.executor.execute(signal, market)
            result["execution"] = exec_result
            self.last_action = exec_result

            if self.mode == "paper":
                self.risk.open_positions = self.paper.positions
                self.risk.update_equity(self.paper.equity)
            else:
                self.risk.sync_positions(self.live.positions)
                if self.live.equity_usd > 0:
                    self.risk.update_equity(self.live.equity_usd)
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
        text = (text or "").strip().lower()

        if not text or text in ("status", "how are you", "eko status"):
            return await self._status()

        if text in ("live", "go live", "enable live", "mode live"):
            return self.set_mode("live")

        if text in ("paper", "go paper", "enable paper", "mode paper"):
            return self.set_mode("paper")

        if "kill switch" in text or text == "kill":
            off = "off" in text or "deactivate" in text or "disable" in text
            if off:
                self.risk.set_kill_switch(False)
                return {"ok": True, "message": "Kill switch DEACTIVATED. Trading resumed."}
            self.risk.set_kill_switch(True)
            return {"ok": True, "message": "Kill switch ACTIVATED. All trading halted."}

        if text in ("cancel all", "cancel orders", "flatten orders"):
            if self.mode != "live":
                return {"ok": False, "message": "Cancel only available in live mode."}
            result = self.live.cancel_all_orders()
            return {"ok": True, "message": "Cancel request sent", "result": result}

        if text in ("sync", "sync positions", "refresh positions"):
            if self.mode != "live":
                return {"ok": False, "message": "Sync only meaningful in live mode."}
            sync = self.live.sync_positions()
            self.risk.sync_positions(self.live.positions)
            if self.live.equity_usd > 0:
                self.risk.update_equity(self.live.equity_usd)
            return {"ok": True, "message": "Positions synced", "sync": sync}

        if text.startswith("force buy") or text.startswith("buy"):
            return await self._force_trade(Side.BUY, text)

        if text.startswith("force sell") or text.startswith("sell"):
            return await self._force_trade(Side.SELL, text)

        if text.startswith("limit buy"):
            return await self._force_trade(Side.BUY, text, force_limit=True)

        if text.startswith("limit sell"):
            return await self._force_trade(Side.SELL, text, force_limit=True)

        if text.startswith("remember "):
            note = text[9:].strip()
            self.remember(note)
            return {"ok": True, "message": f"Remembered: {note}"}

        if text in ("recall", "memory", "what do you remember"):
            return {"ok": True, "memory": self.recall() or ["(empty)"]}

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

        if text in ("accounts", "balances", "live balances"):
            if self.mode != "live":
                return {"ok": False, "message": "Switch to live mode first."}
            return {"ok": True, "accounts": self.live.get_accounts()}

        if text in ("prefer limit", "use limit"):
            self.prefer_limit = True
            return {"ok": True, "message": "Prefer LIMIT orders enabled"}

        if text in ("prefer market", "use market"):
            self.prefer_limit = False
            return {"ok": True, "message": "Prefer MARKET orders enabled"}

        return {
            "ok": False,
            "message": (
                "Commands: status · live · paper · kill switch · sync · cancel all · "
                "force buy/sell · limit buy/sell · accounts · remember · recall · "
                "prefer limit/market · search · market memory BTC"
            ),
        }

    async def _status(self) -> dict:
        if self.last_market:
            market = self.last_market.to_dict()
        else:
            m = await self.data.get_market_state("BTC-USD")
            market = m.to_dict()

        if self.mode == "live":
            portfolio = self.live.status()
        else:
            portfolio = self.paper.status()

        return {
            "ok": True,
            "message": f"Eko online — mode={self.mode.upper()}",
            "mode": self.mode,
            "live_ready": self.live.is_ready(),
            "prefer_limit": self.prefer_limit,
            "market": market,
            "signal": self.last_signal.to_dict() if self.last_signal else None,
            "risk": self.risk.status(),
            "portfolio": portfolio,
            "memory_count": len(self.memory),
            "last_action": self.last_action,
        }

    async def _force_trade(self, side: Side, text: str, force_limit: bool = False) -> dict:
        symbol = "BTC-USD"
        for token in text.upper().split():
            if "-" in token or token in ("BTC", "ETH", "SOL"):
                symbol = token if "-" in token else f"{token}-USD"
                break

        market = await self.data.get_market_state(symbol)
        size = 0.001 if self.mode == "live" else 0.005

        order_type = OrderType.LIMIT if (force_limit or (self.mode == "live" and self.prefer_limit)) else OrderType.MARKET
        limit_price = None
        if order_type == OrderType.LIMIT and market.last:
            limit_price = round(market.last * (0.999 if side == Side.BUY else 1.001), 2)

        signal = Signal(
            side=side,
            size=size,
            confidence=0.95,
            reason="Forced by user command",
            symbol=symbol,
            order_type=order_type,
            limit_price=limit_price,
        )

        allowed, reason = self.risk.check(signal, market)
        if not allowed:
            return {"ok": False, "message": f"Risk blocked: {reason}"}

        result = self.executor.execute(signal, market)

        if self.mode == "paper":
            self.risk.open_positions = self.paper.positions
            self.risk.update_equity(self.paper.equity)
        else:
            self.risk.sync_positions(self.live.positions)
            if self.live.equity_usd > 0:
                self.risk.update_equity(self.live.equity_usd)

        return {"ok": True, "mode": self.mode, "execution": result}

    async def close(self):
        await self.data.close()
