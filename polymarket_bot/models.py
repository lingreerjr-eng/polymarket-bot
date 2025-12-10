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

        normalized = self.question.strip().lower()
        exact_titles = {
            "bitcoin up or down - 15 minute",
            "bitcoin up or down - 15 minutes",
            "ethereum up or down - 15 minute",
            "ethereum up or down - 15 minutes",
            "xrp up or down - 15 minute",
            "xrp up or down - 15 minutes",
        }
        if normalized in exact_titles:
            return True

        assets = ["bitcoin", "btc", "ethereum", "eth", "xrp", "ripple", "crypto"]
        has_asset = any(asset in normalized for asset in assets)
        time_tokens = [
            "15m",
            "15 m",
            "15 minute",
            "15 minutes",
            "15-minute",
            "15-minutes",
            "15 min",
            "quarter",
        ]
        has_time = any(token in normalized for token in time_tokens) or " 15" in normalized
        directional_tokens = ["up", "down", "up/down", "up or down", "rise", "fall", "increase", "decrease"]
        has_direction = any(token in normalized for token in directional_tokens)
        return has_asset and has_time and has_direction


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
