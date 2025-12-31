#!/usr/bin/env python3
"""
Live Cryptocurrency Price Visualizer

Reads the CSV output from crypto_price_checker.py and displays
a real-time updating chart of prices from all providers.

Usage:
    python3 live_chart.py btc_usd_24h.csv

Requirements:
    pip install matplotlib pandas
"""

import sys
import time
import argparse
from datetime import datetime, timedelta

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.animation import FuncAnimation
except ImportError:
    print("Error: Required libraries not found.")
    print("Install them with: pip install matplotlib pandas")
    sys.exit(1)


class LivePriceChart:
    def __init__(self, csv_path: str, window_minutes: int = 60, update_interval: int = 5000):
        """
        Initialize the live chart.
        
        Args:
            csv_path: Path to the CSV file being written by crypto_price_checker
            window_minutes: How many minutes of data to show (rolling window)
            update_interval: Milliseconds between chart updates
        """
        self.csv_path = csv_path
        self.window_minutes = window_minutes
        self.update_interval = update_interval
        
        # Set up the figure
        plt.style.use('dark_background')
        self.fig, (self.ax_price, self.ax_spread) = plt.subplots(
            2, 1, figsize=(14, 8), height_ratios=[3, 1]
        )
        self.fig.suptitle('Live Cryptocurrency Prices', fontsize=14, fontweight='bold')
        
        # Colors for each provider
        self.colors = {
            'CoinGecko': '#8DC647',   # Green
            'Binance': '#F0B90B',      # Yellow/Gold
            'Coinbase': '#0052FF',     # Blue
            'average': '#FFFFFF',      # White
        }
        
        # Initialize empty line objects
        self.lines = {}
        self.spread_line = None
        
        # Track last file size to detect updates
        self.last_size = 0
        
    def read_csv(self) -> pd.DataFrame:
        """Read the CSV file and return as DataFrame."""
        try:
            df = pd.read_csv(self.csv_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter to rolling window
            if self.window_minutes:
                cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
                df = df[df['timestamp'] > cutoff]
            
            return df
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return pd.DataFrame()
    
    def init_plot(self):
        """Initialize the plot elements."""
        self.ax_price.set_xlabel('Time')
        self.ax_price.set_ylabel('Price (USD)')
        self.ax_price.grid(True, alpha=0.3)
        self.ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        self.ax_spread.set_xlabel('Time')
        self.ax_spread.set_ylabel('Spread %')
        self.ax_spread.grid(True, alpha=0.3)
        self.ax_spread.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        return []
    
    def update(self, frame):
        """Update function called by animation."""
        df = self.read_csv()
        
        if df.empty:
            return []
        
        # Clear and redraw
        self.ax_price.clear()
        self.ax_spread.clear()
        
        # Get the symbol from data
        symbol = df['symbol'].iloc[0] if 'symbol' in df.columns else 'CRYPTO'
        currency = df['base_currency'].iloc[0] if 'base_currency' in df.columns else 'USD'
        
        # Plot each provider
        providers = ['CoinGecko', 'Binance', 'Coinbase']
        for provider in providers:
            if provider in df.columns:
                valid_data = df[df[provider].notna()]
                if not valid_data.empty:
                    self.ax_price.plot(
                        valid_data['timestamp'], 
                        valid_data[provider],
                        label=provider,
                        color=self.colors.get(provider, '#CCCCCC'),
                        linewidth=1.5,
                        marker='o',
                        markersize=3
                    )
        
        # Plot average
        if 'average' in df.columns:
            valid_avg = df[df['average'].notna()]
            if not valid_avg.empty:
                self.ax_price.plot(
                    valid_avg['timestamp'],
                    valid_avg['average'],
                    label='Average',
                    color=self.colors['average'],
                    linewidth=2,
                    linestyle='--',
                    alpha=0.8
                )
        
        # Plot spread percentage
        if 'spread_pct' in df.columns:
            valid_spread = df[df['spread_pct'].notna()]
            if not valid_spread.empty:
                self.ax_spread.fill_between(
                    valid_spread['timestamp'],
                    valid_spread['spread_pct'],
                    alpha=0.5,
                    color='#FF6B6B'
                )
                self.ax_spread.plot(
                    valid_spread['timestamp'],
                    valid_spread['spread_pct'],
                    color='#FF6B6B',
                    linewidth=1.5
                )
        
        # Formatting
        self.ax_price.set_title(f'{symbol}/{currency} - Live Prices', fontsize=12)
        self.ax_price.set_ylabel(f'Price ({currency})')
        self.ax_price.legend(loc='upper left')
        self.ax_price.grid(True, alpha=0.3)
        self.ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Add current price annotation
        if 'average' in df.columns and not df['average'].isna().all():
            last_price = df['average'].dropna().iloc[-1]
            last_time = df['timestamp'].iloc[-1]
            self.ax_price.annotate(
                f'${last_price:,.2f}',
                xy=(last_time, last_price),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=11,
                fontweight='bold',
                color='white',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#333333', edgecolor='white')
            )
        
        self.ax_spread.set_title('Price Spread Between Exchanges', fontsize=10)
        self.ax_spread.set_ylabel('Spread %')
        self.ax_spread.set_xlabel('Time')
        self.ax_spread.grid(True, alpha=0.3)
        self.ax_spread.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Rotate x-axis labels
        plt.setp(self.ax_price.xaxis.get_majorticklabels(), rotation=45, ha='right')
        plt.setp(self.ax_spread.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        self.fig.tight_layout()
        
        return []
    
    def run(self):
        """Start the live chart."""
        print(f"📊 Starting live chart for: {self.csv_path}")
        print(f"   Window: {self.window_minutes} minutes")
        print(f"   Update interval: {self.update_interval}ms")
        print("   Close the chart window to stop.")
        
        ani = FuncAnimation(
            self.fig,
            self.update,
            init_func=self.init_plot,
            interval=self.update_interval,
            blit=False,
            cache_frame_data=False
        )
        
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Live visualization of cryptocurrency price data from CSV'
    )
    parser.add_argument(
        'csv_file',
        help='Path to the CSV file (e.g., btc_usd_24h.csv)'
    )
    parser.add_argument(
        '--window', '-w',
        type=int,
        default=60,
        help='Rolling window in minutes (default: 60)'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=5000,
        help='Chart update interval in milliseconds (default: 5000)'
    )
    
    args = parser.parse_args()
    
    chart = LivePriceChart(
        csv_path=args.csv_file,
        window_minutes=args.window,
        update_interval=args.interval
    )
    chart.run()


if __name__ == '__main__':
    main()
