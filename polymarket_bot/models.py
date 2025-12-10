"""Core data models used by the trading bot."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Market:
    id: str
    question: str
    outcome_yes_price: float
    outcome_no_price: float
    ends_at: datetime
    liquidity: float
    volume: float
    source: str

    @property
    def is_crypto_quarter_hour(self) -> bool:
        """Return True when the market is a 15-minute BTC/ETH/XRP up/down contract."""

        normalized = self.question.lower()
        assets = ["bitcoin", "btc", "ethereum", "eth", "xrp", "ripple"]
        return (
            any(asset in normalized for asset in assets)
            and "up" in normalized
            and "down" in normalized
            and "15" in normalized
        )


@dataclass
class Forecast:
    probability_yes: float
    reasoning: str
    confidence: float


@dataclass
class Critique:
    concerns: List[str]
    approval: bool


@dataclass
class TradeDecision:
    action: str  # "BUY" | "SELL" | "SKIP"
    probability_yes: float
    size: float
    reasoning: str
    confidence: float


@dataclass
class Position:
    market_id: str
    size: float
    average_price: float
    side: str  # "YES" or "NO"
    opened_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PortfolioState:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    def total_value(self) -> float:
        return self.cash + self.realized_pnl + self.unrealized_pnl


@dataclass
class RiskLimits:
    max_daily_loss: float
    max_position_per_market: float
    risk_free_rate: float


@dataclass
class DecisionContext:
    market: Market
    portfolio: PortfolioState
    news: Optional[str] = None


@dataclass
class MicrostructureSnapshot:
    """Single-time snapshot of order book microstructure state."""

    market_id: str
    timestamp: datetime
    best_bid: float
    best_ask: float
    spread: float
    depth_bid: float
    depth_ask: float
    near_top_depth: float
    realized_vol_1m: float
    depth_change_30s: float
    spread_change: float
    in_macro_window: bool


@dataclass
class TimingFeatures:
    """Feature vector for the timing classifier (designed for backtests)."""

    timestamp: datetime
    realized_vol_1m: float
    depth_change_30s: float
    spread_change: float
    in_macro_window: bool
