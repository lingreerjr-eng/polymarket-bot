"""Main orchestration loop for the Polymarket crypto arbitrage bot."""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple

from polymarket_bot.config import BotConfig
from polymarket_bot.integrations.polymarket import PolymarketClient
from polymarket_bot.models import (
    PortfolioState,
    RiskLimits,
    Position,
    TimingFeatures,
)
from polymarket_bot.services.analytics import PerformanceTracker
from polymarket_bot.services.execution import ExecutionService
from polymarket_bot.services.market_scanner import MarketScanner
from polymarket_bot.services.microstructure import MicrostructureScanner
from polymarket_bot.services.timing_classifier import TimingClassifier
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
        self.microstructure = MicrostructureScanner(self.polymarket_client)
        self.timing_classifier = TimingClassifier(
            volatility_threshold=config.volatility_threshold,
            depth_acceleration_threshold=config.depth_acceleration_threshold,
            spread_widening_limit=config.spread_widening_limit,
        )
        self.pending_entries: Dict[str, datetime] = {}

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
        snapshot = await self.microstructure.snapshot(market)
        yes_price = min(snapshot.best_ask, market.outcome_yes_price)
        no_price = min(snapshot.best_bid, market.outcome_no_price)
        combined_price = yes_price + no_price

        yes_pos, no_pos = self._positions_for_market(market.id)
        cheap_side, cheap_price = ("YES", yes_price) if yes_price < no_price else ("NO", no_price)
        base_size = min(self.portfolio.cash * 0.05, self.risk_limits.max_position_per_market)

        await self._manage_open_risk(market.id, yes_pos, no_pos, yes_price, no_price, snapshot)

        # Depth-weighted entry: limit to what the book can support
        size_cap = min(base_size, snapshot.near_top_depth / 3) if snapshot.near_top_depth else base_size
        features = TimingFeatures(
            timestamp=snapshot.timestamp,
            realized_vol_1m=snapshot.realized_vol_1m,
            depth_change_30s=snapshot.depth_change_30s,
            spread_change=snapshot.spread_change,
            in_macro_window=snapshot.in_macro_window,
        )
        mispricing = max(0.0, 1 - combined_price - self.config.slippage_penalty)

        entry_filters_pass = all(
            [
                cheap_price < 0.35,
                snapshot.realized_vol_1m < self.config.volatility_threshold,
                snapshot.depth_change_30s > self.config.depth_acceleration_threshold,
                mispricing > self.config.mispricing_edge,
                not snapshot.in_macro_window,
                self.timing_classifier.allow_entry(features),
            ]
        )

        if entry_filters_pass and size_cap > 0:
            if combined_price < 0.985 and snapshot.near_top_depth >= 3 * size_cap:
                await self._buy_side(market.id, "YES", size_cap, yes_price)
                await self._buy_side(market.id, "NO", size_cap, no_price)
                self.pending_entries.pop(market.id, None)
                self.performance.log_trade(
                    market_id=market.id,
                    action="HEDGE",
                    size=size_cap,
                    price=combined_price,
                    confidence=0.92,
                    reasoning="Depth-backed hedge under $0.985 with benign microstructure",
                )
            else:
                await self._buy_side(market.id, cheap_side, size_cap, cheap_price)
                self.pending_entries[market.id] = snapshot.timestamp
                self.performance.log_trade(
                    market_id=market.id,
                    action=f"BUY_{cheap_side}",
                    size=size_cap,
                    price=cheap_price,
                    confidence=0.72,
                    reasoning="Bought discounted side after volatility/depth/time filters",
                )

    async def _manage_open_risk(
        self,
        market_id: str,
        yes_pos: Optional[Position],
        no_pos: Optional[Position],
        yes_price: float,
        no_price: float,
        snapshot,
    ) -> None:
        now = datetime.utcnow()
        pending_ts = self.pending_entries.get(market_id)

        # hedge existing single-leg if conditions are right
        combined_price = yes_price + no_price
        if yes_pos and not no_pos:
            if combined_price < 0.985 and snapshot.near_top_depth >= 3 * yes_pos.size and not snapshot.in_macro_window:
                await self._buy_side(market_id, "NO", yes_pos.size, no_price)
                self.performance.log_trade(
                    market_id=market_id,
                    action="HEDGE_NO",
                    size=yes_pos.size,
                    price=no_price,
                    confidence=0.85,
                    reasoning="Added NO hedge with sufficient depth and tight pricing",
                )
                self.pending_entries.pop(market_id, None)
                return
        if no_pos and not yes_pos:
            if combined_price < 0.985 and snapshot.near_top_depth >= 3 * no_pos.size and not snapshot.in_macro_window:
                await self._buy_side(market_id, "YES", no_pos.size, yes_price)
                self.performance.log_trade(
                    market_id=market_id,
                    action="HEDGE_YES",
                    size=no_pos.size,
                    price=yes_price,
                    confidence=0.85,
                    reasoning="Added YES hedge with sufficient depth and tight pricing",
                )
                self.pending_entries.pop(market_id, None)
                return

        # exit criteria for stranded single-leg positions
        if pending_ts:
            waited = (now - pending_ts).total_seconds()
            should_exit = any(
                [
                    waited > self.config.hedge_timeout_seconds,
                    snapshot.realized_vol_1m > self.config.volatility_threshold,
                    snapshot.depth_change_30s < 0,
                    snapshot.spread_change > self.config.spread_widening_limit,
                ]
            )
            if should_exit:
                if yes_pos and not no_pos and yes_price >= yes_pos.average_price:
                    await self.execution.close_position(market_id, "YES", yes_price)
                    self.performance.log_trade(
                        market_id=market_id,
                        action="EXIT_YES",
                        size=yes_pos.size,
                        price=yes_price,
                        confidence=0.55,
                        reasoning="Hedge timeout/volatility/depth warnings triggered",
                    )
                    self.pending_entries.pop(market_id, None)
                elif no_pos and not yes_pos and no_price >= no_pos.average_price:
                    await self.execution.close_position(market_id, "NO", no_price)
                    self.performance.log_trade(
                        market_id=market_id,
                        action="EXIT_NO",
                        size=no_pos.size,
                        price=no_price,
                        confidence=0.55,
                        reasoning="Hedge timeout/volatility/depth warnings triggered",
                    )
                    self.pending_entries.pop(market_id, None)

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
