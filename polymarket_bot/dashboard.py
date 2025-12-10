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
          <title>Polymarket // CYBERNETIC TRADING TERMINAL</title>
          <style>
            :root {
              --color-bg: #0b0f15;
              --color-panel: #131a25;
              --color-accent: #00e0ff;
              --color-pos: #00ff9d;
              --color-neg: #ff2a6d;
              --color-text: #e0f7ff;
              --color-muted: #5c6b7f;
              --font-mono: 'Space Mono', 'Courier New', monospace;
              --glow-blue: 0 0 10px rgba(0, 224, 255, 0.4);
              --glow-green: 0 0 10px rgba(0, 255, 157, 0.4);
              --mouse-x: 50%;
              --mouse-y: 50%;
              --globe-rot-x: 0deg;
              --globe-rot-y: 0deg;
            }
            body {
              margin: 0;
              background: var(--color-bg);
              color: var(--color-text);
              font-family: var(--font-mono);
              overflow-x: hidden;
              min-height: 100vh;
              cursor: crosshair;
            }
            .cyber-grid {
              position: fixed;
              inset: 0;
              z-index: -2;
              opacity: 0.25;
              background:
                linear-gradient(transparent 95%, var(--color-accent) 95%),
                linear-gradient(90deg, transparent 95%, var(--color-accent) 95%);
              background-size: 40px 40px;
              animation: grid-scroll 20s linear infinite;
              mask-image: radial-gradient(circle 300px at var(--mouse-x) var(--mouse-y), black, transparent);
              -webkit-mask-image: radial-gradient(circle 300px at var(--mouse-x) var(--mouse-y), black, transparent);
            }
            @keyframes grid-scroll {
              0% { transform: perspective(500px) rotateX(10deg) translateY(0); }
              100% { transform: perspective(500px) rotateX(10deg) translateY(40px); }
            }
            .globe-wrapper { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 0; height: 0; z-index: -1; perspective: 1000px; pointer-events: none; }
            .globe-pivot { position: absolute; transform-style: preserve-3d; transform: rotateX(var(--globe-rot-x)) rotateY(var(--globe-rot-y)); transition: transform 0.1s linear; }
            .cube { position: absolute; width: 12px; height: 12px; background: rgba(0, 224, 255, 0.2); border: 1px solid var(--color-accent); box-shadow: 0 0 4px var(--color-accent); pointer-events: auto; transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
            .cube:hover { background: var(--color-pos); border-color: #fff; box-shadow: 0 0 15px var(--color-pos); transform: scale(3) translateZ(50px) !important; z-index: 1000; }
            .container { max-width: 1600px; margin: 0 auto; padding: 20px; display: grid; grid-template-columns: 3fr 1fr; gap: 20px; position: relative; z-index: 10; }
            h1 { grid-column: 1 / -1; text-transform: uppercase; letter-spacing: 2px; text-shadow: var(--glow-blue); border-bottom: 2px solid var(--color-accent); padding-bottom: 10px; margin-bottom: 5px; }
            .subtitle { grid-column: 1 / -1; color: var(--color-muted); margin-bottom: 20px; font-size: 0.9em; }
            section { background: rgba(19, 26, 37, 0.85); border: 1px solid rgba(0, 224, 255, 0.2); border-radius: 4px; padding: 15px; backdrop-filter: blur(5px); box-shadow: 0 0 20px rgba(0,0,0,0.5); }
            section:hover { border-color: var(--color-accent); box-shadow: var(--glow-blue); }
            h3 { margin-top: 0; color: var(--color-pos); text-transform: uppercase; font-size: 0.9rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; letter-spacing: 1px; }
            table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
            th { text-align: left; color: var(--color-muted); padding: 8px; font-weight: normal; }
            td { padding: 8px; border-top: 1px solid rgba(255,255,255,0.05); }
            tr:hover td { background: rgba(0, 224, 255, 0.1); }
            input[type=\"checkbox\"] { accent-color: var(--color-accent); cursor: pointer; width: 16px; height: 16px; }
            .pos { color: var(--color-pos); }
            .neg { color: var(--color-neg); }
            .accent { color: var(--color-accent); }
            .muted { color: var(--color-muted); font-size: 0.8em; }
            .status-box { font-weight: bold; padding: 10px; background: rgba(0,0,0,0.3); border-left: 3px solid var(--color-accent); }
            .search-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
            .search-row input { flex: 1; padding: 8px; background: #0f141d; border: 1px solid #2c394b; color: var(--color-text); border-radius: 4px; }
          </style>
          <link href=\"https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap\" rel=\"stylesheet\">
        </head>
        <body>
          <div class=\"cyber-grid\"></div>
          <div class=\"globe-wrapper\"><div class=\"globe-pivot\" id=\"globe\"></div></div>
          <div class=\"container\">
            <h1>Polymarket // Crypto Dashboard</h1>
            <div class=\"subtitle\">Live neural link established. BTC/ETH/XRP 15m Markets. [CHECK ONE BOX TO ENABLE TRADING]</div>
            <div style=\"display: flex; flex-direction: column; gap: 20px;\">
              <section>
                <h3>Active Markets Scan</h3>
                <div id=\"markets\"><div class=\"muted\">Initializing market connection...</div></div>
              </section>
              <section>
                <h3>AI Neural Engine Decisions</h3>
                <div id=\"ai\"><div class=\"muted\">Waiting for inference...</div></div>
              </section>
              <section>
                <h3>Execution Log</h3>
                <div id=\"trades\"><div class=\"muted\">No trades recorded.</div></div>
              </section>
            </div>
            <div style=\"display: flex; flex-direction: column; gap: 20px;\">
              <section>
                <h3>System Status</h3>
                <div id=\"status\" class=\"status-box\">Connecting...</div>
              </section>
              <section>
                <h3>Portfolio Metrics</h3>
                <div id=\"portfolio\">Loading asset data...</div>
              </section>
            </div>
          </div>
          <script>
            const globe = document.getElementById('globe');
            const root = document.documentElement;
            let lastMarkets = { markets: [] };
            let marketSearch = '';
            document.addEventListener('mousemove', (e) => {
              root.style.setProperty('--mouse-x', e.clientX + 'px');
              root.style.setProperty('--mouse-y', e.clientY + 'px');
              const rotX = -((e.clientY / window.innerHeight) - 0.5) * 30;
              const rotY = ((e.clientX / window.innerWidth) - 0.5) * 30;
              root.style.setProperty('--globe-rot-x', rotX + 'deg');
              root.style.setProperty('--globe-rot-y', rotY + 'deg');
            });
            (function initGlobe() {
              const count = 100, radius = 200;
              for (let i = 0; i < count; i++) {
                const div = document.createElement('div');
                div.className = 'cube';
                const phi = Math.acos(1 - 2 * (i + 0.5) / count);
                const theta = Math.PI * (1 + Math.sqrt(5)) * i;
                const x = radius * Math.sin(phi) * Math.cos(theta);
                const y = radius * Math.sin(phi) * Math.sin(theta);
                const z = radius * Math.cos(phi);
                div.style.transform = `translate3d(${x}px, ${y}px, ${z}px) lookAt(0,0,0)`;
                globe.appendChild(div);
              }
            })();
            const fmt = (n, d = 2) => (typeof n === 'number' ? n.toFixed(d) : '0.00');
            const col = (n) => n > 0 ? 'pos' : (n < 0 ? 'neg' : 'muted');
            async function load() {
              try {
                const [health, markets, portfolio, performance, ai] = await Promise.all([
                  fetch('/health').then(r => r.json()).catch(() => ({ status: 'OFFLINE', mode: 'ERR', message: 'API Unreachable' })),
                  fetch('/markets').then(r => r.json()).catch(() => ({ markets: [] })),
                  fetch('/portfolio').then(r => r.json()).catch(() => ({ cash: 0, realized_pnl: 0, unrealized_pnl: 0, positions: {} })),
                  fetch('/performance').then(r => r.json()).catch(() => ({ trades: [] })),
                  fetch('/ai').then(r => r.json()).catch(() => ({ entries: {} })),
                ]);
                lastMarkets = markets || { markets: [] };
                document.getElementById('status').innerHTML = renderStatus(health);
                document.getElementById('markets').innerHTML = renderMarkets();
                document.getElementById('portfolio').innerHTML = renderPortfolio(portfolio);
                document.getElementById('trades').innerHTML = renderTrades(performance.trades);
                document.getElementById('ai').innerHTML = renderAI(ai);
              } catch (e) {
                console.error('Dashboard Loop Error:', e);
              }
            }
            function renderStatus(health) {
              const ok = (health.status || '').toLowerCase() === 'operational' || health.status === 'ok';
              return `<span class="${ok ? 'pos' : 'neg'}">${health.status || 'OFFLINE'}</span><br>
                      <span class="muted">Mode:</span> ${health.mode || '-'}<br>
                      <span class="muted">Msg:</span> ${health.message || 'Nominal'}`;
            }
            function setSearch(val) {
              marketSearch = (val || '').toLowerCase();
              document.getElementById('markets').innerHTML = renderMarkets();
            }
            function renderMarkets() {
              if (!lastMarkets.markets || lastMarkets.markets.length === 0) return '<div class="muted">No markets found in scan.</div>';
              const selected = new Set(lastMarkets.selected_ids || []);
              const eligible = new Set(lastMarkets.eligible_ids || []);
              const search = marketSearch || '';
              const sorted = [...lastMarkets.markets].sort((a, b) => {
                const aElig = eligible.has(a.id) ? 1 : 0;
                const bElig = eligible.has(b.id) ? 1 : 0;
                if (aElig !== bElig) return bElig - aElig;
                return (a.question || '').localeCompare(b.question || '');
              });
              const filtered = sorted.filter(m => {
                if (!search) return true;
                return (m.question || '').toLowerCase().includes(search) || (m.id || '').toLowerCase().includes(search);
              });
              const rows = filtered.map(m => {
                const snap = lastMarkets.snapshots[m.id] || {};
                const isSel = selected.has(m.id);
                const isElig = eligible.has(m.id);
                const checkedStr = isSel ? 'checked' : '';
                const disabledStr = isElig ? '' : 'disabled';
                const eligIcon = isElig ? '<span class="pos">CRITERIA MET</span>' : '<span class="muted">--</span>';
                const dChange = snap.depth_change_30s || 0;
                return `<tr>
                  <td style="text-align:center;"><input type="checkbox" ${checkedStr} ${disabledStr} onchange="toggleSelect('${m.id}', this.checked, this)"></td>
                  <td class="accent">${m.id}</td>
                  <td>${m.question}</td>
                  <td class="pos">${fmt(m.outcome_yes_price, 3)}</td>
                  <td class="neg">${fmt(m.outcome_no_price, 3)}</td>
                  <td>${fmt(snap.realized_vol_1m, 4)}</td>
                  <td class="${col(dChange)}">${fmt(dChange, 3)}</td>
                  <td>${eligIcon}</td>
                </tr>`;
              }).join('');
              const lastScan = lastMarkets.last_scan_at ? `<div class="muted" style="margin-bottom:10px;">Last Scan: ${lastMarkets.last_scan_at}</div>` : '';
              return `${lastScan}
                <div class="search-row">
                  <input type="text" placeholder="Search by ID or text..." value="${marketSearch}" oninput="setSearch(this.value)">
                  <div class="muted">Eligible crypto markets float to the top.</div>
                </div>
                <table>
                  <thead><tr><th>ACT</th><th>ID</th><th>QUESTION</th><th>YES</th><th>NO</th><th>VOL(1m)</th><th>DPTH Δ</th><th>ELIGIBLE</th></tr></thead>
                  <tbody>${rows}</tbody>
                </table>`;
            }
            async function toggleSelect(marketId, selected, el) {
              try {
                if (selected) {
                  document.querySelectorAll('#markets input[type="checkbox"]').forEach(cb => { if (cb !== el) cb.checked = false; });
                }
                await fetch('/markets/select', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ market_id: marketId, selected })
                });
                await load();
              } catch (e) {
                alert('Failed to toggle market selection');
              }
            }
            function renderPortfolio(p) {
              const positions = Object.values(p.positions || {});
              const rows = positions.map(pos => {
                const sideClass = pos.side === 'YES' ? 'pos' : 'neg';
                return `<tr><td class="accent">${pos.market_id}</td><td class="${sideClass}">${pos.side}</td><td>${pos.size}</td><td>${fmt(pos.average_price, 3)}</td></tr>`;
              }).join('');
              return `<div style="margin-bottom:15px; border-bottom:1px solid #333; padding-bottom:10px;">
                        <div style="font-size:1.2em;">USD: <span class="accent">$${fmt(p.cash)}</span></div>
                        <div>Realized: <span class="${col(p.realized_pnl)}">$${fmt(p.realized_pnl)}</span></div>
                        <div>Unrealized: <span class="${col(p.unrealized_pnl)}">$${fmt(p.unrealized_pnl)}</span></div>
                      </div>
                      <table><thead><tr><th>MKT</th><th>SIDE</th><th>SZ</th><th>AVG</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="muted">No Active Positions</td></tr>'}</tbody></table>`;
            }
            function renderTrades(trades) {
              if (!trades || trades.length === 0) return '<div class="muted">No execution history.</div>';
              const rows = trades.slice(-15).reverse().map(t => {
                const actionCol = t.action === 'BUY' ? 'pos' : 'neg';
                const ts = t.timestamp?.split('T')[1]?.split('.')[0] || t.timestamp;
                return `<tr><td class="muted">${ts}</td><td class="${actionCol}">${t.action}</td><td>${t.market_id}</td><td>${t.size} @ ${fmt(t.price, 3)}</td></tr>`;
              }).join('');
              return `<table><thead><tr><th>TIME</th><th>ACT</th><th>ID</th><th>FILL</th></tr></thead><tbody>${rows}</tbody></table>`;
            }
            function renderAI(ai) {
              if (!ai || !ai.entries || Object.keys(ai.entries).length === 0) return '<div class="muted">AI Model Idle.</div>';
              const rows = Object.entries(ai.entries).map(([marketId, data]) => {
                const dec = data.decision || {};
                const fc = data.forecast || {};
                const prob = fc.probability_yes ?? 0.5;
                return `<tr><td class="accent">${marketId}</td><td class="${prob > 0.6 ? 'pos' : (prob < 0.4 ? 'neg' : 'muted')}">${fmt(prob, 2)}</td><td class="${dec.action === 'BUY' ? 'pos' : 'neg'}">${dec.action || '-'}</td><td class="muted" style="font-size:0.7em;">${dec.reasoning ? dec.reasoning.substring(0, 50) + '...' : ''}</td></tr>`;
              }).join('');
              return `<table><thead><tr><th>ID</th><th>P(YES)</th><th>ACT</th><th>NOTE</th></tr></thead><tbody>${rows}</tbody></table>`;
            }
            load();
            setInterval(load, 4000);
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
