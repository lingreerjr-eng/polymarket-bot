"""Real-time Polymarket microstructure scanner."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from statistics import pstdev
from typing import Deque, Dict, Tuple

from polymarket_bot.integrations.polymarket import PolymarketClient
from polymarket_bot.models import Market, MicrostructureSnapshot


class MicrostructureScanner:
    """Tracks order book dynamics for volatility, depth, and spread changes."""

    def __init__(self, client: PolymarketClient) -> None:
        self.client = client
        self.price_history: Dict[str, Deque[Tuple[datetime, float]]] = {}
        self.depth_history: Dict[str, Deque[Tuple[datetime, float]]] = {}
        self.spread_history: Dict[str, Deque[Tuple[datetime, float]]] = {}

    async def snapshot(self, market: Market) -> MicrostructureSnapshot:
        book = await self.client.order_book(market.id)
        now = datetime.utcnow().replace(tzinfo=timezone.utc)

        best_bid = float(book.get("bestBid", market.outcome_no_price))
        best_ask = float(book.get("bestAsk", market.outcome_yes_price))
        depth_bid = float(book.get("depthBid", 0.0))
        depth_ask = float(book.get("depthAsk", 0.0))
        near_top_depth = float(book.get("nearTopDepth", depth_bid + depth_ask))
        spread = max(best_ask - best_bid, 0.0)
        mid = (best_bid + best_ask) / 2 if best_bid and best_ask else best_ask or best_bid
        combined_depth = depth_bid + depth_ask

        self._append(self.price_history, market.id, now, mid)
        self._append(self.depth_history, market.id, now, combined_depth)
        self._append(self.spread_history, market.id, now, spread)

        realized_vol = self._realized_volatility(market.id, window=timedelta(minutes=1))
        depth_change = self._change_over(market.id, self.depth_history, timedelta(seconds=30))
        spread_change = self._change_over(market.id, self.spread_history, timedelta(seconds=30))

        return MicrostructureSnapshot(
            market_id=market.id,
            timestamp=now,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            depth_bid=depth_bid,
            depth_ask=depth_ask,
            near_top_depth=near_top_depth,
            realized_vol_1m=realized_vol,
            depth_change_30s=depth_change,
            spread_change=spread_change,
            in_macro_window=self._in_macro_window(now),
        )

    def _append(
        self,
        store: Dict[str, Deque[Tuple[datetime, float]]],
        key: str,
        timestamp: datetime,
        value: float,
        *,
        max_age: timedelta = timedelta(minutes=5),
    ) -> None:
        series = store.setdefault(key, deque())
        series.append((timestamp, value))
        cutoff = timestamp - max_age
        while series and series[0][0] < cutoff:
            series.popleft()

    def _realized_volatility(self, market_id: str, window: timedelta) -> float:
        series = self.price_history.get(market_id)
        if not series:
            return 0.0
        cutoff = series[-1][0] - window
        relevant = [price for ts, price in series if ts >= cutoff]
        if len(relevant) < 2:
            return 0.0
        returns = []
        for first, second in zip(relevant[:-1], relevant[1:]):
            if first <= 0:
                continue
            returns.append((second - first) / first)
        return pstdev(returns) if len(returns) >= 2 else (abs(returns[0]) if returns else 0.0)

    def _change_over(
        self,
        market_id: str,
        store: Dict[str, Deque[Tuple[datetime, float]]],
        window: timedelta,
    ) -> float:
        series = store.get(market_id)
        if not series:
            return 0.0
        now = series[-1][0]
        cutoff = now - window
        current = series[-1][1]
        past_values = [value for ts, value in series if ts <= cutoff]
        if not past_values:
            return 0.0
        past = past_values[-1]
        if past == 0:
            return 0.0
        return (current - past) / past

    def _in_macro_window(self, ts: datetime) -> bool:
        """Approximate macro/news windows (e.g., CPI/FOMC releases)."""

        # Default to UTC hours that overlap with US 8:00-15:00 ET (~13:00-20:00 UTC)
        hour = ts.hour
        high_impact_hours = range(13, 21)
        return hour in high_impact_hours

    @staticmethod
    def is_quiet_us_hour(ts: datetime) -> bool:
        """Return True for midnight to early-morning US hours (05:00-10:00 UTC)."""

        return ts.hour in range(5, 11)

