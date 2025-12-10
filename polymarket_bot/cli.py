"""Command-line entrypoint for running the Polymarket Bitcoin bot."""
from __future__ import annotations

import argparse
import asyncio

import uvicorn

from polymarket_bot.config import load_config
from polymarket_bot.dashboard import create_app
from polymarket_bot.trading_bot import TradingBot


async def main_async(watch: bool = False, dashboard: bool = False) -> None:
    config = load_config()
    bot = TradingBot(config)

    tasks = []
    if watch:
        tasks.append(asyncio.create_task(bot.run_forever()))
    else:
        tasks.append(asyncio.create_task(bot.tick()))

    if dashboard:
        app = create_app(bot)
        server = uvicorn.Server(
            uvicorn.Config(app, host=config.dashboard_host, port=config.dashboard_port, log_level="info")
        )
        tasks.append(asyncio.create_task(server.serve()))

    await asyncio.gather(*tasks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polymarket crypto arbitrage bot")
    parser.add_argument("--watch", action="store_true", help="Run continuously")
    parser.add_argument("--dashboard", action="store_true", help="Start the FastAPI dashboard")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(watch=args.watch, dashboard=args.dashboard))


if __name__ == "__main__":
    main()
