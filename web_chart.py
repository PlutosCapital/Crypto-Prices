#!/usr/bin/env python3
"""
Web-Based Live Cryptocurrency Price Visualizer

Starts a local web server that serves a live-updating chart
reading from your CSV file. No external dependencies needed!

Usage:
    python3 web_chart.py btc_usd_24h.csv
    
Then open http://localhost:8080 in your browser.

Uses only Python standard library + inline JavaScript (Chart.js from CDN).
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class ChartHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving chart data."""
    
    csv_path = None
    window_minutes = 60
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            self.serve_html()
        elif parsed.path == '/data':
            self.serve_data()
        else:
            self.send_error(404)
    
    def serve_html(self):
        """Serve the main HTML page with Chart.js."""
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Crypto Prices</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 {
            text-align: center;
            margin-bottom: 10px;
            font-size: 2em;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status {
            text-align: center;
            margin-bottom: 20px;
            color: #888;
            font-size: 0.9em;
        }
        .status .live { color: #4ade80; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-card .label { color: #888; font-size: 0.85em; margin-bottom: 5px; }
        .stat-card .value { font-size: 1.8em; font-weight: bold; }
        .stat-card.coingecko .value { color: #8DC647; }
        .stat-card.binance .value { color: #F0B90B; }
        .stat-card.coinbase .value { color: #0052FF; }
        .stat-card.average .value { color: #fff; }
        .stat-card.spread .value { color: #FF6B6B; }
        .chart-container {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .chart-title {
            font-size: 1.1em;
            margin-bottom: 15px;
            color: #ccc;
        }
        canvas { width: 100% !important; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 Live Crypto Prices</h1>
        <p class="status">
            <span class="live">●</span> Live updating every 5 seconds
            | Data points: <span id="dataPoints">0</span>
            | Last update: <span id="lastUpdate">--</span>
        </p>
        
        <div class="stats">
            <div class="stat-card coingecko">
                <div class="label">CoinGecko</div>
                <div class="value" id="price-coingecko">--</div>
            </div>
            <div class="stat-card binance">
                <div class="label">Binance</div>
                <div class="value" id="price-binance">--</div>
            </div>
            <div class="stat-card coinbase">
                <div class="label">Coinbase</div>
                <div class="value" id="price-coinbase">--</div>
            </div>
            <div class="stat-card average">
                <div class="label">Average</div>
                <div class="value" id="price-average">--</div>
            </div>
            <div class="stat-card spread">
                <div class="label">Spread</div>
                <div class="value" id="price-spread">--</div>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">Price Comparison</div>
            <canvas id="priceChart"></canvas>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">Spread Percentage</div>
            <canvas id="spreadChart"></canvas>
        </div>
    </div>

    <script>
        // Chart configuration
        const priceCtx = document.getElementById('priceChart').getContext('2d');
        const spreadCtx = document.getElementById('spreadChart').getContext('2d');
        
        const priceChart = new Chart(priceCtx, {
            type: 'line',
            data: {
                datasets: [
                    { label: 'CoinGecko', borderColor: '#8DC647', backgroundColor: 'rgba(141,198,71,0.1)', data: [], tension: 0.1 },
                    { label: 'Binance', borderColor: '#F0B90B', backgroundColor: 'rgba(240,185,11,0.1)', data: [], tension: 0.1 },
                    { label: 'Coinbase', borderColor: '#0052FF', backgroundColor: 'rgba(0,82,255,0.1)', data: [], tension: 0.1 },
                    { label: 'Average', borderColor: '#ffffff', backgroundColor: 'rgba(255,255,255,0.1)', data: [], borderDash: [5, 5], tension: 0.1 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 3,
                interaction: { intersect: false, mode: 'index' },
                scales: {
                    x: { type: 'time', time: { unit: 'minute' }, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#888' } },
                    y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#888', callback: v => '$' + v.toLocaleString() } }
                },
                plugins: { legend: { labels: { color: '#ccc' } } }
            }
        });
        
        const spreadChart = new Chart(spreadCtx, {
            type: 'line',
            data: {
                datasets: [
                    { label: 'Spread %', borderColor: '#FF6B6B', backgroundColor: 'rgba(255,107,107,0.2)', data: [], fill: true, tension: 0.1 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 5,
                scales: {
                    x: { type: 'time', time: { unit: 'minute' }, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#888' } },
                    y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#888', callback: v => v.toFixed(3) + '%' }, min: 0 }
                },
                plugins: { legend: { display: false } }
            }
        });
        
        function formatPrice(value) {
            if (!value || isNaN(value)) return '--';
            return '$' + parseFloat(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
        
        async function fetchData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();
                
                if (!data.length) return;
                
                // Update stats
                const latest = data[data.length - 1];
                document.getElementById('price-coingecko').textContent = formatPrice(latest.CoinGecko);
                document.getElementById('price-binance').textContent = formatPrice(latest.Binance);
                document.getElementById('price-coinbase').textContent = formatPrice(latest.Coinbase);
                document.getElementById('price-average').textContent = formatPrice(latest.average);
                document.getElementById('price-spread').textContent = latest.spread_pct ? latest.spread_pct.toFixed(3) + '%' : '--';
                document.getElementById('dataPoints').textContent = data.length;
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                
                // Update charts
                priceChart.data.datasets[0].data = data.map(d => ({ x: new Date(d.timestamp), y: d.CoinGecko })).filter(d => d.y);
                priceChart.data.datasets[1].data = data.map(d => ({ x: new Date(d.timestamp), y: d.Binance })).filter(d => d.y);
                priceChart.data.datasets[2].data = data.map(d => ({ x: new Date(d.timestamp), y: d.Coinbase })).filter(d => d.y);
                priceChart.data.datasets[3].data = data.map(d => ({ x: new Date(d.timestamp), y: d.average })).filter(d => d.y);
                priceChart.update('none');
                
                spreadChart.data.datasets[0].data = data.map(d => ({ x: new Date(d.timestamp), y: d.spread_pct })).filter(d => d.y);
                spreadChart.update('none');
                
            } catch (err) {
                console.error('Failed to fetch data:', err);
            }
        }
        
        // Initial fetch and set up polling
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>'''
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_data(self):
        """Serve CSV data as JSON."""
        data = []
        
        try:
            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
                
                for row in reader:
                    try:
                        ts = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                        if ts > cutoff:
                            data.append({
                                'timestamp': row['timestamp'],
                                'symbol': row.get('symbol', ''),
                                'CoinGecko': float(row['CoinGecko']) if row.get('CoinGecko') else None,
                                'Binance': float(row['Binance']) if row.get('Binance') else None,
                                'Coinbase': float(row['Coinbase']) if row.get('Coinbase') else None,
                                'average': float(row['average']) if row.get('average') else None,
                                'spread_pct': float(row['spread_pct']) if row.get('spread_pct') else None,
                            })
                    except (ValueError, KeyError):
                        continue
        except FileNotFoundError:
            pass
        
        json_data = json.dumps(data)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(json_data))
        self.end_headers()
        self.wfile.write(json_data.encode())
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main():
    parser = argparse.ArgumentParser(
        description='Web-based live visualization of crypto prices'
    )
    parser.add_argument(
        'csv_file',
        help='Path to the CSV file'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8080,
        help='Port to run the server on (default: 8080)'
    )
    parser.add_argument(
        '--window', '-w',
        type=int,
        default=60,
        help='Rolling window in minutes (default: 60)'
    )
    
    args = parser.parse_args()
    
    # Set class variables
    ChartHandler.csv_path = args.csv_file
    ChartHandler.window_minutes = args.window
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║        📊 Live Crypto Price Visualizer                   ║
╠══════════════════════════════════════════════════════════╣
║  CSV File: {args.csv_file:<45} ║
║  Window:   {args.window} minutes{' ' * 40}║
║  Server:   http://localhost:{args.port:<30} ║
╠══════════════════════════════════════════════════════════╣
║  Open the URL above in your browser                      ║
║  Press Ctrl+C to stop the server                         ║
╚══════════════════════════════════════════════════════════╝
""")
    
    server = HTTPServer(('localhost', args.port), ChartHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
        server.shutdown()


if __name__ == '__main__':
    main()
