"""Lightweight Ollama/OpenAI compatible client used by the agents."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional

import httpx


@dataclass
class AIResponse:
    text: str
    model: str
    cost: float = 0.0


class AIClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, prompt: str, temperature: float = 0.2) -> AIResponse:
        payload: Dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate", json=payload
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response") or data.get("message", "")
                return AIResponse(text=text, model=self.model)
        except Exception:
            fallback = self._fallback_response(prompt)
            return AIResponse(text=fallback, model=f"offline-{self.model}")

    def _fallback_response(self, prompt: str) -> str:
        summary_prompt = prompt.lower()
        if "probability" in summary_prompt:
            return json.dumps(
                {
                    "probability_yes": 0.52,
                    "confidence": 0.35,
                    "reasoning": "Fallback heuristic: mild bullish bias on BTC short term.",
                }
            )
        if "concern" in summary_prompt:
            return json.dumps(
                {
                    "approval": True,
                    "concerns": [
                        "Using cached forecast due to offline AI client",
                        "Ensure manual review before executing large orders",
                    ],
                }
            )
        return json.dumps(
            {
                "action": "SKIP",
                "size": 0,
                "reasoning": "Offline mode: insufficient signal to trade.",
                "confidence": 0.1,
            }
        )
