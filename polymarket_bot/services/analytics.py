"""Performance tracking and cost analytics."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class TradeLog:
    timestamp: datetime
    market_id: str
    action: str
    size: float
    price: float
    confidence: float
    reasoning: str


@dataclass
class PerformanceTracker:
    trades: List[TradeLog] = field(default_factory=list)
    ai_costs: float = 0.0

    def log_trade(
        self, market_id: str, action: str, size: float, price: float, confidence: float, reasoning: str
    ) -> None:
        self.trades.append(
            TradeLog(
                timestamp=datetime.utcnow(),
                market_id=market_id,
                action=action,
                size=size,
                price=price,
                confidence=confidence,
                reasoning=reasoning,
            )
        )

    def total_volume(self) -> float:
        return sum(abs(t.size) for t in self.trades)

    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = len([t for t in self.trades if t.confidence >= 0.5])
        return wins / len(self.trades)
