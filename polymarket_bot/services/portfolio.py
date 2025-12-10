"""Portfolio sizing utilities (Kelly and risk parity)."""
from __future__ import annotations

import math
from typing import Dict, Iterable

from polymarket_bot.models import Market, PortfolioState, RiskLimits


def kelly_position(edge: float, price: float, bankroll: float) -> float:
    if price <= 0 or price >= 1:
        return 0.0
    fraction = edge / (price * (1 - price))
    fraction = max(min(fraction, 1.0), -1.0)
    return bankroll * fraction


def risk_parity_weights(positions: Iterable[Market]) -> Dict[str, float]:
    markets = list(positions)
    if not markets:
        return {}
    weight = 1.0 / len(markets)
    return {m.id: weight for m in markets}


def clamp_position(size: float, limits: RiskLimits) -> float:
    return max(min(size, limits.max_position_per_market), -limits.max_position_per_market)


def enforce_daily_loss(portfolio: PortfolioState, limits: RiskLimits) -> bool:
    return portfolio.realized_pnl + portfolio.unrealized_pnl <= -limits.max_daily_loss
