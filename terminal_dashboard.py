#!/usr/bin/env python3
import argparse
import csv
import curses
import os
import time
from datetime import datetime
from statistics import mean, pstdev


def parse_float(x):
    try:
        return float(x)
    except Exception:
        return None


def read_csv_tail(path, max_rows=600):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    if len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows


def extract_series(rows):
    ts = []
    avgs = []
    spreads = []
    providers = []
    for row in rows:
        t = row.get("timestamp")
        ts.append(t)
        a = parse_float(row.get("average", ""))
        if a is None:
            vals = [parse_float(row.get(k, "")) for k in ["CoinGecko", "Binance", "Coinbase"]]
            vals = [v for v in vals if v is not None]
            a = mean(vals) if vals else None
        avgs.append(a)
        s = parse_float(row.get("spread", ""))
        spreads.append(s)
        providers.append({
            "CoinGecko": parse_float(row.get("CoinGecko", "")),
            "Binance": parse_float(row.get("Binance", "")),
            "Coinbase": parse_float(row.get("Coinbase", "")),
        })
    return ts, avgs, spreads, providers


def select_window(ts, values, seconds):
    if not ts or not values:
        return []
    try:
        end = datetime.strptime(ts[-1], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return []
    out = []
    for t, v in zip(ts[::-1], values[::-1]):
        try:
            dt = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
        except Exception:
            break
        delta = (end - dt).total_seconds()
        if delta <= seconds:
            if v is not None:
                out.append(v)
        else:
            break
    return out[::-1]


def sparkline(values, width):
    if not values:
        return "".ljust(width)
    chars = "▁▂▃▄▅▆▇█"
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return chars[0] * min(width, len(values))
    step = max(1, len(values) // max(1, width))
    samples = values[::step]
    out = []
    for v in samples[:width]:
        idx = int((v - lo) / (hi - lo) * (len(chars) - 1))
        out.append(chars[idx])
    return "".join(out).ljust(width)


def draw_dashboard(stdscr, csv_path, refresh, chart_points):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    while True:
        rows = read_csv_tail(csv_path, max_rows=2000)
        ts, avgs, spreads, providers = extract_series(rows)
        h, w = stdscr.getmaxyx()
        stdscr.erase()
        title = "Crypto Terminal v3"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last = rows[-1] if rows else {}
        sym = last.get("symbol", "BTC")
        base = last.get("base_currency", "USD")
        stdscr.addstr(0, 2, f"{title}  {now}")
        stdscr.addstr(0, w - 24, f"{sym}/{base}")
        latest_avg = avgs[-1] if avgs and avgs[-1] is not None else None
        latest_spread = spreads[-1] if spreads and spreads[-1] is not None else None
        ma_1m = mean(select_window(ts, avgs, 60)) if select_window(ts, avgs, 60) else None
        ma_5m = mean(select_window(ts, avgs, 300)) if select_window(ts, avgs, 300) else None
        ma_15m = mean(select_window(ts, avgs, 900)) if select_window(ts, avgs, 900) else None
        vol_15m_vals = select_window(ts, avgs, 900)
        vol_15m = pstdev(vol_15m_vals) if len(vol_15m_vals) >= 2 else None
        spread_mean_15m = mean(select_window(ts, spreads, 900)) if select_window(ts, spreads, 900) else None
        spread_max_15m = max(select_window(ts, spreads, 900)) if select_window(ts, spreads, 900) else None
        line_y = 2
        stdscr.addstr(line_y, 2, "Latest:")
        if latest_avg is not None:
            stdscr.addstr(line_y, 12, f"{latest_avg:,.2f}", curses.color_pair(3))
        if latest_spread is not None and latest_avg:
            sp_pct = latest_spread / latest_avg * 100
            stdscr.addstr(line_y, 28, f"Spread {latest_spread:,.2f} ({sp_pct:.3f}%)")
        stdscr.addstr(line_y + 1, 2, "MA1m:")
        stdscr.addstr(line_y + 1, 12, f"{ma_1m:,.2f}" if ma_1m else "-")
        stdscr.addstr(line_y + 1, 28, "MA5m:")
        stdscr.addstr(line_y + 1, 36, f"{ma_5m:,.2f}" if ma_5m else "-")
        stdscr.addstr(line_y + 1, 52, "MA15m:")
        stdscr.addstr(line_y + 1, 61, f"{ma_15m:,.2f}" if ma_15m else "-")
        stdscr.addstr(line_y + 2, 2, "Vol15m:")
        stdscr.addstr(line_y + 2, 12, f"{vol_15m:,.2f}" if vol_15m else "-")
        stdscr.addstr(line_y + 2, 28, "Spread15m:")
        stdscr.addstr(line_y + 2, 40, f"mean {spread_mean_15m:,.2f}" if spread_mean_15m else "mean -")
        stdscr.addstr(line_y + 2, 62, f"max {spread_max_15m:,.2f}" if spread_max_15m else "max -")
        chart_y = line_y + 4
        chart_h = max(5, min(12, h - chart_y - 8))
        chart_w = max(30, w - 32)
        series = [v for v in avgs if v is not None]
        if series:
            series = series[-chart_points:]
        sl = sparkline(series, chart_w)
        stdscr.addstr(chart_y, 2, sl)
        table_y = chart_y + 2
        stdscr.addstr(table_y, 2, "Providers:")
        last_prov = providers[-1] if providers else {}
        cg = last_prov.get("CoinGecko") if last_prov else None
        bn = last_prov.get("Binance") if last_prov else None
        cb = last_prov.get("Coinbase") if last_prov else None
        def color_for_delta(val):
            if latest_avg is None or val is None:
                return 0
            d = val - latest_avg
            return 1 if d >= 0 else 2
        stdscr.addstr(table_y + 1, 4, "CoinGecko")
        stdscr.addstr(table_y + 1, 18, f"{cg:,.2f}" if cg else "-", curses.color_pair(color_for_delta(cg)))
        stdscr.addstr(table_y + 2, 4, "Binance")
        stdscr.addstr(table_y + 2, 18, f"{bn:,.2f}" if bn else "-", curses.color_pair(color_for_delta(bn)))
        stdscr.addstr(table_y + 3, 4, "Coinbase")
        stdscr.addstr(table_y + 3, 18, f"{cb:,.2f}" if cb else "-", curses.color_pair(color_for_delta(cb)))
        stdscr.addstr(h - 2, 2, "q: quit  r: refresh")
        stdscr.refresh()
        stdscr.nodelay(True)
        for _ in range(int(refresh * 10)):
            ch = stdscr.getch()
            if ch in (ord("q"), 27):
                return
            time.sleep(0.1)


def main():
    p = argparse.ArgumentParser(description="Terminal dashboard v3")
    p.add_argument("--csv", type=str, default=os.path.expanduser("~/Documents/florian/coding/Crypto_PriceDataFetch/btc_usd_24h.csv"))
    p.add_argument("--refresh", type=float, default=1.0)
    p.add_argument("--points", type=int, default=240)
    args = p.parse_args()
    curses.wrapper(draw_dashboard, args.csv, args.refresh, args.points)


if __name__ == "__main__":
    main()
            font-size: 0.8em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
        }
        
        .card-body { padding: 18px; }
        
        /* Price Grid */
        .price-grid {
            grid-column: 1;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }
        
        .price-card {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
        }
        
        .price-card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }
        
        .price-symbol {
            font-size: 1.3em;
            font-weight: 700;
        }
        
        .price-symbol.btc { color: #f7931a; }
        .price-symbol.eth { color: #627eea; }
        .price-symbol.sol { color: #00ffa3; }
        
        .price-badge {
            font-size: 0.75em;
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 500;
        }
        
        .price-badge.positive { background: rgba(0,255,136,0.15); color: var(--accent-green); }
        .price-badge.negative { background: rgba(255,51,102,0.15); color: var(--accent-red); }
        
        .price-main {
            font-family: 'JetBrains Mono', monospace;
            font-size: 2em;
            font-weight: 600;
            margin-bottom: 20px;
        }
        
        .price-exchanges {
            display: grid;
            gap: 10px;
        }
        
        .exchange-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: var(--bg-secondary);
            border-radius: 6px;
            font-size: 0.9em;
        }
        
        .exchange-name { color: var(--text-secondary); }
        .exchange-price { font-family: 'JetBrains Mono', monospace; }
        
        .exchange-row.best-buy { border-left: 3px solid var(--accent-green); }
        .exchange-row.best-sell { border-left: 3px solid var(--accent-red); }
        
        .spread-indicator {
            margin-top: 16px;
            padding: 12px;
            background: var(--bg-secondary);
            border-radius: 8px;
            text-align: center;
        }
        
        .spread-label { font-size: 0.75em; color: var(--text-secondary); margin-bottom: 4px; }
        .spread-value { font-family: 'JetBrains Mono', monospace; font-size: 1.4em; font-weight: 600; }
        .spread-value.alert { color: var(--accent-yellow); }
        
        /* Chart Section */
        .chart-section {
            grid-column: 1;
        }
        
        .chart-container {
            height: 300px;
            padding: 10px;
        }
        
        /* Sidebar */
        .sidebar {
            grid-column: 2;
            grid-row: 2 / -1;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        /* Controls */
        .controls { display: flex; flex-direction: column; gap: 12px; }
        
        .btn {
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-size: 0.9em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            color: white;
        }
        
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,170,255,0.3); }
        
        .btn-danger {
            background: rgba(255,51,102,0.2);
            color: var(--accent-red);
            border: 1px solid var(--accent-red);
        }
        
        .btn-danger:hover { background: rgba(255,51,102,0.3); }
        
        .btn-success {
            background: rgba(0,255,136,0.2);
            color: var(--accent-green);
            border: 1px solid var(--accent-green);
        }
        
        .btn-success:hover { background: rgba(0,255,136,0.3); }
        
        /* Stats */
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        
        .stat-item {
            background: var(--bg-tertiary);
            padding: 14px;
            border-radius: 8px;
            text-align: center;
        }
        
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.4em;
            font-weight: 600;
            color: var(--accent-blue);
        }
        
        .stat-label {
            font-size: 0.7em;
            color: var(--text-secondary);
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Settings */
        .setting-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .setting-row:last-child { border-bottom: none; }
        
        .setting-label { font-size: 0.9em; color: var(--text-secondary); }
        
        .setting-input {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px 12px;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            width: 100px;
            text-align: right;
        }
        
        .setting-input:focus { outline: none; border-color: var(--accent-blue); }
        
        /* Alerts Log */
        .alerts-log {
            max-height: 200px;
            overflow-y: auto;
        }
        
        .alert-item {
            padding: 10px 12px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            margin-bottom: 8px;
            border-left: 3px solid var(--accent-yellow);
        }
        
        .alert-item-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
        }
        
        .alert-symbol { font-weight: 600; color: var(--accent-yellow); }
        .alert-time { font-size: 0.75em; color: var(--text-secondary); font-family: 'JetBrains Mono', monospace; }
        .alert-spread { font-family: 'JetBrains Mono', monospace; font-size: 0.9em; }
        
        /* Market Overview Table */
        .market-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .market-table th {
            text-align: left;
            padding: 12px;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border);
        }
        
        .market-table td {
            padding: 14px 12px;
            border-bottom: 1px solid var(--border);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9em;
        }
        
        .market-table tr:hover { background: var(--bg-tertiary); }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-secondary); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-secondary); }
        
        /* Responsive */
        @media (max-width: 1200px) {
            .main { grid-template-columns: 1fr; }
            .sidebar { grid-column: 1; grid-row: auto; }
            .price-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <div class="logo-icon">📊</div>
            <span>ArbitrageAndy</span>
            <span style="font-size: 0.5em; color: var(--text-secondary); font-weight: 400;">TERMINAL v2.0</span>
        </div>
        <div class="header-right">
            <div class="clock terminal-font" id="clock">--:--:--</div>
            <div class="status-indicator" id="statusIndicator">
                <div class="pulse"></div>
                <span id="statusText">LOADING</span>
            </div>
        </div>
    </header>
    
    <main class="main">
        <!-- Ticker Tape -->
        <div class="ticker-tape" id="tickerTape">
            <div class="ticker-item">
                <span class="ticker-symbol">Loading...</span>
            </div>
        </div>
        
        <!-- Price Cards -->
        <div class="price-grid" id="priceGrid">
            <!-- Populated by JS -->
        </div>
        
        <!-- Chart -->
        <div class="card chart-section">
            <div class="card-header">
                <span class="card-title">📈 Spread History</span>
                <select id="chartSymbol" style="background: var(--bg-tertiary); border: 1px solid var(--border); color: var(--text-primary); padding: 4px 8px; border-radius: 4px;">
                    <option value="BTC">BTC</option>
                    <option value="ETH">ETH</option>
                    <option value="SOL">SOL</option>
                </select>
            </div>
            <div class="chart-container">
                <canvas id="spreadChart"></canvas>
            </div>
        </div>
        
        <!-- Sidebar -->
        <div class="sidebar">
            <!-- Controls -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">⚡ Bot Controls</span>
                </div>
                <div class="card-body controls">
                    <button class="btn btn-success" id="btnStart" onclick="startBot()">
                        ▶ Start Bot
                    </button>
                    <button class="btn btn-danger" id="btnStop" onclick="stopBot()" style="display:none;">
                        ⏹ Stop Bot
                    </button>
                    <button class="btn btn-primary" onclick="sendTestAlert()">
                        📤 Send Test Alert
                    </button>
                </div>
            </div>
            
            <!-- Stats -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">📊 Session Stats</span>
                </div>
                <div class="card-body">
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-value" id="statChecks">0</div>
                            <div class="stat-label">Checks</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="statAlerts">0</div>
                            <div class="stat-label">Alerts</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="statUptime">00:00</div>
                            <div class="stat-label">Uptime</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="statMaxSpread">0.00%</div>
                            <div class="stat-label">Max Spread</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Settings -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">⚙️ Settings</span>
                </div>
                <div class="card-body">
                    <div class="setting-row">
                        <span class="setting-label">Spread Alert %</span>
                        <input type="number" class="setting-input" id="settingSpread" value="0.2" step="0.05" onchange="updateSettings()">
                    </div>
                    <div class="setting-row">
                        <span class="setting-label">Check Interval (s)</span>
                        <input type="number" class="setting-input" id="settingInterval" value="15" step="5" onchange="updateSettings()">
                    </div>
                    <div class="setting-row">
                        <span class="setting-label">Alerts Enabled</span>
                        <input type="checkbox" id="settingAlerts" checked onchange="updateSettings()" style="width: 20px; height: 20px;">
                    </div>
                </div>
            </div>
            
            <!-- Recent Alerts -->
            <div class="card" style="flex: 1;">
                <div class="card-header">
                    <span class="card-title">🔔 Recent Alerts</span>
                </div>
                <div class="card-body alerts-log" id="alertsLog">
                    <div style="color: var(--text-secondary); text-align: center; padding: 20px;">
                        No alerts yet
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        // Chart setup
        const ctx = document.getElementById('spreadChart').getContext('2d');
        const spreadChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Spread %',
                    data: [],
                    borderColor: '#00aaff',
                    backgroundColor: 'rgba(0, 170, 255, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    borderWidth: 2
                }, {
                    label: 'Threshold',
                    data: [],
                    borderColor: '#ffaa00',
                    borderDash: [5, 5],
                    pointRadius: 0,
                    borderWidth: 1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'minute' },
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#8888aa' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { 
                            color: '#8888aa',
                            callback: v => v.toFixed(2) + '%'
                        },
                        min: 0
                    }
                }
            }
        });
        
        let currentData = {};
        let maxSpread = 0;
        
        // Clock
        function updateClock() {
            document.getElementById('clock').textContent = new Date().toLocaleTimeString();
        }
        setInterval(updateClock, 1000);
        updateClock();
        
        // Fetch data
        async function fetchData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                currentData = data;
                updateUI(data);
            } catch (e) {
                console.error('Fetch error:', e);
            }
        }
        
        function updateUI(data) {
            // Status
            const indicator = document.getElementById('statusIndicator');
            const statusText = document.getElementById('statusText');
            const btnStart = document.getElementById('btnStart');
            const btnStop = document.getElementById('btnStop');
            
            if (data.bot_status.running) {
                indicator.className = 'status-indicator status-running';
                statusText.textContent = 'LIVE';
                btnStart.style.display = 'none';
                btnStop.style.display = 'flex';
            } else {
                indicator.className = 'status-indicator status-stopped';
                statusText.textContent = 'STOPPED';
                btnStart.style.display = 'flex';
                btnStop.style.display = 'none';
            }
            
            // Stats
            document.getElementById('statChecks').textContent = data.bot_status.checks || 0;
            document.getElementById('statAlerts').textContent = data.bot_status.alerts_sent || 0;
            
            if (data.bot_status.start_time && data.bot_status.running) {
                const start = new Date(data.bot_status.start_time);
                const diff = Math.floor((Date.now() - start) / 1000);
                const mins = Math.floor(diff / 60);
                const secs = diff % 60;
                document.getElementById('statUptime').textContent = 
                    `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            }
            
            // Ticker & Price Cards
            if (data.prices) {
                updateTicker(data.prices);
                updatePriceCards(data.prices);
            }
            
            // Chart
            if (data.history && data.history.length > 0) {
                updateChart(data.history);
            }
            
            // Alerts
            if (data.alerts) {
                updateAlerts(data.alerts);
            }
            
            // Max spread
            document.getElementById('statMaxSpread').textContent = maxSpread.toFixed(2) + '%';
        }
        
        function updateTicker(prices) {
            const ticker = document.getElementById('tickerTape');
            ticker.innerHTML = Object.entries(prices).map(([symbol, data]) => {
                const change = data.change_24h || 0;
                const changeClass = change >= 0 ? 'positive' : 'negative';
                const changeSign = change >= 0 ? '+' : '';
                return `
                    <div class="ticker-item">
                        <span class="ticker-symbol">${symbol}</span>
                        <span class="ticker-price">$${data.average?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '--'}</span>
                        <span class="ticker-change ${changeClass}">${changeSign}${change?.toFixed(2) || '0.00'}%</span>
                    </div>
                `;
            }).join('');
        }
        
        function updatePriceCards(prices) {
            const grid = document.getElementById('priceGrid');
            grid.innerHTML = Object.entries(prices).map(([symbol, data]) => {
                const exchanges = [
                    { name: 'CoinGecko', price: data.coingecko },
                    { name: 'Binance', price: data.binance },
                    { name: 'Coinbase', price: data.coinbase }
                ].filter(e => e.price);
                
                const minEx = exchanges.reduce((a, b) => (a.price < b.price ? a : b), exchanges[0]);
                const maxEx = exchanges.reduce((a, b) => (a.price > b.price ? a : b), exchanges[0]);
                
                const change = data.change_24h || 0;
                const changeClass = change >= 0 ? 'positive' : 'negative';
                const spreadPct = data.spread_pct || 0;
                const spreadClass = spreadPct >= 0.2 ? 'alert' : '';
                
                if (spreadPct > maxSpread) maxSpread = spreadPct;
                
                return `
                    <div class="price-card">
                        <div class="price-card-header">
                            <span class="price-symbol ${symbol.toLowerCase()}">${symbol}</span>
                            <span class="price-badge ${changeClass}">${change >= 0 ? '+' : ''}${change?.toFixed(2)}%</span>
                        </div>
                        <div class="price-main">$${data.average?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '--'}</div>
                        <div class="price-exchanges">
                            ${exchanges.map(ex => `
                                <div class="exchange-row ${ex.name === minEx?.name ? 'best-buy' : ''} ${ex.name === maxEx?.name ? 'best-sell' : ''}">
                                    <span class="exchange-name">${ex.name}</span>
                                    <span class="exchange-price">$${ex.price?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                                </div>
                            `).join('')}
                        </div>
                        <div class="spread-indicator">
                            <div class="spread-label">SPREAD</div>
                            <div class="spread-value ${spreadClass}">${spreadPct?.toFixed(3)}%</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function updateChart(history) {
            const symbol = document.getElementById('chartSymbol').value;
            const threshold = parseFloat(document.getElementById('settingSpread').value) || 0.2;
            
            const chartData = history
                .filter(h => h.prices && h.prices[symbol])
                .slice(-60)
                .map(h => ({
                    x: new Date(h.timestamp),
                    y: h.prices[symbol].spread_pct || 0
                }));
            
            const thresholdData = chartData.map(d => ({ x: d.x, y: threshold }));
            
            spreadChart.data.datasets[0].data = chartData;
            spreadChart.data.datasets[1].data = thresholdData;
            spreadChart.update('none');
        }
        
        function updateAlerts(alerts) {
            const log = document.getElementById('alertsLog');
            if (alerts.length === 0) {
                log.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 20px;">No alerts yet</div>';
                return;
            }
            
            log.innerHTML = alerts.slice(-10).reverse().map(a => `
                <div class="alert-item">
                    <div class="alert-item-header">
                        <span class="alert-symbol">${a.symbol}</span>
                        <span class="alert-time">${new Date(a.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div class="alert-spread">Spread: ${a.spread_pct?.toFixed(3)}% ($${a.spread?.toFixed(2)})</div>
                </div>
            `).join('');
        }
        
        // Actions
        async function startBot() {
            await fetch('/api/start', { method: 'POST' });
            fetchData();
        }
        
        async function stopBot() {
            await fetch('/api/stop', { method: 'POST' });
            fetchData();
        }
        
        async function sendTestAlert() {
            await fetch('/api/test', { method: 'POST' });
            alert('Test alert sent to Telegram!');
        }
        
        async function updateSettings() {
            const settings = {
                spread_threshold: parseFloat(document.getElementById('settingSpread').value),
                check_interval: parseInt(document.getElementById('settingInterval').value),
                alerts_enabled: document.getElementById('settingAlerts').checked
            };
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
        }
        
        // Chart symbol change
        document.getElementById('chartSymbol').addEventListener('change', () => {
            if (currentData.history) updateChart(currentData.history);
        });
        
        // Initial fetch and polling
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>
'''

# =============================================================================
# HTTP HANDLER
# =============================================================================

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logs
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/':
            self.send_html(DASHBOARD_HTML)
        elif path == '/api/data':
            prices = fetch_all_prices() if not price_history else price_history[-1].get('prices', {})
            self.send_json({
                'prices': prices,
                'history': price_history[-100:],
                'alerts': alert_history[-20:],
                'bot_status': bot_status,
                'config': CONFIG
            })
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        path = urlparse(self.path).path
        
        if path == '/api/start':
            start_bot()
            self.send_json({'success': True})
        elif path == '/api/stop':
            stop_bot()
            self.send_json({'success': True})
        elif path == '/api/test':
            send_telegram("🧪 <b>Test Alert</b>\n\nArbitrageAndy Terminal is working!")
            self.send_json({'success': True})
        elif path == '/api/settings':
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            CONFIG.update(body)
            self.send_json({'success': True})
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# =============================================================================
# MAIN
# =============================================================================

def main():
    port = 8080
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     █████╗ ██████╗ ██████╗ ██╗████████╗██████╗  █████╗        ║
║    ██╔══██╗██╔══██╗██╔══██╗██║╚══██╔══╝██╔══██╗██╔══██╗       ║
║    ███████║██████╔╝██████╔╝██║   ██║   ██████╔╝███████║       ║
║    ██╔══██║██╔══██╗██╔══██╗██║   ██║   ██╔══██╗██╔══██║       ║
║    ██║  ██║██║  ██║██████╔╝██║   ██║   ██║  ██║██║  ██║       ║
║    ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝       ║
║                                                               ║
║                    TERMINAL DASHBOARD v2.0                    ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║   🌐 Dashboard: http://localhost:{port:<24}             ║
║                                                               ║
║   📊 Monitoring: BTC, ETH, SOL                                ║
║   📱 Telegram: @ArbitrageAndy_bot                             ║
║                                                               ║
║   Press Ctrl+C to stop                                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        stop_bot()
        server.shutdown()

if __name__ == '__main__':
    main()
