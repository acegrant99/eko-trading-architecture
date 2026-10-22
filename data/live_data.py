"""Live market data from Coinbase Exchange (public) and DexScreener.

No API keys required. Used by the Data Layer.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import httpx

from data.models import MarketState


COINBASE_BASE = "https://api.exchange.coinbase.com"
DEXSCREENER_BASE = "https://api.dexscreener.com"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"


class LiveDataProvider:
    """Fetches normalized MarketState from public endpoints."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def coinbase_ticker(self, product_id: str = "BTC-USD") -> dict:
        """GET /products/{product_id}/ticker — public, no auth."""
        client = await self._get_client()
        url = f"{COINBASE_BASE}/products/{product_id}/ticker"
        r = await client.get(url)
        r.raise_for_status()
        return r.json()
