"""HTTP client for Polymarket live and demo APIs.

This module keeps requests lightweight and rate-limited so it can run in
restricted environments while still demonstrating the trading flow.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable, List, Optional

import httpx

from polymarket_bot.models import Market


class RateLimiter:
    """Simple token bucket limiter."""

    def __init__(self, per_minute: int) -> None:
        self.capacity = per_minute
        self.tokens = per_minute
        self.updated = asyncio.get_event_loop().time()

    async def acquire(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self.updated
        refill = (elapsed / 60) * self.capacity
        if refill >= 1:
            self.tokens = min(self.capacity, self.tokens + int(refill))
            self.updated = now
        if self.tokens <= 0:
            await asyncio.sleep(1)
            return await self.acquire()
        self.tokens -= 1


class PolymarketClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        rate_limit_per_minute: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.rate_limiter = RateLimiter(rate_limit_per_minute)

    async def _get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        await self.rate_limiter.acquire()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(base_url=self.base_url, headers=headers) as client:
            response = await client.get(path, params=params, timeout=20)
            response.raise_for_status()
            return response

    async def list_markets(self) -> List[Market]:
        """Return *all* available markets (no crypto filter) from the API."""

        try:
            response = await self._get("/markets", params={"limit": 250})
            data = response.json()
        except Exception:
            data = []

        if isinstance(data, dict):
            markets_data = data.get("markets") or data.get("data") or data.get("results") or []
        else:
            markets_data = data

        parsed = [self._parse_market(item) for item in markets_data if isinstance(item, dict)]
        return parsed

    def _parse_market(self, item: dict) -> Market:
        raw_end = item.get("endDate") or item.get("closeTime") or ""
        try:
            ends_at = datetime.fromisoformat(raw_end.replace("Z", "+00:00")) if raw_end else datetime.utcnow()
        except Exception:
            ends_at = datetime.utcnow()
        return Market(
            id=str(item.get("id")),
            question=item.get("question", ""),
            outcome_yes_price=float(item.get("yesPrice", 0.0)),
            outcome_no_price=float(item.get("noPrice", 0.0)),
            ends_at=ends_at,
            liquidity=float(item.get("liquidity", 0.0)),
            volume=float(item.get("volume", 0.0)),
            source=self.base_url,
        )

    async def place_order(
        self,
        market_id: str,
        size: float,
        price: float,
        side: str,
    ) -> dict:
        payload = {"marketId": market_id, "size": size, "price": price, "side": side}
        await self.rate_limiter.acquire()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(base_url=self.base_url, headers=headers) as client:
                response = await client.post("/orders", json=payload, timeout=20)
                response.raise_for_status()
                return response.json()
        except Exception:
            return {"status": "simulated", "payload": payload}

    async def order_book(self, market_id: str) -> dict:
        """Return an order book snapshot with depth aggregates."""

        try:
            response = await self._get(f"/markets/{market_id}/book")
            data = response.json()
        except Exception:
            data = {}

        bids = data.get("bids", []) or []
        asks = data.get("asks", []) or []
        best_bid = float(bids[0].get("price", 0.0)) if bids else 0.0
        best_ask = float(asks[0].get("price", 1.0)) if asks else 1.0
        depth_bid = sum(float(b.get("size", 0.0)) for b in bids[:5])
        depth_ask = sum(float(a.get("size", 0.0)) for a in asks[:5])
        near_top_depth = sum(float(b.get("size", 0.0)) for b in bids[:2]) + sum(
            float(a.get("size", 0.0)) for a in asks[:2]
        )
        return {
            "bids": bids,
            "asks": asks,
            "bestBid": best_bid,
            "bestAsk": best_ask,
            "depthBid": depth_bid,
            "depthAsk": depth_ask,
            "nearTopDepth": near_top_depth,
        }


async def filter_markets_for_crypto(markets: Iterable[Market]) -> List[Market]:
    return [m for m in markets if m.is_crypto_quarter_hour]
