"""Critic agent checks the forecast for missing context or flaws."""
from __future__ import annotations

import json
from polymarket_bot.agents.base import CriticAgent
from polymarket_bot.integrations.ai_client import AIClient
from polymarket_bot.models import Critique, DecisionContext, Forecast


class AICritic(CriticAgent):
    def __init__(self, ai_client: AIClient) -> None:
        self.ai_client = ai_client

    async def __call__(self, context: DecisionContext, forecast: Forecast) -> Critique:
        prompt = self._build_prompt(context, forecast)
        response = await self.ai_client.complete(prompt)
        data = self._parse_response(response.text)
        return Critique(
            concerns=data.get("concerns", []),
            approval=bool(data.get("approval", True)),
        )

    def _build_prompt(self, context: DecisionContext, forecast: Forecast) -> str:
        return (
            "You are the Critic agent. Review the forecast for potential blind spots"
            " such as liquidity, news events, correlation, or timing risk."
            " Provide JSON with approval (true/false) and a list of concerns."
            f" Market: {context.market.question}. Forecast: {forecast}"
        )

    def _parse_response(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"approval": True, "concerns": [text.strip()[:120]]}
