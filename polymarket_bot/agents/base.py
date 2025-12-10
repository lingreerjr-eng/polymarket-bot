"""Agent interfaces used by the decision engine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from polymarket_bot.models import Critique, DecisionContext, Forecast, TradeDecision


class Agent(ABC):
    name: str

    @abstractmethod
    async def __call__(self, context: DecisionContext) -> Any:  # pragma: no cover - interface
        ...


class ForecasterAgent(Agent):
    name = "forecaster"

    @abstractmethod
    async def __call__(self, context: DecisionContext) -> Forecast:
        ...


class CriticAgent(Agent):
    name = "critic"

    @abstractmethod
    async def __call__(self, context: DecisionContext, forecast: Forecast) -> Critique:
        ...


class TraderAgent(Agent):
    name = "trader"

    @abstractmethod
    async def __call__(
        self, context: DecisionContext, forecast: Forecast, critique: Critique
    ) -> TradeDecision:
        ...
