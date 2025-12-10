"""Main orchestration loop for the Polymarket crypto arbitrage bot."""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple

from polymarket_bot.agents.critic import AICritic
from polymarket_bot.agents.forecaster import AIForecaster
from polymarket_bot.agents.trader import AITrader
from polymarket_bot.config import BotConfig
from polymarket_bot.integrations.ai_client import AIClient
from polymarket_bot.integrations.news import NewsClient
from polymarket_bot.integrations.polymarket import PolymarketClient
from polymarket_bot.models import (
    Critique,
    DecisionContext,
    Forecast,
    PortfolioState,
    RiskLimits,
    Position,
    TimingFeatures,
    TradeDecision,
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
        self.portfolio = PortfolioState(cash=0.0)
        self.risk_limits = RiskLimits(
            max_daily_loss=config.max_daily_loss,
            max_position_per_market=config.max_position_per_market,
            risk_free_rate=config.risk_free_rate,
        )
        self.performance = PerformanceTracker()
        self.ai_client = AIClient(config.ollama_base_url, config.ollama_model)
        self.forecaster = AIForecaster(self.ai_client)
        self.critic = AICritic(self.ai_client)
        self.trader_agent = AITrader(self.ai_client)
        self.news_client = NewsClient(config.news_api_key)
        self.polymarket_client = PolymarketClient(
            base_url=config.api_url,
            discovery_url=config.polymarket_gamma_url,
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
        self.pending_entries: Dict[str, Dict[str, object]] = {}
        self.last_all_markets = []
        self.last_eligible_markets = []
        self.last_markets = []
        self.last_snapshots: Dict[str, object] = {}
        self.last_ai_notes: Dict[str, object] = {}
        self.last_scan_at: Optional[datetime] = None
        self.last_status: str = "idle"
        self.selected_market_ids: set[str] = set()
        self._portfolio_bootstrapped: bool = False
        self._unrealized_marks: Dict[str, float] = {}

    async def run_forever(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(self.config.poll_interval)

    async def tick(self) -> None:
        await self._bootstrap_portfolio()
        if portfolio.enforce_daily_loss(self.portfolio, self.risk_limits):
            print("Daily loss limit reached - pausing trading")
            return

        eligible_markets = await self.market_scanner.scan()
        self.last_all_markets = list(self.market_scanner.last_all)
        self.last_eligible_markets = eligible_markets
        self.last_markets = self.last_all_markets
        self.last_scan_at = datetime.utcnow()
        self.last_status = (
            f"Scanned {self.market_scanner.last_total} markets, "
            f"{self.market_scanner.last_filtered} eligible crypto"
        )

        if not eligible_markets:
            print("No qualifying crypto 15m markets found")
            self.last_status = "No qualifying crypto 15m markets found"
            return

        trade_targets = (
            [m for m in eligible_markets if m.id in self.selected_market_ids]
            if self.selected_market_ids
            else eligible_markets
        )
        if self.selected_market_ids and not trade_targets:
            self.last_status += " | Waiting for selected eligible markets"
            return

        for market in trade_targets:
            await self._trade_market(market)

        # Refresh unrealized PnL from the latest marks
        self.portfolio.unrealized_pnl = sum(self._unrealized_marks.values())

    async def _trade_market(self, market) -> None:
        snapshot = await self.microstructure.snapshot(market)
        yes_price = min(snapshot.best_ask, market.outcome_yes_price)
        no_price = min(snapshot.best_bid, market.outcome_no_price)
        combined_price = yes_price + no_price

        yes_pos, no_pos = self._positions_for_market(market.id)
        cheap_side, cheap_price = ("YES", yes_price) if yes_price < no_price else ("NO", no_price)
        other_side_price = no_price if cheap_side == "YES" else yes_price
        base_size = min(self.portfolio.cash * 0.05, self.risk_limits.max_position_per_market)

        await self._manage_open_risk(market.id, yes_pos, no_pos, yes_price, no_price, snapshot)

        # Skip fresh entries if we already hold one leg; hedge logic is handled separately
        yes_pos, no_pos = self._positions_for_market(market.id)
        if yes_pos or no_pos:
            self.last_snapshots[market.id] = snapshot
            self._mark_unrealized(market.id, yes_price, no_price)
            return

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
                cheap_price < other_side_price,
                snapshot.realized_vol_1m < self.config.volatility_threshold,
                snapshot.depth_change_30s > self.config.depth_acceleration_threshold,
                not snapshot.in_macro_window,
                self.timing_classifier.allow_entry(features),
            ]
        )

        if entry_filters_pass and size_cap > 0:
            decision = await self._ai_gate_trade(
                market=market,
                cheap_side=cheap_side,
                size_cap=size_cap,
                snapshot=snapshot,
                mispricing=mispricing,
            )
            ai_action = decision.action.upper() if decision else "BUY"
            ai_size = decision.size if decision else size_cap
            ai_size = min(size_cap, ai_size if ai_size > 0 else size_cap)
            if ai_action not in {"BUY", cheap_side, f"BUY_{cheap_side}", "HEDGE"}:
                self.performance.log_trade(
                    market_id=market.id,
                    action="AI_SKIP",
                    size=0,
                    price=cheap_price,
                    confidence=decision.confidence if decision else 0.0,
                    reasoning=(
                        decision.reasoning
                        if decision
                        else "AI gate declined entry despite microstructure pass"
                    ),
                )
                return

            await self._buy_side(market.id, cheap_side, ai_size, cheap_price)
            self.pending_entries[market.id] = {
                "timestamp": snapshot.timestamp,
                "initial_other_price": other_side_price,
                "entry_side": cheap_side,
                "entry_price": cheap_price,
                "planned_size": ai_size,
            }
            self.performance.log_trade(
                market_id=market.id,
                action=f"BUY_{cheap_side}",
                size=ai_size,
                price=cheap_price,
                confidence=decision.confidence if decision else 0.72,
                reasoning=(
                    decision.reasoning
                    if decision
                    else "Bought cheaper outcome; waiting for opposite to cheapen before hedging"
                ),
            )

        self.last_snapshots[market.id] = snapshot
        self._mark_unrealized(market.id, yes_price, no_price)

    async def _ai_gate_trade(
        self,
        *,
        market,
        cheap_side: str,
        size_cap: float,
        snapshot,
        mispricing: float,
    ) -> Optional[TradeDecision]:
        news_summary = await self.news_client.latest_bitcoin_headlines()
        context = DecisionContext(market=market, portfolio=self.portfolio, news=news_summary)
        forecast: Forecast = await self.forecaster(context)
        critique: Critique = await self.critic(context, forecast)
        decision: TradeDecision = await self.trader_agent(context, forecast, critique)
        self.last_ai_notes[market.id] = {
            "forecast": forecast,
            "critique": critique,
            "decision": decision,
            "mispricing": mispricing,
            "snapshot": snapshot,
            "cheap_side": cheap_side,
            "size_cap": size_cap,
        }
        return decision

    async def _bootstrap_portfolio(self) -> None:
        """Fetch balances/positions from Polymarket once to seed the portfolio state."""

        if self._portfolio_bootstrapped:
            return
        snapshot = await self.polymarket_client.account_snapshot()
        if not snapshot:
            self._portfolio_bootstrapped = True
            return

        try:
            self.portfolio.cash = float(snapshot.get("cash", self.portfolio.cash))
        except Exception:
            pass
        try:
            self.portfolio.realized_pnl = float(snapshot.get("realized_pnl", self.portfolio.realized_pnl))
            self.portfolio.unrealized_pnl = float(snapshot.get("unrealized_pnl", self.portfolio.unrealized_pnl))
        except Exception:
            pass

        positions = snapshot.get("positions") or []
        if isinstance(positions, list):
            for pos in positions:
                if not isinstance(pos, dict):
                    continue
                market_id = str(pos.get("market_id") or pos.get("id") or "")
                side = str(pos.get("side") or "").upper() or "YES"
                try:
                    size = float(pos.get("size") or 0.0)
                except Exception:
                    size = 0.0
                try:
                    avg = float(pos.get("average_price") or pos.get("avg_price") or 0.0)
                except Exception:
                    avg = 0.0
                key = f"{market_id}:{side}"
                self.portfolio.positions[key] = Position(
                    market_id=market_id,
                    side=side,
                    size=size,
                    average_price=avg,
                )

        self._portfolio_bootstrapped = True

    def _mark_unrealized(self, market_id: str, yes_price: float, no_price: float) -> None:
        yes_pos, no_pos = self._positions_for_market(market_id)
        unrealized = 0.0
        if yes_pos:
            unrealized += (yes_price - yes_pos.average_price) * yes_pos.size
        if no_pos:
            unrealized += (no_price - no_pos.average_price) * no_pos.size
        if yes_pos or no_pos:
            self._unrealized_marks[market_id] = unrealized
        elif market_id in self._unrealized_marks:
            self._unrealized_marks.pop(market_id, None)

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
        pending = self.pending_entries.get(market_id)
        pending_ts = pending.get("timestamp") if isinstance(pending, dict) else pending

        # hedge existing single-leg if conditions are right
        combined_price = yes_price + no_price
        if yes_pos and not no_pos:
            trigger_price = pending.get("initial_other_price") if isinstance(pending, dict) else None
            planned_size = pending.get("planned_size") if isinstance(pending, dict) else yes_pos.size
            projected_cost = self._combined_average(
                yes_pos,
                no_pos,
                add_yes=0,
                add_no=planned_size,
                price_yes=yes_price,
                price_no=no_price,
            )
            if (
                trigger_price is not None
                and no_price < trigger_price
                and projected_cost < 0.99
                and snapshot.near_top_depth >= 3 * planned_size
                and not snapshot.in_macro_window
            ):
                await self._buy_side(market_id, "NO", planned_size, no_price)
                self.performance.log_trade(
                    market_id=market_id,
                    action="HEDGE_NO",
                    size=planned_size,
                    price=no_price,
                    confidence=0.88,
                    reasoning="Opposite outcome cheapened; paired hedge keeps combined cost < $1",
                )
                self.pending_entries.pop(market_id, None)
                return
        if no_pos and not yes_pos:
            trigger_price = pending.get("initial_other_price") if isinstance(pending, dict) else None
            planned_size = pending.get("planned_size") if isinstance(pending, dict) else no_pos.size
            projected_cost = self._combined_average(
                yes_pos,
                no_pos,
                add_yes=planned_size,
                add_no=0,
                price_yes=yes_price,
                price_no=no_price,
            )
            if (
                trigger_price is not None
                and yes_price < trigger_price
                and projected_cost < 0.99
                and snapshot.near_top_depth >= 3 * planned_size
                and not snapshot.in_macro_window
            ):
                await self._buy_side(market_id, "YES", planned_size, yes_price)
                self.performance.log_trade(
                    market_id=market_id,
                    action="HEDGE_YES",
                    size=planned_size,
                    price=yes_price,
                    confidence=0.88,
                    reasoning="Opposite outcome cheapened; paired hedge keeps combined cost < $1",
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

    def set_market_selected(self, market_id: str, selected: bool) -> None:
        if selected:
            self.selected_market_ids = {market_id}
        else:
            self.selected_market_ids.discard(market_id)


async def run_bot(config: BotConfig) -> None:
    bot = TradingBot(config)
    await bot.tick()


async def run_bot_forever(config: BotConfig) -> None:
    bot = TradingBot(config)
    await bot.run_forever()
