"""Eko Conscience Brain + Subconscious.

The conscience enforces capital-protection principles and forms a high-level
"feeling" about the market and the system's health.

The subconscious accumulates volatility, regime, and outcome memory that
bias future decisions. Seed notes from data/memory_seed.json load on startup.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional, Any
import statistics


SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "memory_seed.json"


@dataclass
class Feeling:
    """How Eko currently feels about trading."""
    mood: str = "neutral"          # calm | cautious | confident | fearful | greedy
    aggression: float = 0.5        # 0.0 = freeze, 1.0 = max allowed size
    trust_signal: float = 0.5      # how much to trust the strategy signal
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mood": self.mood,
            "aggression": round(self.aggression, 3),
            "trust_signal": round(self.trust_signal, 3),
            "notes": self.notes[-5:],
        }


class Subconscious:
    """Accumulates volatility, regime, and per-market outcome memory."""

    def __init__(self, max_prices: int = 120, max_outcomes: int = 50, load_seed: bool = True):
        self.prices: Dict[str, Deque[float]] = {}
        self.outcomes: Deque[dict] = deque(maxlen=max_outcomes)
        self.notes: List[str] = []
        self.max_prices = max_prices
        if load_seed:
            self._load_seed()

    def _load_seed(self):
        try:
            if SEED_PATH.exists():
                raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    for note in raw:
                        if isinstance(note, str) and note.strip():
                            self.notes.append(note.strip())
        except Exception:
            pass

    def observe_price(self, symbol: str, price: float):
        if symbol not in self.prices:
            self.prices[symbol] = deque(maxlen=self.max_prices)
        if price and price > 0:
            self.prices[symbol].append(price)

    def record_outcome(self, symbol: str, side: str, pnl: float, reason: str = ""):
        self.outcomes.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "pnl": pnl,
            "reason": reason,
        })

    def remember(self, note: str):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        self.notes.append(f"[{ts}] {note}")
        if len(self.notes) > 200:
            self.notes = self.notes[-200:]

    def volatility(self, symbol: str) -> Optional[float]:
        series = self.prices.get(symbol)
        if not series or len(series) < 8:
            return None
        rets = []
        prev = None
        for p in series:
            if prev and prev > 0:
                rets.append((p - prev) / prev)
            prev = p
        if len(rets) < 5:
            return None
        return statistics.pstdev(rets)

    def recent_pnl(self, n: int = 10) -> float:
        return sum(o.get("pnl", 0.0) for o in list(self.outcomes)[-n:])

    def win_rate(self, n: int = 20) -> Optional[float]:
        recent = list(self.outcomes)[-n:]
        if not recent:
            return None
        wins = sum(1 for o in recent if o.get("pnl", 0) > 0)
        return wins / len(recent)

    def regime(self, symbol: str) -> str:
        series = list(self.prices.get(symbol) or [])
        if len(series) < 15:
            return "unknown"
        short = sum(series[-5:]) / 5
        longer = sum(series[-15:]) / 15
        if short > longer * 1.003:
            return "uptrend"
        if short < longer * 0.997:
            return "downtrend"
        return "range"

    def snapshot(self, symbol: str = "BTC-USD") -> dict:
        return {
            "volatility": self.volatility(symbol),
            "regime": self.regime(symbol),
            "recent_pnl": self.recent_pnl(),
            "win_rate": self.win_rate(),
            "notes": self.notes[-12:],
            "outcome_count": len(self.outcomes),
        }


class Conscience:
    """Capital-protection principles + high-level feeling formation."""

    PRINCIPLES = [
        "Never risk ruin for a single idea",
        "Reduce size when uncertain or losing",
        "Respect the kill switch above all",
        "Prefer survival over opportunity",
        "Let memory of pain slow the next decision",
    ]

    def __init__(self, subconscious: Optional[Subconscious] = None):
        self.sub = subconscious or Subconscious()
        self.last_feeling = Feeling()

    def feel(
        self,
        symbol: str,
        signal_confidence: float,
        equity: float,
        daily_pnl: float,
        kill_switch: bool,
    ) -> Feeling:
        notes: List[str] = []
        aggression = 0.55
        trust = signal_confidence
        mood = "neutral"

        if kill_switch:
            return Feeling(
                mood="fearful",
                aggression=0.0,
                trust_signal=0.0,
                notes=["Kill switch active — conscience freezes all action"],
            )

        vol = self.sub.volatility(symbol)
        regime = self.sub.regime(symbol)
        recent_pnl = self.sub.recent_pnl()
        win_rate = self.sub.win_rate()

        if vol is not None:
            if vol > 0.012:
                aggression *= 0.45
                trust *= 0.7
                notes.append(f"High volatility ({vol:.4f}) — size down")
                mood = "cautious"
            elif vol < 0.003:
                aggression *= 1.1
                notes.append("Low volatility — slightly more room")

        if regime == "downtrend":
            aggression *= 0.6
            notes.append("Downtrend regime — defensive")
            mood = "cautious"
        elif regime == "uptrend":
            aggression *= 1.05
            notes.append("Uptrend regime — mild confidence")
            if mood == "neutral":
                mood = "confident"

        if recent_pnl < 0:
            aggression *= 0.5
            trust *= 0.75
            notes.append(f"Recent pain (pnl={recent_pnl:.2f}) — slow down")
            mood = "fearful"
        elif recent_pnl > 0 and (win_rate or 0) > 0.6:
            aggression *= 1.1
            notes.append("Recent wins — measured confidence")
            mood = "confident"

        if equity > 0 and daily_pnl < 0:
            dd = abs(daily_pnl) / equity
            if dd > 0.01:
                aggression *= 0.4
                notes.append(f"Daily drawdown {dd*100:.1f}% — protect capital")
                mood = "fearful"

        # Memory bias from seed + user notes
        caution_words = (
            "volatile", "crash", "careful", "risk", "fear", "uncertain",
            "risk-off", "avoid", "weak", "extended", "chase", "fomo",
            "survival", "reduce size", "pullback",
        )
        confidence_words = ("outperform", "momentum", "strength", "uptrend", "bid")
        mem_caution = 0
        mem_confidence = 0
        for n in self.sub.notes[-20:]:
            lower = n.lower()
            if any(w in lower for w in caution_words):
                mem_caution += 1
            if any(w in lower for w in confidence_words):
                mem_confidence += 1

        if mem_caution > 0:
            aggression *= max(0.5, 1.0 - 0.06 * mem_caution)
            notes.append(f"Memory urges caution ({mem_caution} notes)")
            if mood in ("neutral", "confident"):
                mood = "cautious"

        if mem_confidence > mem_caution and regime == "uptrend":
            aggression *= 1.05
            notes.append("Memory supports selective strength")

        aggression = max(0.0, min(1.0, aggression))
        trust = max(0.0, min(1.0, trust))

        if aggression < 0.25:
            mood = "fearful"
        elif aggression > 0.75 and mood == "neutral":
            mood = "confident"

        feeling = Feeling(mood=mood, aggression=aggression, trust_signal=trust, notes=notes)
        self.last_feeling = feeling
        return feeling

    def approve(self, feeling: Feeling, min_aggression: float = 0.2) -> tuple[bool, str]:
        if feeling.aggression < min_aggression:
            return False, f"Conscience withholds approval (aggression={feeling.aggression:.2f}, mood={feeling.mood})"
        if feeling.trust_signal < 0.35:
            return False, f"Conscience distrusts signal (trust={feeling.trust_signal:.2f})"
        return True, "Conscience approves"

    def status(self, symbol: str = "BTC-USD") -> dict:
        return {
            "principles": self.PRINCIPLES,
            "feeling": self.last_feeling.to_dict(),
            "subconscious": self.sub.snapshot(symbol),
        }
