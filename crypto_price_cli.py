import argparse
import json
import time
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests  # type: ignore
except Exception:
    requests = None

import urllib.request
import urllib.error


def http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> Any:
    if requests is not None:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8"))


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().lower()


def normalize_base(base: str) -> str:
    return base.strip().lower()


def gecko_id_for_symbol(symbol: str) -> Optional[str]:
    m = {
        "btc": "bitcoin",
        "xbt": "bitcoin",
        "eth": "ethereum",
        "ltc": "litecoin",
        "doge": "dogecoin",
        "dogecoin": "dogecoin",
        "ada": "cardano",
        "sol": "solana",
        "xrp": "ripple",
        "dot": "polkadot",
        "trx": "tron",
        "uni": "uniswap",
    }
    if symbol in m:
        return m[symbol]
    if symbol in m.values():
        return symbol
    return None


def binance_pair(symbol: str, base: str) -> Optional[str]:
    s = symbol.upper()
    b = base.upper()
    if b == "USD":
        b = "USDT"
    if b in {"USDT", "BUSD", "EUR", "GBP", "TRY"}:
        return f"{s}{b}"
    return None


def coinbase_pair(symbol: str, base: str) -> str:
    return f"{symbol.upper()}-{base.upper()}"


def currency_prefix(base: str) -> str:
    b = base.lower()
    if b == "usd":
        return "$"
    if b == "eur":
        return "€"
    if b == "gbp":
        return "£"
    return f"{base.upper()} "


def format_price(base: str, value: float) -> str:
    p = f"{value:,.2f}"
    if base.lower() in {"usd", "eur", "gbp"}:
        return f"{currency_prefix(base)}{p}"
    return f"{p} {base.upper()}"


def fetch_coingecko(symbol: str, base: str) -> Tuple[Optional[float], Optional[str]]:
    sid = gecko_id_for_symbol(symbol)
    if sid is None:
        return None, "CoinGecko does not recognize symbol"
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={sid}&vs_currencies={base.lower()}"
    try:
        data = http_get_json(url, headers={"Accept": "application/json"})
        v = data.get(sid, {}).get(base.lower())
        if v is None:
            return None, "CoinGecko missing price"
        return float(v), None
    except Exception as e:
        return None, f"CoinGecko error: {e}"


def fetch_binance(symbol: str, base: str) -> Tuple[Optional[float], Optional[str]]:
    pair = binance_pair(symbol, base)
    if pair is None:
        return None, "Binance unsupported base"
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
    try:
        data = http_get_json(url, headers={"Accept": "application/json"})
        p = data.get("price")
        if p is None:
            return None, "Binance missing price"
        return float(p), None
    except Exception as e:
        return None, f"Binance error: {e}"


def fetch_coinbase(symbol: str, base: str) -> Tuple[Optional[float], Optional[str]]:
    pair = coinbase_pair(symbol, base)
    url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
    try:
        data = http_get_json(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "crypto-price-cli/1.0",
            },
        )
        amount = data.get("data", {}).get("amount")
        if amount is None:
            return None, "Coinbase missing price"
        return float(amount), None
    except Exception as e:
        return None, f"Coinbase error: {e}"


def collect_prices(symbol: str, base: str, delay: float = 0.0) -> List[Dict[str, Any]]:
    providers = [
        ("CoinGecko", fetch_coingecko),
        ("Binance", fetch_binance),
        ("Coinbase", fetch_coinbase),
    ]
    out: List[Dict[str, Any]] = []
    for name, fn in providers:
        t = datetime.now()
        price, err = fn(symbol, base)
        out.append(
            {
                "provider": name,
                "price": price,
                "error": err,
                "timestamp": t,
            }
        )
        if delay > 0.0:
            time.sleep(delay)
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="crypto-price-cli",
        description="Fetch real-time crypto prices from multiple providers",
    )
    p.add_argument("symbol", type=str, help="Asset symbol, e.g., btc, eth")
    p.add_argument(
        "--base",
        type=str,
        default="usd",
        help="Quote currency, default usd",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Optional delay between provider requests in seconds",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sym = normalize_symbol(args.symbol)
    base = normalize_base(args.base)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_symbol = args.symbol.upper()
    header_base = args.base.upper()
    print(f"Fetching prices for {header_symbol} in {header_base} at {now}")
    results = collect_prices(sym, base, delay=args.delay)
    valid_prices = []
    for r in results:
        name = r["provider"]
        ts = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        if r["price"] is not None:
            print(f"{name}: {format_price(base, r['price'])} ({ts})")
            valid_prices.append(r["price"])
        else:
            print(f"{name}: unavailable ({r['error']})")
    if len(valid_prices) >= 2:
        avg = mean(valid_prices)
        print(f"Average across providers: {format_price(base, avg)}")


if __name__ == "__main__":
    main()

