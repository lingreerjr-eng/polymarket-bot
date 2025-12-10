"""Scans Polymarket for BTC/ETH/XRP 15-minute markets."""
from __future__ import annotations

from typing import List

from polymarket_bot.integrations.polymarket import PolymarketClient, filter_markets_for_crypto
from polymarket_bot.models import Market


class MarketScanner:
    def __init__(self, client: PolymarketClient) -> None:
        self.client = client

    async def scan(self) -> List[Market]:
        markets = await self.client.list_markets()
        return await filter_markets_for_crypto(markets)
