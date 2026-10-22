"""Live trading executor using Coinbase Advanced Trade API.

Supports:
- Market and Limit orders
- Position / balance sync from Coinbase
- Order cancellation
- Persistent trade logging

Requires:
  COINBASE_API_KEY
  COINBASE_API_SECRET
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from data.models import Signal, MarketState, Trade, Position, OrderType
from execution.trade_logger import append_trade_log


class LiveExecutor:
    """Places real orders on Coinbase Advanced Trade."""

    def __init__(self):
        self.api_key = os.getenv("COINBASE_API_KEY", "").strip()
        self.api_secret = os.getenv("COINBASE_API_SECRET", "").strip()
        self._client = None
        self.enabled = bool(self.api_key and self.api_secret)
        self.last_error: Optional[str] = None
        self.positions: dict[str, Position] = {}
        self.balances: dict[str, float] = {}
        self.equity_usd: float = 0.0

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
        side = signal.side.value.lower()
        client_order_id = str(uuid.uuid4())
        order_type = signal.order_type or OrderType.MARKET

        try:
            if order_type == OrderType.LIMIT:
                order = self._place_limit(signal, market, client_order_id)
            else:
                order = self._place_market(signal, market, client_order_id)

            order_dict = order.to_dict() if hasattr(order, "to_dict") else dict(order)
            success = order_dict.get("success", False)

            trade = Trade(
                id=client_order_id[:8],
                symbol=product_id,
                side=signal.side.value,
                size=signal.size,
                price=signal.limit_price or market.last or 0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reason=f"LIVE: {signal.reason}",
                order_type=order_type.value,
                live=True,
            )
            append_trade_log({**trade.to_dict(), "raw": order_dict})

            # Refresh positions after order
            self.sync_positions()

            if success:
                return {
                    "status": "filled" if order_type == OrderType.MARKET else "submitted",
                    "mode": "live",
                    "order_type": order_type.value,
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
            return {"status": "error", "mode": "live", "reason": str(e)}

    def _place_market(self, signal: Signal, market: MarketState, client_order_id: str):
        side = signal.side.value.lower()
        product_id = signal.symbol
        price = market.last or 0.0

        if side == "buy":
            if price <= 0:
                raise ValueError("No market price for market buy")
            quote_size = str(round(signal.size * price, 2))
            return self._client.market_order_buy(
                client_order_id=client_order_id,
                product_id=product_id,
                quote_size=quote_size,
            )
        else:
            base_size = str(round(signal.size, 8))
            return self._client.market_order_sell(
                client_order_id=client_order_id,
                product_id=product_id,
                base_size=base_size,
            )

    def _place_limit(self, signal: Signal, market: MarketState, client_order_id: str):
        side = signal.side.value.lower()
        product_id = signal.symbol
        limit_price = signal.limit_price
        if not limit_price or limit_price <= 0:
            # Default: slight improvement vs market
            last = market.last or 0
            if last <= 0:
                raise ValueError("No price available for limit order")
            limit_price = last * (0.999 if side == "buy" else 1.001)

        base_size = str(round(signal.size, 8))
        limit_price_str = str(round(limit_price, 2))

        if side == "buy":
            return self._client.limit_order_gtc_buy(
                client_order_id=client_order_id,
                product_id=product_id,
                base_size=base_size,
                limit_price=limit_price_str,
            )
        else:
            return self._client.limit_order_gtc_sell(
                client_order_id=client_order_id,
                product_id=product_id,
                base_size=base_size,
                limit_price=limit_price_str,
            )

    def sync_positions(self) -> dict:
        """Pull balances from Coinbase and map into Position objects."""
        if not self.is_ready():
            return {"error": "not ready"}

        try:
            accounts_resp = self._client.get_accounts()
            accounts_data = accounts_resp.to_dict() if hasattr(accounts_resp, "to_dict") else dict(accounts_resp)
            accounts = accounts_data.get("accounts") or accounts_data.get("data") or []

            self.balances = {}
            self.positions = {}
            equity = 0.0

            for acc in accounts:
                currency = (acc.get("currency") or acc.get("available_balance", {}).get("currency") or "").upper()
                # available_balance can be nested
                bal_info = acc.get("available_balance") or {}
                if isinstance(bal_info, dict):
                    available = float(bal_info.get("value") or bal_info.get("amount") or 0)
                else:
                    available = float(acc.get("available") or acc.get("balance") or 0)

                hold_info = acc.get("hold") or {}
                if isinstance(hold_info, dict):
                    hold = float(hold_info.get("value") or 0)
                else:
                    hold = 0.0

                total = available + hold
                if total <= 0:
                    continue

                self.balances[currency] = total

                if currency in ("USD", "USDC", "USDT"):
                    equity += total
                else:
                    # Treat non-fiat as a position (entry_price unknown → 0)
                    symbol = f"{currency}-USD"
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        side="LONG",
                        size=total,
                        entry_price=0.0,
                        currency=currency,
                    )

            self.equity_usd = equity
            return {
                "balances": self.balances,
                "positions": {k: v.to_dict() for k, v in self.positions.items()},
                "equity_usd": self.equity_usd,
            }
        except Exception as e:
            self.last_error = str(e)
            return {"error": str(e)}

    def cancel_all_orders(self) -> dict:
        if not self.is_ready():
            return {"error": "not ready"}
        try:
            # Prefer batch cancel if available; fallback to listing + cancel
            result = self._client.cancel_orders(order_ids=[])  # empty may mean all depending on SDK
            return result.to_dict() if hasattr(result, "to_dict") else dict(result)
        except Exception as e:
            # Fallback: list open orders then cancel
            try:
                orders = self._client.list_orders(order_status=["OPEN"])
                orders_data = orders.to_dict() if hasattr(orders, "to_dict") else dict(orders)
                order_list = orders_data.get("orders") or []
                ids = [o.get("order_id") for o in order_list if o.get("order_id")]
                if not ids:
                    return {"ok": True, "cancelled": 0}
                result = self._client.cancel_orders(order_ids=ids)
                return result.to_dict() if hasattr(result, "to_dict") else dict(result)
            except Exception as e2:
                return {"error": str(e2)}

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
            "balances": self.balances,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "equity_usd": self.equity_usd,
        }
