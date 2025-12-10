"""Main orchestration loop for the Polymarket crypto arbitrage bot."""
from __future__ import annotations
import asyncio
from typing import Optional, Tuple

from polymarket_bot.config import BotConfig
from polymarket_bot.integrations.polymarket import PolymarketClient
from polymarket_bot.models import PortfolioState, RiskLimits, Position
from polymarket_bot.services.analytics import PerformanceTracker
from polymarket_bot.services.execution import ExecutionService
from polymarket_bot.services.market_scanner import MarketScanner
from polymarket_bot.services import portfolio


class TradingBot:
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.portfolio = PortfolioState(cash=10_000)
        self.risk_limits = RiskLimits(
            max_daily_loss=config.max_daily_loss,
            max_position_per_market=config.max_position_per_market,
            risk_free_rate=config.risk_free_rate,
        )
        self.performance = PerformanceTracker()
        self.polymarket_client = PolymarketClient(
            base_url=config.api_url,
            api_key=config.polymarket_api_key,
            rate_limit_per_minute=config.rate_limit_per_minute,
        )
        self.market_scanner = MarketScanner(self.polymarket_client)
        self.execution = ExecutionService(self.polymarket_client, self.portfolio)

    async def run_forever(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(self.config.poll_interval)

    async def tick(self) -> None:
        if portfolio.enforce_daily_loss(self.portfolio, self.risk_limits):
            print("Daily loss limit reached - pausing trading")
            return

        markets = await self.market_scanner.scan()
        if not markets:
            print("No qualifying crypto 15m markets found")
            return

        for market in markets:
            await self._trade_market(market)

    async def _trade_market(self, market) -> None:
        best_quote = await self.polymarket_client.best_bid_ask(market.id)
        yes_price = (
            best_quote.get("bestAsk", market.outcome_yes_price) if best_quote else market.outcome_yes_price
        )
        no_price = (
            best_quote.get("bestBid", market.outcome_no_price) if best_quote else market.outcome_no_price
        )

        yes_pos, no_pos = self._positions_for_market(market.id)
        combined_price = yes_price + no_price
        cheap_side, cheap_price = ("YES", yes_price) if yes_price < no_price else ("NO", no_price)

        base_size = min(self.portfolio.cash * 0.05, self.risk_limits.max_position_per_market)
        if cheap_price < 0.35 and base_size > 0:
            if combined_price <= 0.99:
                projected_avg = self._combined_average(
                    yes_pos,
                    no_pos,
                    add_yes=base_size,
                    add_no=base_size,
                    price_yes=yes_price,
                    price_no=no_price,
                )
                if projected_avg < 0.99:
                    await self._buy_side(market.id, "YES", base_size, yes_price)
                    await self._buy_side(market.id, "NO", base_size, no_price)
                    self.performance.log_trade(
                        market_id=market.id,
                        action="HEDGE",
                        size=base_size,
                        price=combined_price,
                        confidence=0.9,
                        reasoning="Bought both sides under $0.99 to lock spread",
                    )
                    return
            else:
                await self._buy_side(market.id, cheap_side, base_size, cheap_price)
                self.performance.log_trade(
                    market_id=market.id,
                    action=f"BUY_{cheap_side}",
                    size=base_size,
                    price=cheap_price,
                    confidence=0.7,
                    reasoning="Accumulating discounted side awaiting hedge",
                )
                return

        # If no hedge is available and we hold a single-side position, close at break-even or better
        if yes_pos and not no_pos and yes_price >= yes_pos.average_price:
            await self.execution.close_position(market.id, "YES", yes_price)
            self.performance.log_trade(
                market_id=market.id,
                action="CLOSE_YES",
                size=yes_pos.size,
                price=yes_price,
                confidence=0.5,
                reasoning="No hedge available; closing YES at no loss",
            )
        if no_pos and not yes_pos and no_price >= no_pos.average_price:
            await self.execution.close_position(market.id, "NO", no_price)
            self.performance.log_trade(
                market_id=market.id,
                action="CLOSE_NO",
                size=no_pos.size,
                price=no_price,
                confidence=0.5,
                reasoning="No hedge available; closing NO at no loss",
            )

    def _positions_for_market(self, market_id: str) -> Tuple[Optional[Position], Optional[Position]]:
        yes_key = f"{market_id}:YES"
        no_key = f"{market_id}:NO"
        return self.portfolio.positions.get(yes_key), self.portfolio.positions.get(no_key)

    def _combined_average(
        self,
        yes_pos,
        no_pos,
        *,
        add_yes: float,
        add_no: float,
        price_yes: float,
        price_no: float,
    ) -> float:
        yes_cost = (yes_pos.average_price * yes_pos.size if yes_pos else 0) + price_yes * add_yes
        no_cost = (no_pos.average_price * no_pos.size if no_pos else 0) + price_no * add_no
        yes_total = (yes_pos.size if yes_pos else 0) + add_yes
        no_total = (no_pos.size if no_pos else 0) + add_no
        combined = 0.0
        if yes_total:
            combined += yes_cost / yes_total
        if no_total:
            combined += no_cost / no_total
        return combined

    async def _buy_side(self, market_id: str, side: str, size: float, price: float) -> None:
        clamped = portfolio.clamp_position(size, self.risk_limits)
        if clamped <= 0:
            return
        await self.execution.execute_market_order(
            market_id=market_id,
            size=clamped,
            price=price,
            side=side,
        )


async def run_bot(config: BotConfig) -> None:
    bot = TradingBot(config)
    await bot.tick()


async def run_bot_forever(config: BotConfig) -> None:
    bot = TradingBot(config)
    await bot.run_forever()
