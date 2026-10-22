"""Eko Controller — driven by conscience + subconscious.

Autonomous loop trades according to how Eko feels and thinks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from data.live_data import LiveDataProvider
from data.models import Signal, Side, OrderType
from strategy.sma_crossover import SMACrossover
from risk.risk_manager import RiskManager, RiskConfig
from execution.paper_executor import PaperExecutor
from execution.live_executor import LiveExecutor
from conscience.brain import Conscience, Subconscious


class EkoController:
    def __init__(self):
        self.data = LiveDataProvider()
        self.strategy = SMACrossover(fast=5, slow=15)

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

        self.subconscious = Subconscious()
        self.conscience = Conscience(self.subconscious)

        self.mode = "paper"
        self.prefer_limit = True
        self.autonomous = False
        self._auto_task: Optional[asyncio.Task] = None
        self.auto_interval_sec = 20

        self.last_market = None
        self.last_signal: Optional[Signal] = None
        self.last_feeling = None
        self.last_action: Dict[str, Any] = {}
        self.decision_log: List[dict] = []

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
            sync = self.live.sync_positions()
            if "error" in sync:
                return {"ok": False, "message": f"Failed to sync positions: {sync['error']}"}

            self.mode = "live"
            self.risk.set_live_mode(True)
            if self.live.equity_usd > 0:
                self.risk.update_equity(self.live.equity_usd)
            self.risk.sync_positions(self.live.positions)
            self.subconscious.remember("Entered LIVE mode — conscience on high alert")
            return {
                "ok": True,
                "message": "⚠️ LIVE MODE ENABLED. Conscience is watching. Kill switch available.",
                "mode": "live",
                "sync": sync,
            }
        else:
            self.mode = "paper"
            self.risk.set_live_mode(False)
            self.risk.sync_positions(self.paper.positions)
            self.risk.update_equity(self.paper.equity)
            self.subconscious.remember("Returned to PAPER mode")
            return {"ok": True, "message": "Paper mode active. No real orders.", "mode": "paper"}

    def _build_signal(self, raw: Signal, market, feeling) -> Signal:
        """Scale size by conscience aggression and optionally use limits."""
        size = raw.size * max(0.05, feeling.aggression)

        if self.mode == "live":
            size = min(size, 0.0015 * feeling.aggression)

        order_type = OrderType.MARKET
        limit_price = None
        if self.prefer_limit and raw.side != Side.HOLD and market.last:
            order_type = OrderType.LIMIT
            limit_price = round(
                market.last * (0.9995 if raw.side == Side.BUY else 1.0005),
                2,
            )

        # Blend confidence with conscience trust
        confidence = raw.confidence * 0.6 + feeling.trust_signal * 0.4

        return Signal(
            side=raw.side,
            size=size,
            confidence=confidence,
            reason=f"{raw.reason} | mood={feeling.mood} agg={feeling.aggression:.2f}",
            symbol=raw.symbol,
            order_type=order_type,
            limit_price=limit_price,
        )

    async def think_and_act(self, symbol: str = "BTC-USD") -> dict:
        """Full cognitive cycle: sense → feel → strategize → risk → (maybe) act."""
        market = await self.data.get_market_state(symbol)
        self.last_market = market

        if market.last:
            self.subconscious.observe_price(symbol, market.last)

        # Strategy proposes
        raw_signal = self.strategy.generate_signal(market)

        # Conscience forms a feeling
        equity = self.paper.equity if self.mode == "paper" else (self.live.equity_usd or self.risk.equity)
        feeling = self.conscience.feel(
            symbol=symbol,
            signal_confidence=raw_signal.confidence,
            equity=equity,
            daily_pnl=self.risk.daily_pnl,
            kill_switch=self.risk.config.kill_switch,
        )
        self.last_feeling = feeling

        # Shape signal with feeling
        signal = self._build_signal(raw_signal, market, feeling)
        self.last_signal = signal

        # Risk gate
        allowed, risk_reason = self.risk.check(signal, market)

        # Conscience final approval
        conscience_ok, conscience_reason = self.conscience.approve(feeling)

        decision = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode,
            "market": market.to_dict(),
            "raw_signal": raw_signal.to_dict(),
            "signal": signal.to_dict(),
            "feeling": feeling.to_dict(),
            "risk_allowed": allowed,
            "risk_reason": risk_reason,
            "conscience_ok": conscience_ok,
            "conscience_reason": conscience_reason,
        }

        if allowed and conscience_ok and signal.side != Side.HOLD:
            exec_result = self.executor.execute(signal, market)
            decision["execution"] = exec_result
            self.last_action = exec_result

            # Feed outcome into subconscious when we have pnl info
            pnl = 0.0
            if isinstance(exec_result, dict):
                trade = exec_result.get("trade") or {}
                pnl = float(trade.get("pnl") or 0.0)
            self.subconscious.record_outcome(
                symbol=signal.symbol,
                side=signal.side.value,
                pnl=pnl,
                reason=signal.reason,
            )

            if self.mode == "paper":
                self.risk.open_positions = self.paper.positions
                self.risk.update_equity(self.paper.equity)
            else:
                self.risk.sync_positions(self.live.positions)
                if self.live.equity_usd > 0:
                    self.risk.update_equity(self.live.equity_usd)
        else:
            why = risk_reason if not allowed else conscience_reason
            decision["execution"] = {"status": "skipped", "reason": why}

        self.decision_log.append(decision)
        if len(self.decision_log) > 50:
            self.decision_log = self.decision_log[-50:]

        return decision

    # Backwards-compatible alias
    async def tick(self, symbol: str = "BTC-USD") -> dict:
        return await self.think_and_act(symbol)

    async def _auto_loop(self):
        while self.autonomous:
            try:
                await self.think_and_act("BTC-USD")
            except Exception as e:
                self.subconscious.remember(f"Auto-loop error: {e}")
            await asyncio.sleep(self.auto_interval_sec)

    def start_autonomous(self, interval_sec: int = 20) -> dict:
        if self.autonomous:
            return {"ok": True, "message": "Already running autonomously"}
        self.auto_interval_sec = max(8, interval_sec)
        self.autonomous = True
        try:
            loop = asyncio.get_running_loop()
            self._auto_task = loop.create_task(self._auto_loop())
        except RuntimeError:
            # No running loop yet — server will drive via periodic ticks
            pass
        self.subconscious.remember(f"Autonomous trading started (every {self.auto_interval_sec}s)")
        return {
            "ok": True,
            "message": f"Eko is now thinking and trading autonomously every {self.auto_interval_sec}s according to conscience.",
            "autonomous": True,
        }

    def stop_autonomous(self) -> dict:
        self.autonomous = False
        if self._auto_task and not self._auto_task.done():
            self._auto_task.cancel()
        self._auto_task = None
        self.subconscious.remember("Autonomous trading stopped")
        return {"ok": True, "message": "Autonomous trading stopped. Eko is idle.", "autonomous": False}

    def remember(self, note: str):
        self.subconscious.remember(note)

    def recall(self, limit: int = 10) -> List[str]:
        return self.subconscious.notes[-limit:]

    async def handle_command(self, text: str) -> dict:
        text = (text or "").strip().lower()

        if not text or text in ("status", "how are you", "eko status", "how do you feel"):
            return await self._status()

        if text in ("think", "feel", "what do you think"):
            d = await self.think_and_act("BTC-USD")
            return {
                "ok": True,
                "message": f"Mood: {d['feeling']['mood']} · aggression={d['feeling']['aggression']}",
                **{k: d[k] for k in ("feeling", "signal", "conscience_ok", "conscience_reason", "execution", "mode")},
            }

        if text in ("auto", "start auto", "autonomous", "run", "go"):
            return self.start_autonomous()

        if text in ("stop", "stop auto", "halt auto", "pause"):
            return self.stop_autonomous()

        if text in ("live", "go live", "enable live", "mode live"):
            return self.set_mode("live")

        if text in ("paper", "go paper", "enable paper", "mode paper"):
            return self.set_mode("paper")

        if "kill switch" in text or text == "kill":
            off = "off" in text or "deactivate" in text or "disable" in text
            if off:
                self.risk.set_kill_switch(False)
                self.subconscious.remember("Kill switch deactivated")
                return {"ok": True, "message": "Kill switch DEACTIVATED."}
            self.risk.set_kill_switch(True)
            self.subconscious.remember("Kill switch activated by user")
            return {"ok": True, "message": "Kill switch ACTIVATED. All trading halted."}

        if text in ("cancel all", "cancel orders"):
            if self.mode != "live":
                return {"ok": False, "message": "Cancel only in live mode."}
            result = self.live.cancel_all_orders()
            return {"ok": True, "message": "Cancel request sent", "result": result}

        if text in ("sync", "sync positions"):
            if self.mode != "live":
                return {"ok": False, "message": "Sync only in live mode."}
            sync = self.live.sync_positions()
            self.risk.sync_positions(self.live.positions)
            if self.live.equity_usd > 0:
                self.risk.update_equity(self.live.equity_usd)
            return {"ok": True, "message": "Positions synced", "sync": sync}

        if text.startswith("force buy") or text.startswith("buy "):
            return await self._force_trade(Side.BUY, text)

        if text.startswith("force sell") or text.startswith("sell "):
            return await self._force_trade(Side.SELL, text)

        if text.startswith("limit buy"):
            return await self._force_trade(Side.BUY, text, force_limit=True)

        if text.startswith("limit sell"):
            return await self._force_trade(Side.SELL, text, force_limit=True)

        if text.startswith("remember "):
            note = text[9:].strip()
            self.remember(note)
            return {"ok": True, "message": f"Remembered: {note}"}

        if text in ("recall", "memory"):
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

        if text in ("accounts", "balances"):
            if self.mode != "live":
                return {"ok": False, "message": "Switch to live mode first."}
            return {"ok": True, "accounts": self.live.get_accounts()}

        if text in ("prefer limit", "use limit"):
            self.prefer_limit = True
            return {"ok": True, "message": "Prefer LIMIT orders"}

        if text in ("prefer market", "use market"):
            self.prefer_limit = False
            return {"ok": True, "message": "Prefer MARKET orders"}

        if text in ("conscience", "principles"):
            return {"ok": True, "conscience": self.conscience.status()}

        return {
            "ok": False,
            "message": (
                "Commands: status · think · auto · stop · live · paper · kill switch · "
                "sync · cancel all · force/limit buy|sell · remember · recall · conscience · accounts"
            ),
        }

    async def _status(self) -> dict:
        if self.last_market:
            market = self.last_market.to_dict()
        else:
            m = await self.data.get_market_state("BTC-USD")
            market = m.to_dict()

        portfolio = self.paper.status() if self.mode == "paper" else self.live.status()
        feeling = self.last_feeling.to_dict() if self.last_feeling else None

        return {
            "ok": True,
            "message": f"Eko online — mode={self.mode.upper()} · auto={self.autonomous}",
            "mode": self.mode,
            "autonomous": self.autonomous,
            "live_ready": self.live.is_ready(),
            "prefer_limit": self.prefer_limit,
            "feeling": feeling,
            "conscience": self.conscience.status(market.get("symbol", "BTC-USD")),
            "market": market,
            "signal": self.last_signal.to_dict() if self.last_signal else None,
            "risk": self.risk.status(),
            "portfolio": portfolio,
            "memory_count": len(self.subconscious.notes),
            "last_action": self.last_action,
        }

    async def _force_trade(self, side: Side, text: str, force_limit: bool = False) -> dict:
        symbol = "BTC-USD"
        for token in text.upper().split():
            if "-" in token or token in ("BTC", "ETH", "SOL"):
                symbol = token if "-" in token else f"{token}-USD"
                break

        market = await self.data.get_market_state(symbol)
        if market.last:
            self.subconscious.observe_price(symbol, market.last)

        size = 0.001 if self.mode == "live" else 0.005
        order_type = OrderType.LIMIT if (force_limit or (self.mode == "live" and self.prefer_limit)) else OrderType.MARKET
        limit_price = None
        if order_type == OrderType.LIMIT and market.last:
            limit_price = round(market.last * (0.999 if side == Side.BUY else 1.001), 2)

        signal = Signal(
            side=side,
            size=size,
            confidence=0.95,
            reason="Forced by user",
            symbol=symbol,
            order_type=order_type,
            limit_price=limit_price,
        )

        allowed, reason = self.risk.check(signal, market)
        if not allowed:
            return {"ok": False, "message": f"Risk blocked: {reason}"}

        # Even forced trades pass through a soft conscience check
        feeling = self.conscience.feel(
            symbol=symbol,
            signal_confidence=0.95,
            equity=self.risk.equity,
            daily_pnl=self.risk.daily_pnl,
            kill_switch=self.risk.config.kill_switch,
        )
        if feeling.mood == "fearful" and feeling.aggression < 0.15:
            return {"ok": False, "message": f"Conscience strongly opposed (mood={feeling.mood})"}

        result = self.executor.execute(signal, market)

        if self.mode == "paper":
            self.risk.open_positions = self.paper.positions
            self.risk.update_equity(self.paper.equity)
        else:
            self.risk.sync_positions(self.live.positions)
            if self.live.equity_usd > 0:
                self.risk.update_equity(self.live.equity_usd)

        return {"ok": True, "mode": self.mode, "feeling": feeling.to_dict(), "execution": result}

    async def close(self):
        self.stop_autonomous()
        await self.data.close()
