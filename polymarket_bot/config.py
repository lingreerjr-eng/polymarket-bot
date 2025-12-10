"""Configuration helpers for the Polymarket trading bot.

Environment variables are used for all sensitive settings. This module avoids
committing credentials to source control.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional


@dataclass
class BotConfig:
    """Runtime configuration for the bot."""

    polymarket_api_key: Optional[str]
    polymarket_base_url: str
    polymarket_demo_url: str
    trading_mode: str
    poll_interval: float
    max_daily_loss: float
    max_position_per_market: float
    risk_free_rate: float
    ollama_base_url: str
    ollama_model: str
    news_api_key: Optional[str]
    dashboard_host: str
    dashboard_port: int
    rate_limit_per_minute: int
    volatility_threshold: float
    mispricing_edge: float
    slippage_penalty: float
    hedge_timeout_seconds: int
    depth_acceleration_threshold: float
    spread_widening_limit: float

    @classmethod
    def from_env(cls) -> "BotConfig":
        trading_mode = os.getenv("TRADING_MODE", "demo").lower()
        return cls(
            polymarket_api_key=os.getenv("POLYMARKET_API_KEY"),
            polymarket_base_url=os.getenv(
                "POLYMARKET_BASE_URL", "https://clob.polymarket.com"
            ),
            polymarket_demo_url=os.getenv(
                "POLYMARKET_DEMO_URL", "https://clob.demo.polymarket.com"
            ),
            trading_mode=trading_mode,
            poll_interval=float(os.getenv("POLL_INTERVAL", "15")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "500")),
            max_position_per_market=float(
                os.getenv("MAX_POSITION_PER_MARKET", "250")
            ),
            risk_free_rate=float(os.getenv("RISK_FREE_RATE", "0.02")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
            news_api_key=os.getenv("NEWS_API_KEY"),
            dashboard_host=os.getenv("DASHBOARD_HOST", "0.0.0.0"),
            dashboard_port=int(os.getenv("DASHBOARD_PORT", "8000")),
            rate_limit_per_minute=int(os.getenv("POLYMARKET_RATE_LIMIT", "60")),
            volatility_threshold=float(os.getenv("VOLATILITY_THRESHOLD", "0.18")),
            mispricing_edge=float(os.getenv("MISPRICING_EDGE", "0.04")),
            slippage_penalty=float(os.getenv("SLIPPAGE_PENALTY", "0.01")),
            hedge_timeout_seconds=int(os.getenv("HEDGE_TIMEOUT_SECONDS", "45")),
            depth_acceleration_threshold=float(
                os.getenv("DEPTH_ACCELERATION_THRESHOLD", "0.05")
            ),
            spread_widening_limit=float(os.getenv("SPREAD_WIDENING_LIMIT", "0.02")),
        )

    @property
    def api_url(self) -> str:
        return (
            self.polymarket_base_url
            if self.trading_mode == "live"
            else self.polymarket_demo_url
        )

    @property
    def poll_period(self) -> timedelta:
        return timedelta(seconds=self.poll_interval)


def load_config() -> BotConfig:
    return BotConfig.from_env()
