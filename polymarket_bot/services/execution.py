"""Order execution with risk management hooks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from polymarket_bot.integrations.polymarket import PolymarketClient
from polymarket_bot.models import PortfolioState, Position


@dataclass
class ExecutionResult:
    status: str
    payload: Dict[str, object]


class ExecutionService:
    def __init__(self, client: PolymarketClient, portfolio: PortfolioState) -> None:
        self.client = client
        self.portfolio = portfolio

    async def execute_market_order(
        self, market_id: str, size: float, price: float, side: str
    ) -> ExecutionResult:
        result = await self.client.place_order(market_id, size=size, price=price, side=side)
        self._update_portfolio(market_id, size=size, price=price, side=side)
        return ExecutionResult(status=str(result.get("status", "submitted")), payload=result)

    def _position_key(self, market_id: str, side: str) -> str:
        return f"{market_id}:{side.upper()}"

    def _update_portfolio(self, market_id: str, size: float, price: float, side: str) -> None:
        key = self._position_key(market_id, side)
        pos = self.portfolio.positions.get(key)
        if not pos:
            pos = Position(market_id=market_id, size=0, average_price=price, side=side)
            self.portfolio.positions[key] = pos
        total_cost = pos.average_price * abs(pos.size)
        new_cost = price * abs(size)
        pos.average_price = (total_cost + new_cost) / max(abs(pos.size + size), 1)
        pos.size += abs(size)

    async def close_position(self, market_id: str, side: str, price: float) -> ExecutionResult:
        key = self._position_key(market_id, side)
        pos = self.portfolio.positions.get(key)
        if not pos:
            return ExecutionResult(status="skipped", payload={"reason": "no position"})
        size = abs(pos.size)
        exit_side = "NO" if side.upper() == "YES" else "YES"
        result = await self.client.place_order(market_id, size=size, price=price, side=exit_side)
        self.portfolio.realized_pnl += (price - pos.average_price) * pos.size
        del self.portfolio.positions[key]
        return ExecutionResult(status=str(result.get("status", "closed")), payload=result)
