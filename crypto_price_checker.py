#!/usr/bin/env python3
"""
Cryptocurrency Price Comparison Tool

A lightweight CLI tool to fetch and compare real-time cryptocurrency prices
from multiple API providers (CoinGecko, Binance, Coinbase).

Usage:
    python crypto_price_checker.py [symbol] [base_currency]
    
Examples:
    python crypto_price_checker.py btc
    python crypto_price_checker.py eth usd
    python crypto_price_checker.py sol eur

Author: Claude
License: MIT
"""

import csv
import json
import os
import signal
import sys
import time
import argparse
from datetime import datetime
from statistics import mean
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional, Dict, List, Tuple

# Global flag for graceful shutdown
running = True


# =============================================================================
# SYMBOL MAPPING CONFIGURATION
# =============================================================================

# CoinGecko uses full names (lowercase)
COINGECKO_SYMBOL_MAP = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'sol': 'solana',
    'ada': 'cardano',
    'xrp': 'ripple',
    'doge': 'dogecoin',
    'dot': 'polkadot',
    'matic': 'polygon',
    'link': 'chainlink',
    'avax': 'avalanche-2',
    'ltc': 'litecoin',
    'uni': 'uniswap',
    'atom': 'cosmos',
    'xlm': 'stellar',
    'algo': 'algorand',
    'near': 'near',
    'ftm': 'fantom',
    'aave': 'aave',
    'bnb': 'binancecoin',
    'shib': 'shiba-inu',
}

# Binance uses uppercase pairs with specific quote currencies
BINANCE_QUOTE_MAP = {
    'usd': 'USDT',   # Binance uses USDT as USD proxy
    'eur': 'EUR',
    'gbp': 'GBP',
    'usdt': 'USDT',
    'usdc': 'USDC',
    'busd': 'BUSD',
}

# Coinbase uses hyphenated pairs
COINBASE_QUOTE_MAP = {
    'usd': 'USD',
    'eur': 'EUR',
    'gbp': 'GBP',
    'usdt': 'USDT',
    'usdc': 'USDC',
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def make_request(url: str, timeout: int = 10) -> Optional[Dict]:
    """
    Make an HTTP GET request and return JSON response.
    
    Args:
        url: The API endpoint URL
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON response as dict, or None if request failed
    """
    headers = {
        'User-Agent': 'CryptoPriceChecker/1.0',
        'Accept': 'application/json',
    }
    
    try:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        if e.code == 429:
            print(f"  ⚠ Rate limited. Please wait before retrying.")
        elif e.code == 404:
            print(f"  ⚠ Symbol not found on this exchange.")
        else:
            print(f"  ⚠ HTTP Error {e.code}: {e.reason}")
        return None
    except URLError as e:
        print(f"  ⚠ Network error: {e.reason}")
        return None
    except json.JSONDecodeError:
        print(f"  ⚠ Invalid response format")
        return None
    except Exception as e:
        print(f"  ⚠ Unexpected error: {str(e)}")
        return None


def format_price(price: float, currency: str = 'usd') -> str:
    """Format price with appropriate currency symbol and formatting."""
    symbols = {
        'usd': '$', 'eur': '€', 'gbp': '£', 
        'usdt': '$', 'usdc': '$', 'busd': '$'
    }
    symbol = symbols.get(currency.lower(), '')
    
    if price >= 1:
        return f"{symbol}{price:,.2f}"
    elif price >= 0.01:
        return f"{symbol}{price:.4f}"
    else:
        return f"{symbol}{price:.8f}"


def get_timestamp() -> str:
    """Get current timestamp in readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# API PROVIDER FUNCTIONS
# =============================================================================

def fetch_coingecko(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """
    Fetch price from CoinGecko API.
    
    CoinGecko is free and doesn't require an API key for basic usage.
    Rate limit: ~10-50 requests/minute for free tier.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., 'btc', 'eth')
        base_currency: Quote currency (e.g., 'usd', 'eur')
        
    Returns:
        Tuple of (price or None, provider name)
    """
    provider = "CoinGecko"
    
    # Map symbol to CoinGecko ID
    coin_id = COINGECKO_SYMBOL_MAP.get(symbol.lower(), symbol.lower())
    currency = base_currency.lower()
    
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={currency}"
    
    data = make_request(url)
    
    if data and coin_id in data and currency in data[coin_id]:
        return data[coin_id][currency], provider
    
    return None, provider


def fetch_binance(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """
    Fetch price from Binance API.
    
    Binance public API doesn't require authentication for market data.
    Rate limit: 1200 requests/minute for IP.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., 'btc', 'eth')
        base_currency: Quote currency (e.g., 'usd', 'eur')
        
    Returns:
        Tuple of (price or None, provider name)
    """
    provider = "Binance"
    
    # Convert to Binance pair format (e.g., BTCUSDT)
    quote = BINANCE_QUOTE_MAP.get(base_currency.lower(), 'USDT')
    pair = f"{symbol.upper()}{quote}"
    
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
    
    data = make_request(url)
    
    if data and 'price' in data:
        try:
            return float(data['price']), provider
        except ValueError:
            return None, provider
    
    return None, provider


def fetch_coinbase(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """
    Fetch price from Coinbase API.
    
    Coinbase public API doesn't require authentication for spot prices.
    Rate limit: 10,000 requests/hour.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., 'btc', 'eth')
        base_currency: Quote currency (e.g., 'usd', 'eur')
        
    Returns:
        Tuple of (price or None, provider name)
    """
    provider = "Coinbase"
    
    # Convert to Coinbase pair format (e.g., BTC-USD)
    quote = COINBASE_QUOTE_MAP.get(base_currency.lower(), 'USD')
    pair = f"{symbol.upper()}-{quote}"
    
    url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
    
    data = make_request(url)
    
    if data and 'data' in data and 'amount' in data['data']:
        try:
            return float(data['data']['amount']), provider
        except ValueError:
            return None, provider
    
    return None, provider


# =============================================================================
# ADDITIONAL PROVIDER TEMPLATES (Easy to extend)
# =============================================================================

def fetch_kraken(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """
    Fetch price from Kraken API (template for extension).
    
    Kraken uses different symbol conventions (XBT for Bitcoin).
    """
    provider = "Kraken"
    
    # Kraken symbol mapping
    kraken_symbols = {'btc': 'XBT', 'doge': 'XDG'}
    kraken_symbol = kraken_symbols.get(symbol.lower(), symbol.upper())
    quote = 'USD' if base_currency.lower() in ['usd', 'usdt'] else base_currency.upper()
    
    pair = f"{kraken_symbol}{quote}"
    url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
    
    data = make_request(url)
    
    if data and 'result' in data and data['result']:
        # Kraken returns nested structure
        for key, value in data['result'].items():
            if 'c' in value:  # 'c' is the last trade closed price
                try:
                    return float(value['c'][0]), provider
                except (ValueError, IndexError):
                    pass
    
    return None, provider


# =============================================================================
# MAIN PRICE AGGREGATION LOGIC
# =============================================================================

def fetch_all_prices(
    symbol: str, 
    base_currency: str = 'usd',
    providers: Optional[List[str]] = None,
    delay: float = 0.1
) -> Dict[str, Optional[float]]:
    """
    Fetch prices from all configured providers.
    
    Args:
        symbol: Cryptocurrency symbol
        base_currency: Quote currency
        providers: List of provider names to query (None = all)
        delay: Delay between requests in seconds (for rate limiting)
        
    Returns:
        Dict mapping provider names to prices (or None if failed)
    """
    # Available provider functions
    all_providers = {
        'coingecko': fetch_coingecko,
        'binance': fetch_binance,
        'coinbase': fetch_coinbase,
        'kraken': fetch_kraken,
    }
    
    # Default to main three providers
    if providers is None:
        providers = ['coingecko', 'binance', 'coinbase']
    
    results = {}
    
    for i, provider_name in enumerate(providers):
        if provider_name.lower() in all_providers:
            fetch_func = all_providers[provider_name.lower()]
            price, name = fetch_func(symbol, base_currency)
            results[name] = price
            
            # Small delay between requests to respect rate limits
            if i < len(providers) - 1 and delay > 0:
                time.sleep(delay)
    
    return results


def display_results(
    symbol: str, 
    base_currency: str, 
    prices: Dict[str, Optional[float]],
    timestamp: str
) -> None:
    """
    Display formatted price results.
    
    Args:
        symbol: Cryptocurrency symbol
        base_currency: Quote currency
        prices: Dict of provider -> price
        timestamp: Fetch timestamp
    """
    print()
    print("=" * 55)
    print(f"  Fetching prices for {symbol.upper()} in {base_currency.upper()}")
    print(f"  Timestamp: {timestamp}")
    print("=" * 55)
    print()
    
    valid_prices = []
    
    for provider, price in prices.items():
        if price is not None:
            formatted = format_price(price, base_currency)
            print(f"  {provider:12}: {formatted}")
            valid_prices.append(price)
        else:
            print(f"  {provider:12}: ⚠ Data unavailable")
    
    print()
    print("-" * 55)
    
    if len(valid_prices) >= 2:
        avg_price = mean(valid_prices)
        formatted_avg = format_price(avg_price, base_currency)
        print(f"  Average across {len(valid_prices)} providers: {formatted_avg}")
        
        # Show price spread
        spread = max(valid_prices) - min(valid_prices)
        spread_pct = (spread / avg_price) * 100 if avg_price > 0 else 0
        print(f"  Price spread: {format_price(spread, base_currency)} ({spread_pct:.3f}%)")
    elif len(valid_prices) == 1:
        print(f"  Only 1 provider returned data (no average available)")
    else:
        print(f"  ⚠ No valid prices retrieved from any provider")
    
    print("=" * 55)
    print()


# =============================================================================
# CSV LOGGING FUNCTIONS
# =============================================================================

def init_csv_file(filepath: str, providers: List[str]) -> None:
    """
    Initialize CSV file with headers if it doesn't exist.
    
    Args:
        filepath: Path to CSV file
        providers: List of provider names for columns
    """
    if not os.path.exists(filepath):
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            headers = ['timestamp', 'symbol', 'base_currency'] + providers + ['average', 'spread', 'spread_pct']
            writer.writerow(headers)
        print(f"  📄 Created CSV file: {filepath}")


def append_to_csv(
    filepath: str,
    timestamp: str,
    symbol: str,
    base_currency: str,
    prices: Dict[str, Optional[float]],
    providers: List[str]
) -> None:
    """
    Append a row of price data to the CSV file.
    
    Args:
        filepath: Path to CSV file
        timestamp: Fetch timestamp
        symbol: Cryptocurrency symbol
        base_currency: Quote currency
        prices: Dict of provider -> price
        providers: Ordered list of provider names
    """
    valid_prices = [p for p in prices.values() if p is not None]
    
    # Calculate stats
    avg_price = mean(valid_prices) if valid_prices else None
    spread = max(valid_prices) - min(valid_prices) if len(valid_prices) >= 2 else None
    spread_pct = (spread / avg_price * 100) if spread and avg_price else None
    
    # Build row in correct column order
    row = [timestamp, symbol.upper(), base_currency.upper()]
    for provider in providers:
        # Find the price for this provider (case-insensitive match)
        price = None
        for p_name, p_value in prices.items():
            if p_name.lower() == provider.lower():
                price = p_value
                break
        row.append(price if price is not None else '')
    
    row.extend([
        f"{avg_price:.8f}" if avg_price else '',
        f"{spread:.8f}" if spread else '',
        f"{spread_pct:.4f}" if spread_pct else ''
    ])
    
    with open(filepath, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(row)


# =============================================================================
# CONTINUOUS MONITORING
# =============================================================================

def signal_handler(signum, frame):
    """Handle interrupt signals for graceful shutdown."""
    global running
    print("\n\n  🛑 Stopping monitoring... (saving final data)")
    running = False


def run_continuous_monitoring(
    symbol: str,
    base_currency: str,
    interval: int = 15,
    csv_file: Optional[str] = None,
    providers: Optional[List[str]] = None,
    delay: float = 0.1
) -> None:
    """
    Continuously fetch prices at specified intervals and log to CSV.
    
    Args:
        symbol: Cryptocurrency symbol
        base_currency: Quote currency
        interval: Seconds between fetches
        csv_file: Path to CSV output file
        providers: List of providers to query
        delay: Delay between API requests
    """
    global running
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Default providers
    if providers is None:
        providers = ['coingecko', 'binance', 'coinbase']
    
    # Provider display names (capitalized)
    provider_names = [p.capitalize() if p != 'coingecko' else 'CoinGecko' for p in providers]
    
    # Generate default CSV filename if not provided
    if csv_file is None:
        csv_file = f"{symbol.lower()}_{base_currency.lower()}_prices.csv"
    
    # Initialize CSV with headers
    init_csv_file(csv_file, provider_names)
    
    print()
    print("=" * 60)
    print(f"  🔄 Starting continuous price monitoring")
    print(f"  Asset: {symbol.upper()}/{base_currency.upper()}")
    print(f"  Interval: {interval} seconds")
    print(f"  CSV File: {csv_file}")
    print(f"  Providers: {', '.join(provider_names)}")
    print("=" * 60)
    print("  Press Ctrl+C to stop monitoring")
    print("=" * 60)
    
    fetch_count = 0
    
    while running:
        fetch_count += 1
        timestamp = get_timestamp()
        
        print(f"\n  [{fetch_count}] Fetching at {timestamp}...", end=" ", flush=True)
        
        # Fetch prices
        prices = fetch_all_prices(
            symbol=symbol,
            base_currency=base_currency,
            providers=providers,
            delay=delay
        )
        
        # Calculate and display quick summary
        valid_prices = [p for p in prices.values() if p is not None]
        
        if valid_prices:
            avg = mean(valid_prices)
            print(f"Avg: {format_price(avg, base_currency)} ({len(valid_prices)}/{len(providers)} providers)")
            
            # Append to CSV
            append_to_csv(csv_file, timestamp, symbol, base_currency, prices, provider_names)
        else:
            print("⚠ No data received")
        
        # Wait for next interval (check running flag periodically for responsive shutdown)
        if running:
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)
    
    print(f"\n  ✅ Monitoring stopped. {fetch_count} data points saved to {csv_file}")
    print()


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def run_demo_mode(symbol: str = 'btc', base_currency: str = 'usd') -> None:
    """
    Run demonstration mode with simulated prices.
    Useful for testing output formatting without network access.
    """
    import random
    
    timestamp = get_timestamp()
    
    # Simulated base prices for demonstration
    base_prices = {
        'btc': 94500.00,
        'eth': 3350.00,
        'sol': 190.00,
        'xrp': 2.15,
        'doge': 0.32,
        'ada': 0.89,
    }
    
    base = base_prices.get(symbol.lower(), 100.00)
    
    # Simulate slight variations between exchanges (realistic spread)
    prices = {
        'CoinGecko': base * (1 + random.uniform(-0.001, 0.001)),
        'Binance': base * (1 + random.uniform(-0.001, 0.001)),
        'Coinbase': base * (1 + random.uniform(-0.001, 0.001)),
    }
    
    print("\n" + "=" * 55)
    print("  *** DEMO MODE - Simulated Prices ***")
    print("=" * 55)
    
    display_results(symbol, base_currency, prices, timestamp)


def run_demo_continuous(
    symbol: str = 'btc',
    base_currency: str = 'usd',
    interval: int = 15,
    csv_file: Optional[str] = None,
    max_iterations: int = 5
) -> None:
    """
    Run demo continuous monitoring with simulated prices.
    Useful for testing CSV logging without network access.
    
    Args:
        symbol: Cryptocurrency symbol
        base_currency: Quote currency
        interval: Seconds between fetches (shortened to 2s in demo)
        csv_file: Path to CSV output file
        max_iterations: Number of demo iterations to run
    """
    import random
    global running
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    providers = ['CoinGecko', 'Binance', 'Coinbase']
    
    # Base prices for simulation
    base_prices = {
        'btc': 94500.00,
        'eth': 3350.00,
        'sol': 190.00,
        'xrp': 2.15,
        'doge': 0.32,
        'ada': 0.89,
    }
    
    base = base_prices.get(symbol.lower(), 100.00)
    
    if csv_file is None:
        csv_file = f"{symbol.lower()}_{base_currency.lower()}_prices.csv"
    
    init_csv_file(csv_file, providers)
    
    print()
    print("=" * 60)
    print("  *** DEMO MODE - Simulated Continuous Monitoring ***")
    print("=" * 60)
    print(f"  Asset: {symbol.upper()}/{base_currency.upper()}")
    print(f"  Interval: 2 seconds (demo)")
    print(f"  CSV File: {csv_file}")
    print(f"  Iterations: {max_iterations}")
    print("=" * 60)
    print("  Press Ctrl+C to stop early")
    print("=" * 60)
    
    fetch_count = 0
    
    while running and fetch_count < max_iterations:
        fetch_count += 1
        timestamp = get_timestamp()
        
        # Simulate price drift over time
        drift = 1 + (fetch_count - 1) * random.uniform(-0.002, 0.002)
        
        prices = {
            'CoinGecko': base * drift * (1 + random.uniform(-0.001, 0.001)),
            'Binance': base * drift * (1 + random.uniform(-0.001, 0.001)),
            'Coinbase': base * drift * (1 + random.uniform(-0.001, 0.001)),
        }
        
        valid_prices = list(prices.values())
        avg = mean(valid_prices)
        
        print(f"\n  [{fetch_count}] {timestamp} | Avg: {format_price(avg, base_currency)}", end="")
        
        for name, price in prices.items():
            print(f" | {name}: {format_price(price, base_currency)}", end="")
        
        print()
        
        append_to_csv(csv_file, timestamp, symbol, base_currency, prices, providers)
        
        if running and fetch_count < max_iterations:
            time.sleep(2)  # Shortened interval for demo
    
    print(f"\n  ✅ Demo complete. {fetch_count} data points saved to {csv_file}")
    print()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Fetch and compare cryptocurrency prices from multiple exchanges.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s btc              Fetch Bitcoin prices in USD (one-time)
  %(prog)s eth eur          Fetch Ethereum prices in EUR
  %(prog)s btc --watch      Continuous monitoring every 15 seconds with CSV logging
  %(prog)s btc --watch --interval 30 --output prices.csv
                            Custom interval and output file
  %(prog)s sol --providers coingecko binance
                            Fetch Solana from specific providers
  %(prog)s btc --demo       Run demo mode with simulated prices

Supported symbols: btc, eth, sol, ada, xrp, doge, dot, matic, link, 
                   avax, ltc, uni, atom, xlm, algo, near, ftm, aave, bnb, shib

Supported currencies: usd, eur, gbp, usdt, usdc
        """
    )
    
    parser.add_argument(
        'symbol',
        type=str,
        help='Cryptocurrency symbol (e.g., btc, eth, sol)'
    )
    
    parser.add_argument(
        'base_currency',
        type=str,
        nargs='?',
        default='usd',
        help='Quote currency (default: usd)'
    )
    
    parser.add_argument(
        '--providers', '-p',
        nargs='+',
        choices=['coingecko', 'binance', 'coinbase', 'kraken'],
        default=None,
        help='Specific providers to query (default: coingecko, binance, coinbase)'
    )
    
    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=0.1,
        help='Delay between API requests in seconds (default: 0.1)'
    )
    
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output results as JSON'
    )
    
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run demo mode with simulated prices (no network required)'
    )
    
    # Continuous monitoring options
    parser.add_argument(
        '--watch', '-w',
        action='store_true',
        help='Enable continuous monitoring mode with CSV logging'
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=15,
        help='Interval between fetches in seconds (default: 15, used with --watch)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output CSV file path (default: {symbol}_{currency}_prices.csv)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Demo mode
    if args.demo:
        if args.watch:
            # Demo continuous monitoring
            run_demo_continuous(
                symbol=args.symbol,
                base_currency=args.base_currency,
                interval=args.interval,
                csv_file=args.output,
                max_iterations=5
            )
        else:
            # Demo single fetch
            run_demo_mode(args.symbol, args.base_currency)
        return
    
    # Continuous monitoring mode
    if args.watch:
        run_continuous_monitoring(
            symbol=args.symbol,
            base_currency=args.base_currency,
            interval=args.interval,
            csv_file=args.output,
            providers=args.providers,
            delay=args.delay
        )
        return
    
    # One-time fetch mode
    timestamp = get_timestamp()
    
    # Fetch prices from all providers
    prices = fetch_all_prices(
        symbol=args.symbol,
        base_currency=args.base_currency,
        providers=args.providers,
        delay=args.delay
    )
    
    if args.json:
        # JSON output mode
        output = {
            'symbol': args.symbol.upper(),
            'base_currency': args.base_currency.upper(),
            'timestamp': timestamp,
            'prices': {k: v for k, v in prices.items()},
            'average': mean([p for p in prices.values() if p]) if any(prices.values()) else None
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        display_results(args.symbol, args.base_currency, prices, timestamp)


if __name__ == '__main__':
    main()
