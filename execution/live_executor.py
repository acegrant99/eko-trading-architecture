"""Live trading executor using Coinbase Advanced Trade API.

Requires:
  COINBASE_API_KEY
  COINBASE_API_SECRET

Uses the official coinbase-advanced-py SDK.
Paper mode is the default everywhere else in the system.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from data.models import Signal, MarketState, Trade
from execution.trade_logger import append_trade_log


class LiveExecutor:
    """Places real orders on Coinbase Advanced Trade.

    Safety notes:
    - Only activates when both API key and secret are present.
    - Uses market orders by default for simplicity (can be changed later).
    - Always logs every attempt.
    """

    def __init__(self):
        self.api_key = os.getenv("COINBASE_API_KEY", "").strip()
        self.api_secret = os.getenv("COINBASE_API_SECRET", "").strip()
        self._client = None
        self.enabled = bool(self.api_key and self.api_secret)
        self.last_error: Optional[str] = None

        if self.enabled:
            try:
                from coinbase.rest import RESTClient
                self._client = RESTClient(api_key=self.api_key, api_secret=self.api_secret)
            except Exception as e:
                self.enabled = False
                self.last_error = f"Failed to init Coinbase client: {e}"

    def is_ready(self) -> bool:
        return self.enabled and self._client is not None

    def execute(self, signal: Signal, market: MarketState) -> dict:
        if not self.is_ready():
            return {
                "status": "error",
                "reason": self.last_error or "Live executor not configured (missing API keys)",
            }

        if signal.side.value == "HOLD" or signal.size <= 0:
            return {"status": "skipped", "reason": "HOLD or zero size"}

        product_id = signal.symbol
        side = signal.side.value.lower()  # "buy" or "sell"
        client_order_id = str(uuid.uuid4())

        try:
            if side == "buy":
                # Market buy using quote_size (USD)
                # signal.size is treated as base size; convert roughly via last price
                price = market.last or 0
                if price <= 0:
                    return {"status": "error", "reason": "No market price"}
                quote_size = str(round(signal.size * price, 2))
                order = self._client.market_order_buy(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    quote_size=quote_size,
                )
            else:
                # Market sell using base_size
                base_size = str(round(signal.size, 8))
                order = self._client.market_order_sell(
                    client_order_id=client_order_id,
                    product_id=product_id,
                    base_size=base_size,
                )

            # Normalize response
            order_dict = order.to_dict() if hasattr(order, "to_dict") else dict(order)
            success = order_dict.get("success", False)

            trade = Trade(
                id=client_order_id[:8],
                symbol=product_id,
                side=signal.side.value,
                size=signal.size,
                price=market.last or 0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reason=f"LIVE: {signal.reason}",
            )
            append_trade_log({**trade.to_dict(), "live": True, "raw": order_dict})

            if success:
                return {
                    "status": "filled",
                    "mode": "live",
                    "trade": trade.to_dict(),
                    "order": order_dict,
                }
            else:
                error = order_dict.get("error_response") or order_dict.get("error") or "Unknown error"
                return {
                    "status": "error",
                    "mode": "live",
                    "reason": str(error),
                    "order": order_dict,
                }

        except Exception as e:
            self.last_error = str(e)
            return {
                "status": "error",
                "mode": "live",
                "reason": str(e),
            }

    def get_accounts(self) -> Dict[str, Any]:
        if not self.is_ready():
            return {"error": "Live executor not ready"}
        try:
            accounts = self._client.get_accounts()
            return accounts.to_dict() if hasattr(accounts, "to_dict") else dict(accounts)
        except Exception as e:
            return {"error": str(e)}

    def status(self) -> dict:
        return {
            "mode": "live",
            "ready": self.is_ready(),
            "last_error": self.last_error,
            "has_keys": bool(self.api_key and self.api_secret),
        }
