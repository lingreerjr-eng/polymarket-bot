"""Minimal FastAPI dashboard to expose live metrics."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from polymarket_bot.trading_bot import TradingBot


def _jsonify(item: Any) -> Any:
    if isinstance(item, datetime):
        return item.isoformat()
    if hasattr(item, "__dict__"):
        return {k: _jsonify(v) for k, v in item.__dict__.items()}
    if isinstance(item, list):
        return [_jsonify(v) for v in item]
    if isinstance(item, dict):
        return {k: _jsonify(v) for k, v in item.items()}
    return item


def create_app(bot: TradingBot) -> FastAPI:
    app = FastAPI(title="Polymarket Crypto Bot Dashboard")

    @app.get("/", response_class=HTMLResponse)
    async def home() -> str:
        return """
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
          <meta charset=\"UTF-8\" />
          <title>Polymarket Crypto Dashboard</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #0e1117; color: #e8eaed; }
            h1 { margin-bottom: 6px; }
            section { margin-bottom: 22px; padding: 12px; background: #161b22; border-radius: 8px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #2c313a; padding: 6px 8px; text-align: left; }
            th { background: #202632; }
            .muted { color: #9ca3af; font-size: 12px; }
          </style>
        </head>
        <body>
          <h1>Polymarket Crypto Dashboard</h1>
          <div class=\"muted\">Live scan status for BTC/ETH/XRP 15m markets. Check a box to allow trading.</div>
          <section>
            <h3>Status</h3>
            <div id=\"status\">Loading...</div>
          </section>
          <section>
            <h3>Markets</h3>
            <div id=\"markets\">Loading...</div>
          </section>
          <section>
            <h3>Portfolio</h3>
            <div id=\"portfolio\">Loading...</div>
          </section>
          <section>
            <h3>Recent Trades</h3>
            <div id=\"trades\">Loading...</div>
          </section>
          <section>
            <h3>AI Decisions</h3>
            <div id=\"ai\">Loading...</div>
          </section>
          <script>
            async function load() {
              const [health, markets, portfolio, performance, ai] = await Promise.all([
                fetch('/health').then(r => r.json()),
                fetch('/markets').then(r => r.json()),
                fetch('/portfolio').then(r => r.json()),
                fetch('/performance').then(r => r.json()),
                fetch('/ai').then(r => r.json()),
              ]);
              document.getElementById('status').innerText = `${health.status} | mode=${health.mode} | ${health.message || ''}`;
              document.getElementById('markets').innerHTML = renderMarkets(markets);
              document.getElementById('portfolio').innerHTML = renderPortfolio(portfolio);
              document.getElementById('trades').innerHTML = renderTrades(performance.trades);
              document.getElementById('ai').innerHTML = renderAI(ai);
            }
            function renderMarkets(data) {
              if (!data.markets || data.markets.length === 0) return 'No markets scanned yet.';
              const selected = new Set(data.selected_ids || []);
              const eligible = new Set(data.eligible_ids || []);
              const rows = data.markets.map(m => {
                const snap = data.snapshots[m.id] || {};
                const checked = selected.has(m.id) ? 'checked' : '';
                const disabled = eligible.has(m.id) ? '' : 'disabled';
                const eligibleFlag = eligible.has(m.id) ? '✅' : '—';
                return `<tr>
                  <td><input type="checkbox" ${checked} ${disabled} onchange="toggleSelect('${m.id}', this.checked)"></td>
                  <td>${m.id}</td>
                  <td>${m.question}</td>
                  <td>${m.outcome_yes_price.toFixed(3)}</td>
                  <td>${m.outcome_no_price.toFixed(3)}</td>
                  <td>${snap.best_bid ?? '-'}</td>
                  <td>${snap.best_ask ?? '-'}</td>
                  <td>${(snap.realized_vol_1m ?? 0).toFixed(4)}</td>
                  <td>${(snap.depth_change_30s ?? 0).toFixed(3)}</td>
                  <td>${eligibleFlag}</td>
                </tr>`;
              }).join('');
              const scanned = data.last_scan_at ? `<div class="muted">Last scan: ${data.last_scan_at}</div>` : '';
              return `${scanned}<table><thead><tr><th>Trade?</th><th>ID</th><th>Question</th><th>Yes</th><th>No</th><th>Bid</th><th>Ask</th><th>1m Vol</th><th>Depth Δ30s</th><th>Crypto 15m</th></tr></thead><tbody>${rows}</tbody></table>`;
            }
            async function toggleSelect(marketId, selected) {
              await fetch('/markets/select', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ market_id: marketId, selected }) });
              await load();
            }
            function renderPortfolio(p) {
              const positions = Object.values(p.positions || {});
              const rows = positions.map(pos => `<tr><td>${pos.market_id}</td><td>${pos.side}</td><td>${pos.size}</td><td>${pos.average_price.toFixed(3)}</td></tr>`).join('');
              return `<div>Cash: $${p.cash.toFixed(2)} | Realized PnL: ${p.realized_pnl.toFixed(2)} | Unrealized PnL: ${p.unrealized_pnl.toFixed(2)}</div>` +
                     `<table><thead><tr><th>Market</th><th>Side</th><th>Size</th><th>Avg Price</th></tr></thead><tbody>${rows || '<tr><td colspan="4">No open positions</td></tr>'}</tbody></table>`;
            }
            function renderTrades(trades) {
              if (!trades || trades.length === 0) return 'No trades yet.';
              const rows = trades.slice(-20).reverse().map(t => `<tr><td>${t.timestamp}</td><td>${t.market_id}</td><td>${t.action}</td><td>${t.size}</td><td>${t.price.toFixed(3)}</td><td>${t.reasoning}</td></tr>`).join('');
              return `<table><thead><tr><th>Time</th><th>Market</th><th>Action</th><th>Size</th><th>Price</th><th>Notes</th></tr></thead><tbody>${rows}</tbody></table>`;
            }
            function renderAI(ai) {
              if (!ai || !ai.entries || Object.keys(ai.entries).length === 0) return 'No AI decisions yet.';
              const rows = Object.entries(ai.entries).map(([marketId, data]) => {
                const decision = data.decision || {};
                const forecast = data.forecast || {};
                return `<tr><td>${marketId}</td><td>${(forecast.probability_yes ?? 0.5).toFixed(3)}</td><td>${decision.action || '-'}</td><td>${decision.size || '-'}</td><td>${decision.reasoning || ''}</td></tr>`;
              }).join('');
              return `<div class=\"muted\">Last AI-gated calls sent to Ollama</div><table><thead><tr><th>Market</th><th>Prob Yes</th><th>Action</th><th>Size</th><th>Reasoning</th></tr></thead><tbody>${rows}</tbody></table>`;
            }
            load(); setInterval(load, 4000);
          </script>
        </body></html>
        """

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "mode": bot.config.trading_mode, "message": bot.last_status}

    @app.get("/portfolio")
    async def portfolio() -> dict:
        return {
            "cash": bot.portfolio.cash,
            "positions": {k: _jsonify(v) for k, v in bot.portfolio.positions.items()},
            "realized_pnl": bot.portfolio.realized_pnl,
            "unrealized_pnl": bot.portfolio.unrealized_pnl,
        }

    @app.get("/markets")
    async def markets() -> dict:
        return {
            "markets": [_jsonify(m) for m in bot.last_markets],
            "snapshots": {k: _jsonify(v) for k, v in bot.last_snapshots.items()},
            "last_scan_at": _jsonify(bot.last_scan_at),
            "eligible_ids": [m.id for m in bot.last_eligible_markets],
            "selected_ids": sorted(bot.selected_market_ids),
        }

    @app.post("/markets/select")
    async def select_market(payload: dict) -> dict:
        market_id = payload.get("market_id")
        selected = bool(payload.get("selected", True))
        if market_id:
            bot.set_market_selected(market_id, selected)
        return {
            "selected_ids": sorted(bot.selected_market_ids),
            "eligible_ids": [m.id for m in bot.last_eligible_markets],
        }

    @app.get("/performance")
    async def performance() -> dict:
        return {
            "trades": [_jsonify(t) for t in bot.performance.trades],
            "win_rate": bot.performance.win_rate(),
            "total_volume": bot.performance.total_volume(),
        }

    @app.get("/ai")
    async def ai_decisions() -> dict:
        return {"entries": {k: _jsonify(v) for k, v in bot.last_ai_notes.items()}}

    return app
