# Polymarket Crypto Arbitrage Bot

An opinionated arbitrage bot that focuses on Polymarket's 15-minute "Up or Down"
markets for BTC, ETH, and XRP. The bot supports live trading and demo (simulated)
trading, executes a fixed low-price/hedge strategy, and ships with a lightweight
FastAPI dashboard.

## Features
- **Fixed Arbitrage Playbook**: Buys whichever side drops below $0.35, hedges
  both sides when the combined average stays under $0.99, and exits flat if no
  hedge is available.
- **Real-Time Scanning**: Filters Polymarket to BTC/ETH/XRP "Up or Down"
  15-minute listings and respects configurable rate limits.
- **Risk Guardrails**: Daily loss stops and per-market sizing caps keep exposure
  contained during volatile windows.
- **Market Making & Exit Hooks**: Uses best bid/ask data (when available) and
  provides helpers to size and close positions safely.
- **Performance Analytics**: Logs every trade/hedge for downstream monitoring.
- **Live + Demo Modes**: Point at the production API or Polymarket's demo CLOB
  using environment flags.
- **Dashboard**: Optional FastAPI server that surfaces health, portfolio, and
  performance endpoints for external monitoring.

## Project Layout
```
polymarket_bot/
  agents/           # Legacy AI agents (unused by the arbitrage strategy)
  integrations/     # Polymarket API client, optional AI/news connectors
  services/         # Portfolio math, execution, analytics, scanners
  dashboard.py      # FastAPI application factory
  trading_bot.py    # Orchestration loop
  cli.py            # Command-line entry
requirements.txt
```

## Security
- **Never commit API keys or private keys.** Use environment variables only.
- Rotate keys regularly and scope them to the minimum necessary permissions.
- Respect Polymarket API rate limits to avoid bans and unstable behavior.

## Prerequisites
- Python 3.10+
- Polymarket API credentials for live trading (optional for demo mode).

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
All runtime configuration is driven by environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `TRADING_MODE` | `demo` | `live` for production CLOB, `demo` for sandbox |
| `POLYMARKET_API_KEY` | _none_ | Required for authenticated live trading |
| `POLYMARKET_BASE_URL` | `https://clob.polymarket.com` | Live API base |
| `POLYMARKET_DEMO_URL` | `https://clob.demo.polymarket.com` | Demo API base |
| `POLL_INTERVAL` | `15` | Seconds between scans |
| `MAX_DAILY_LOSS` | `500` | Max daily drawdown before pausing |
| `MAX_POSITION_PER_MARKET` | `250` | Absolute USD cap per market |
| `RISK_FREE_RATE` | `0.02` | Used by sizing clamps |
| `POLYMARKET_RATE_LIMIT` | `60` | Max Polymarket requests per minute |
| `DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind address |
| `DASHBOARD_PORT` | `8000` | Dashboard port |

Example `.env` (do **not** commit this file):
```bash
TRADING_MODE=demo
POLL_INTERVAL=20
POLYMARKET_API_KEY=replace-me
```

## Running the Bot
### Demo (sandbox) mode
```bash
TRADING_MODE=demo python -m polymarket_bot.cli --watch --dashboard
```

### Live mode (requires credentials)
```bash
TRADING_MODE=live POLYMARKET_API_KEY=your-key-here python -m polymarket_bot.cli --watch --dashboard
```

- `--watch` keeps the scanner/strategy loop running continuously.
- `--dashboard` starts the FastAPI dashboard at `http://localhost:8000`.

### One-off tick
Use this when testing agent decisions without running a persistent loop:
```bash
python -m polymarket_bot.cli
```

## How It Trades
1. **Scan**: Pulls Polymarket markets, filtering to 15-minute BTC/ETH/XRP Up/Down contracts.
2. **Detect Discount**: Watches for either side (YES/NO) to fall below $0.35.
3. **Hedge**: If the combined YES+NO average stays under $0.99, buys both sides to lock an arbitrage spread.
4. **Accumulate**: If the opposite side is too expensive to hedge, keeps accumulating the discounted side while prices are low.
5. **Exit**: When no hedge is available and the held side returns to break-even, closes out to avoid losses.
6. **Monitor**: Dashboard and logs expose P&L and all trade/hedge actions.

## Market-Making & Exit Controls
- Uses best bid/ask quotes when available to improve execution quality.
- Dual-side positions are tracked separately (YES/NO) so hedges can be opened and
  closed independently.
- Dynamic exit helpers are available in `ExecutionService.close_position` for manual or automated unwinds.

## Notes on Safety & Costs
- Respect the `POLYMARKET_RATE_LIMIT` to avoid throttling.
- Treat demo mode as a rehearsal: confirm portfolio sizing and loss limits before
  flipping `TRADING_MODE=live`.

## Extending
- Adjust the entry/hedge thresholds in `TradingBot._trade_market` to reflect your
  preferred arbitrage windows.
- Add charting or websockets to the FastAPI dashboard if you need richer monitoring.

## Disclaimer
This repository is for educational purposes. Trading on prediction markets carries
risk. Run the bot in demo mode first, and use conservative limits when deploying
in production. You are responsible for API key management and compliance with
Polymarket's terms of service.
