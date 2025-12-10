"""News ingestion stub to enrich context for the agents."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx


class NewsClient:
    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    async def latest_bitcoin_headlines(self) -> str:
        if not self.api_key:
            return "News API key missing; using technical-only signal."
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://cryptopanic.com/api/v1/posts/",
                    params={"auth_token": self.api_key, "currencies": "BTC"},
                )
                response.raise_for_status()
                data = response.json()
                titles = [item.get("title", "") for item in data.get("results", [])[:5]]
                return " | ".join(titles)
        except Exception:
            return "Unable to fetch news; continuing with trading signal only."
