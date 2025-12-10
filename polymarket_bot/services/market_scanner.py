"""Scans Polymarket for BTC/ETH/XRP 15-minute markets."""
from __future__ import annotations

from typing import List

from polymarket_bot.integrations.polymarket import PolymarketClient, filter_markets_for_crypto
from polymarket_bot.models import Market


class MarketScanner:
    def __init__(self, client: PolymarketClient) -> None:
        self.client = client
        self.last_total: int = 0
        self.last_filtered: int = 0
        self.last_all: List[Market] = []

    async def scan(self) -> List[Market]:
        markets = [m for m in await self.client.list_markets() if m.is_open_current_year]
        self.last_total = len(markets)
        self.last_all = markets
        filtered = await filter_markets_for_crypto(markets)
        self.last_filtered = len(filtered)
        return filtered
