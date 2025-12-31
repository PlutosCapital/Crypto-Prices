# Cryptocurrency Price Checker

A lightweight, extensible command-line tool for fetching and comparing real-time cryptocurrency prices from multiple exchanges.

## Overview

This tool queries multiple cryptocurrency exchanges simultaneously and displays consolidated price data, helping you:

- Compare prices across exchanges to spot arbitrage opportunities
- Monitor price movements over time with CSV logging
- Track the bid/ask spread between providers
- Build historical price datasets for analysis

## Features

- **Multi-Exchange Support**: Fetches prices from CoinGecko, Binance, and Coinbase (with Kraken as optional)
- **Continuous Monitoring**: Watch mode polls prices at configurable intervals
- **CSV Logging**: Automatically saves price history for later analysis
- **Price Spread Analysis**: Shows the difference between highest and lowest prices
- **Graceful Shutdown**: Press Ctrl+C to stop monitoring and save all data
- **Zero Dependencies**: Uses only Python standard library (no pip install required)
- **Extensible Design**: Easy to add new exchanges or cryptocurrencies

## Installation

No installation required. Simply download the script and run it with Python 3.6+.

```bash
# Download the script
curl -O https://example.com/crypto_price_checker.py

# Or clone the repository
git clone https://github.com/yourusername/crypto-price-checker.git
cd crypto-price-checker

# Verify Python version (3.6+ required)
python3 --version
```

## Quick Start

```bash
# Fetch current Bitcoin price in USD
python3 crypto_price_checker.py btc

# Fetch Ethereum price in EUR
python3 crypto_price_checker.py eth eur

# Start continuous monitoring (every 15 seconds)
python3 crypto_price_checker.py btc --watch
```

## Usage

### Basic Syntax

```
python3 crypto_price_checker.py <symbol> [base_currency] [options]
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `symbol` | Cryptocurrency symbol (btc, eth, sol, etc.) | Required |
| `base_currency` | Quote currency (usd, eur, gbp) | `usd` |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--watch` | `-w` | Enable continuous monitoring with CSV logging |
| `--interval SECONDS` | `-i` | Polling interval in seconds (default: 15) |
| `--output FILE` | `-o` | Custom CSV output path |
| `--providers LIST` | `-p` | Specific providers to query |
| `--delay SECONDS` | `-d` | Delay between API calls (default: 0.1) |
| `--json` | `-j` | Output results as JSON |
| `--demo` | | Run with simulated data (no network) |
| `--help` | `-h` | Show help message |

## Examples

### One-Time Price Fetch

```bash
# Bitcoin in USD (default)
python3 crypto_price_checker.py btc

# Ethereum in EUR
python3 crypto_price_checker.py eth eur

# Solana from specific exchanges only
python3 crypto_price_checker.py sol --providers binance coinbase

# Output as JSON (for scripting)
python3 crypto_price_checker.py btc --json
```

**Sample Output:**
```
=======================================================
  Fetching prices for BTC in USD
  Timestamp: 2025-12-31 18:40:55
=======================================================

  CoinGecko   : $87,485.00
  Binance     : $87,558.75
  Coinbase    : $87,455.95

-------------------------------------------------------
  Average across 3 providers: $87,499.90
  Price spread: $102.80 (0.117%)
=======================================================
```

### Continuous Monitoring

```bash
# Monitor BTC every 15 seconds (default)
python3 crypto_price_checker.py btc --watch

# Monitor ETH every 30 seconds with custom output file
python3 crypto_price_checker.py eth --watch --interval 30 --output eth_prices.csv

# Fast monitoring (5 seconds) with only Binance and Coinbase
python3 crypto_price_checker.py btc --watch --interval 5 --providers binance coinbase
```

**Sample Output:**
```
============================================================
  🔄 Starting continuous price monitoring
  Asset: BTC/USD
  Interval: 15 seconds
  CSV File: btc_usd_prices.csv
  Providers: CoinGecko, Binance, Coinbase
============================================================
  Press Ctrl+C to stop monitoring
============================================================

  [1] Fetching at 2025-12-31 18:40:55... Avg: $87,499.90 (3/3 providers)
  [2] Fetching at 2025-12-31 18:41:10... Avg: $87,512.33 (3/3 providers)
  [3] Fetching at 2025-12-31 18:41:25... Avg: $87,498.01 (3/3 providers)
  ^C

  🛑 Stopping monitoring... (saving final data)
  ✅ Monitoring stopped. 3 data points saved to btc_usd_prices.csv
```

### Demo Mode

Test the tool without making real API calls:

```bash
# Single fetch demo
python3 crypto_price_checker.py btc --demo

# Continuous monitoring demo (runs 5 iterations)
python3 crypto_price_checker.py btc --watch --demo
```

## CSV Output Format

The continuous monitoring mode saves data to a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `timestamp` | Date and time of the fetch (YYYY-MM-DD HH:MM:SS) |
| `symbol` | Cryptocurrency symbol (uppercase) |
| `base_currency` | Quote currency (uppercase) |
| `CoinGecko` | Price from CoinGecko |
| `Binance` | Price from Binance |
| `Coinbase` | Price from Coinbase |
| `average` | Mean price across all providers |
| `spread` | Difference between max and min price |
| `spread_pct` | Spread as percentage of average |

**Example CSV:**
```csv
timestamp,symbol,base_currency,CoinGecko,Binance,Coinbase,average,spread,spread_pct
2025-12-31 18:40:55,BTC,USD,87485.00,87558.75,87455.95,87499.90,102.80,0.1174
2025-12-31 18:41:10,BTC,USD,87512.00,87545.23,87489.12,87515.45,56.11,0.0641
2025-12-31 18:41:25,BTC,USD,87498.00,87533.89,87462.15,87498.01,71.74,0.0820
```

## Supported Assets

### Cryptocurrencies

| Symbol | Name | Symbol | Name |
|--------|------|--------|------|
| `btc` | Bitcoin | `ltc` | Litecoin |
| `eth` | Ethereum | `uni` | Uniswap |
| `sol` | Solana | `atom` | Cosmos |
| `ada` | Cardano | `xlm` | Stellar |
| `xrp` | Ripple | `algo` | Algorand |
| `doge` | Dogecoin | `near` | NEAR Protocol |
| `dot` | Polkadot | `ftm` | Fantom |
| `matic` | Polygon | `aave` | Aave |
| `link` | Chainlink | `bnb` | BNB |
| `avax` | Avalanche | `shib` | Shiba Inu |

### Quote Currencies

| Currency | Description |
|----------|-------------|
| `usd` | US Dollar (default) |
| `eur` | Euro |
| `gbp` | British Pound |
| `usdt` | Tether |
| `usdc` | USD Coin |

## API Rate Limits

Each exchange has different rate limits for their public APIs:

| Provider | Rate Limit | Recommended Min Interval |
|----------|------------|--------------------------|
| **CoinGecko** | 10-30 calls/min (free) | 2-6 seconds |
| **Binance** | 1,200 calls/min | 0.05 seconds |
| **Coinbase** | 10,000 calls/hour | 0.36 seconds |

**Recommendations:**
- For monitoring with all 3 providers: use `--interval 15` or higher
- For faster updates: use `--interval 5 --providers binance coinbase` (skip CoinGecko)
- The script handles rate limit errors (HTTP 429) gracefully with user-friendly messages

## Extending the Tool

### Adding a New Exchange

1. Create a new fetch function following the existing pattern:

```python
def fetch_newexchange(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """
    Fetch price from NewExchange API.
    """
    provider = "NewExchange"
    
    # Build the API URL
    pair = f"{symbol.upper()}-{base_currency.upper()}"
    url = f"https://api.newexchange.com/v1/price/{pair}"
    
    # Make request
    data = make_request(url)
    
    # Parse response (adjust based on API structure)
    if data and 'price' in data:
        try:
            return float(data['price']), provider
        except ValueError:
            return None, provider
    
    return None, provider
```

2. Register the provider in the `fetch_all_prices` function:

```python
all_providers = {
    'coingecko': fetch_coingecko,
    'binance': fetch_binance,
    'coinbase': fetch_coinbase,
    'kraken': fetch_kraken,
    'newexchange': fetch_newexchange,  # Add this line
}
```

3. Update the argument parser choices:

```python
parser.add_argument(
    '--providers', '-p',
    choices=['coingecko', 'binance', 'coinbase', 'kraken', 'newexchange'],
    ...
)
```

### Adding a New Cryptocurrency

Add the symbol mapping to the relevant dictionaries at the top of the script:

```python
COINGECKO_SYMBOL_MAP = {
    ...
    'newcoin': 'newcoin-network',  # CoinGecko ID
}
```

## Troubleshooting

### Common Issues

**"Network error: Connection refused"**
- Check your internet connection
- Verify the exchange API is accessible from your region
- Some exchanges block requests from certain countries

**"Symbol not found on this exchange"**
- Not all exchanges list all cryptocurrencies
- Check if the symbol is supported by the specific exchange
- Try using `--providers` to exclude problematic exchanges

**"Rate limited. Please wait before retrying."**
- Increase the `--interval` value
- Remove CoinGecko from providers for faster polling
- Wait a few minutes before retrying

**"Invalid response format"**
- The exchange API may have changed
- Check for script updates
- Report the issue on GitHub

### Debug Mode

For troubleshooting, you can add verbose output by modifying the `make_request` function to print the full response.

## License

MIT License - feel free to use, modify, and distribute.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests for:
- New exchange integrations
- Additional features (alerts, charts, etc.)
- Bug fixes
- Documentation improvements

## Disclaimer

This tool is for informational purposes only. Cryptocurrency prices are volatile and may differ from actual trading prices. Always verify prices directly with exchanges before making trading decisions. The authors are not responsible for any financial losses incurred through use of this tool.

## Changelog

### v1.0.0 (2025-12-31)
- Initial release
- Support for CoinGecko, Binance, Coinbase, and Kraken
- Continuous monitoring with CSV logging
- Multi-currency support
- Demo mode for testing
