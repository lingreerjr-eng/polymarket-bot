"""Forecaster agent estimates true probability using markets and news."""
from __future__ import annotations

import json
from typing import Optional

from polymarket_bot.agents.base import ForecasterAgent
from polymarket_bot.integrations.ai_client import AIClient
from polymarket_bot.models import DecisionContext, Forecast


class AIForecaster(ForecasterAgent):
    def __init__(self, ai_client: AIClient) -> None:
        self.ai_client = ai_client

    async def __call__(self, context: DecisionContext) -> Forecast:
        prompt = self._build_prompt(context)
        response = await self.ai_client.complete(prompt)
        data = self._parse_response(response.text)
        return Forecast(
            probability_yes=float(data.get("probability_yes", 0.5)),
            reasoning=data.get("reasoning", "AI forecast unavailable"),
            confidence=float(data.get("confidence", 0.2)),
        )

    def _build_prompt(self, context: DecisionContext) -> str:
        return (
            "You are the Forecaster agent. Estimate the true probability that the"
            " Bitcoin price will finish 'Yes' for the given 15 minute Polymarket"
            " question. Provide JSON with probability_yes (0-1), confidence (0-1),"
            " and reasoning. Market question: "
            f"{context.market.question}. Last news: {context.news}"
        )

    def _parse_response(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "probability_yes": 0.5,
                "confidence": 0.1,
                "reasoning": text.strip()[:200],
            }
