"""Backtestable timing classifier used for entry gating."""
from __future__ import annotations

from dataclasses import dataclass
from polymarket_bot.models import TimingFeatures


@dataclass
class TimingClassifier:
    volatility_threshold: float
    depth_acceleration_threshold: float
    spread_widening_limit: float

    def allow_entry(self, features: TimingFeatures) -> bool:
        """Deterministic timing gate so it can be reused in backtests."""

        if features.in_macro_window:
            return False
        if features.realized_vol_1m >= self.volatility_threshold:
            return False
        if features.depth_change_30s <= self.depth_acceleration_threshold:
            return False
        if features.spread_change >= self.spread_widening_limit:
            return False
        return True

