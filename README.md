# Polymarket Crypto Arbitrage Bot

An opinionated arbitrage bot that focuses on Polymarket's 15-minute "Up or Down"
markets for BTC, ETH, and XRP. The bot supports live trading and demo (simulated)
trading, executes a fixed low-price/hedge strategy, and ships with a lightweight
FastAPI dashboard.

## Features
- **Depth-Weighted Arbitrage Playbook**: Enters the lower-priced outcome first,
  waits for the opposite side to cheapen, then pairs the trade only if the
  combined average cost stays under $1 and the book has enough refreshed depth.
- **Real-Time Scanning**: Filters Polymarket to BTC/ETH/XRP "Up or Down"
  15-minute listings (explicitly matching the titles "Bitcoin/Ethereum/XRP Up or
  Down - 15 minute") and respects configurable rate limits. No synthetic markets
  are injected—only live API data will appear.
- **Microstructure & Timing Filters**: A dedicated scanner tracks depth changes,
  spread shifts, and volatility while a backtestable timing classifier gates
  entries to low-volatility, non-news windows without restricting time-of-day.
- **AI-Gated Decisions**: Every entry/hedge request is reviewed by Ollama-backed
  forecaster/critic/trader agents before orders are sent, and the latest AI
  calls are visible on the dashboard.
- **Risk Guardrails**: Daily loss stops and per-market sizing caps keep exposure
  contained during volatile windows.
- **Market Making & Exit Hooks**: Uses best bid/ask data (when available) and
  provides helpers to size and close positions safely.
- **Performance Analytics**: Logs every trade/hedge for downstream monitoring.
- **Live + Demo Modes**: Point at the production API or Polymarket's demo CLOB
  using environment flags.
- **Dashboard**: Optional FastAPI server that surfaces health, portfolio,
  performance, and live market/snapshot views (HTML + JSON) so you can see what
  the bot is scanning, buying, selling, and its running P&L.

## Project Layout
```
polymarket_bot/
  agents/           # Ollama-driven forecaster/critic/trader agents
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
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where to send Ollama requests |
| `OLLAMA_MODEL` | `gemma3:27b-cloud` | Ollama model name used by the agents |
| `NEWS_API_KEY` | _none_ | Optional Cryptopanic token for news summaries |
| `POLYMARKET_RATE_LIMIT` | `60` | Max Polymarket requests per minute |
| `DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind address |
| `DASHBOARD_PORT` | `8000` | Dashboard port |
| `VOLATILITY_THRESHOLD` | `0.18` | Max 1-minute realized volatility for entries |
| `MISPRICING_EDGE` | `0.04` | Minimum edge after slippage to enter |
| `SLIPPAGE_PENALTY` | `0.01` | Cushion applied when estimating mispricing |
| `HEDGE_TIMEOUT_SECONDS` | `45` | Time to wait for a hedge before flattening |
| `DEPTH_ACCELERATION_THRESHOLD` | `0.05` | Minimum 30s depth growth to enter |
| `SPREAD_WIDENING_LIMIT` | `0.02` | Spread change gate used for exits/timing |

Example `.env` (do **not** commit this file):
```bash
TRADING_MODE=demo
POLL_INTERVAL=20
POLYMARKET_API_KEY=replace-me
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:27b-cloud
```

### Finding eligible markets and their IDs
- The scanner only accepts exact 15-minute crypto titles: `Bitcoin Up or Down - 15 minute`, `Ethereum Up or Down - 15 minute`, and `XRP Up or Down - 15 minute`. If Polymarket publishes variants, adjust the title filter in `polymarket_bot/models.py` and `polymarket_bot/integrations/polymarket.py`.
- To confirm it is hitting real markets, open the dashboard at `/markets` (JSON) or `/` (HTML) and look for the `id` and question fields returned from the live API. Those IDs are the ones used for orders.
- You can also query the Polymarket API directly: `curl "$POLYMARKET_BASE_URL/markets?limit=50" | jq '.[] | {id, question}'` (or replace with the demo base URL). Matching IDs from that feed will appear in the bot once they satisfy the crypto 15-minute filter.

### News source
The optional news enrichment uses the [Cryptopanic](https://cryptopanic.com/developers/api/) API. Supply your token via
`NEWS_API_KEY` to include recent crypto headlines alongside the AI decision prompts. If omitted, the bot falls back to a
technical-only signal.

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
  - `GET /` renders a live HTML view of scan status, markets, positions, trades,
    PnL, and AI approvals.
  - `GET /markets`, `/portfolio`, `/performance`, `/ai`, and `/health` return
    JSON for programmatic monitoring.

### One-off tick
Use this when testing agent decisions without running a persistent loop:
```bash
python -m polymarket_bot.cli
```

## How It Trades
1. **Scan**: Pulls Polymarket markets, filtering to 15-minute BTC/ETH/XRP Up/Down contracts.
2. **Microstructure Check**: Computes 1-minute realized volatility, 30s depth acceleration, spread drift, and book depth around top ticks.
3. **Timing Classifier**: Allows entries only when volatility is muted and the market is outside macro-news windows (no time-of-day restriction).
4. **Enter Cheap Side**: Buys the lower-priced outcome first (with AI approval) only when depth has refreshed and conditions are benign.
5. **Wait for Opposite to Soften**: Tracks the opposite outcome and hedges only after its price falls below the entry reference and the projected combined average price of both sides stays under $1 with sufficient depth.
6. **Exit**: Flatten single legs if hedges fail to appear within the timeout, volatility spikes, depth evaporates, or spreads widen.
7. **Monitor**: Dashboard and logs expose P&L, timing decisions, and all trade/hedge actions.

Example flow: buy the cheaper "Bitcoin Down" leg at $0.25, wait for the market to move and the "Bitcoin Up" leg to slip to $0.45,
then hedge. The combined average cost is $0.70 (well under $1), leaving upside to parity while limiting downside.

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
