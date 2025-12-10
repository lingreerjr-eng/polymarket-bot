"""Trader agent: combines signals and issues the trade decision."""
from __future__ import annotations

import json
from typing import Optional

from polymarket_bot.agents.base import TraderAgent
from polymarket_bot.integrations.ai_client import AIClient
from polymarket_bot.models import Critique, DecisionContext, Forecast, TradeDecision
from polymarket_bot.services import portfolio


class AITrader(TraderAgent):
    def __init__(self, ai_client: AIClient) -> None:
        self.ai_client = ai_client

    async def __call__(
        self, context: DecisionContext, forecast: Forecast, critique: Critique
    ) -> TradeDecision:
        prompt = self._build_prompt(context, forecast, critique)
        response = await self.ai_client.complete(prompt)
        parsed = self._parse_response(response.text)
        return TradeDecision(
            action=parsed.get("action", "SKIP"),
            probability_yes=forecast.probability_yes,
            size=float(parsed.get("size", 0.0)),
            reasoning=parsed.get("reasoning", "No reasoning returned"),
            confidence=float(parsed.get("confidence", forecast.confidence)),
        )

    def _build_prompt(self, context: DecisionContext, forecast: Forecast, critique: Critique) -> str:
        return (
            "You are the Trader agent. Use the forecast and critique to decide"
            " whether to BUY, SELL, or SKIP this Polymarket Bitcoin 15m contract."
            " Use Kelly sizing and risk controls: size must be between 0 and"
            f" {context.portfolio.cash:.2f}. Concerns: {critique.concerns}."
            " Respond with JSON: action, size, reasoning, confidence (0-1)."
            f" Forecast: {forecast}. Current portfolio: {context.portfolio.total_value():.2f} USD"
        )

    def _parse_response(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "action": "SKIP",
                "size": 0.0,
                "reasoning": text.strip()[:200],
                "confidence": 0.1,
            }


def kelly_size(prob_yes: float, market_price: float, bankroll: float) -> float:
    edge = prob_yes - market_price
    return portfolio.kelly_position(edge=edge, price=market_price, bankroll=bankroll)
