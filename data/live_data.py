"""Live market data from Coinbase Exchange (public), DexScreener, and CoinGecko.

No API keys required for public endpoints. Used by the Data Layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

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

    async def get_market_state(self, product_id: str = "BTC-USD") -> MarketState:
        """Return a normalized MarketState from Coinbase ticker."""
        try:
            raw = await self.coinbase_ticker(product_id)
            last = float(raw.get("price") or 0)
            bid = float(raw.get("bid") or 0)
            ask = float(raw.get("ask") or 0)
            volume = float(raw.get("volume") or 0)
            spread_bps = 0.0
            if last > 0 and bid > 0 and ask > 0:
                spread_bps = ((ask - bid) / last) * 10_000

            return MarketState(
                symbol=product_id,
                last=last,
                bid=bid,
                ask=ask,
                volume_24h=volume,
                spread_bps=round(spread_bps, 2),
                timestamp=datetime.now(timezone.utc),
                extra={"source": "coinbase", "raw": raw},
            )
        except Exception as e:
            return MarketState(
                symbol=product_id,
                timestamp=datetime.now(timezone.utc),
                extra={"error": str(e)},
            )

    async def search_coingecko(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simple CoinGecko search."""
        client = await self._get_client()
        url = f"{COINGECKO_BASE}/search"
        r = await client.get(url, params={"query": query})
        r.raise_for_status()
        data = r.json()
        coins = data.get("coins", [])[:limit]
        return [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "symbol": c.get("symbol"),
                "market_cap_rank": c.get("market_cap_rank"),
            }
            for c in coins
        ]

    async def dexscreener_pairs(self, query: str) -> List[Dict[str, Any]]:
        """Search pairs on DexScreener."""
        client = await self._get_client()
        url = f"{DEXSCREENER_BASE}/latest/dex/search"
        r = await client.get(url, params={"q": query})
        r.raise_for_status()
        data = r.json()
        pairs = data.get("pairs") or []
        return pairs[:8]
