"""Minimal FastAPI dashboard to expose live metrics."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from polymarket_bot.trading_bot import TradingBot


def create_app(bot: TradingBot) -> FastAPI:
    app = FastAPI(title="Polymarket Bitcoin Bot Dashboard")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "mode": bot.config.trading_mode}

    @app.get("/portfolio")
    async def portfolio() -> dict:
        return {
            "cash": bot.portfolio.cash,
            "positions": {k: v.__dict__ for k, v in bot.portfolio.positions.items()},
            "realized_pnl": bot.portfolio.realized_pnl,
            "unrealized_pnl": bot.portfolio.unrealized_pnl,
        }

    @app.get("/performance")
    async def performance() -> dict:
        return {
            "trades": [t.__dict__ for t in bot.performance.trades],
            "win_rate": bot.performance.win_rate(),
            "total_volume": bot.performance.total_volume(),
        }

    return app
