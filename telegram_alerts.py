#!/usr/bin/env python3
"""
Cryptocurrency Price Alert Bot for Telegram

Monitors prices and sends alerts to Telegram when:
- Spread between exchanges exceeds threshold
- Price crosses above/below target levels
- Significant price movements occur

Setup:
    1. Create a bot via @BotFather on Telegram
    2. Get your bot token
    3. Get your chat ID (send /start to @userinfobot)
    4. Run: python3 telegram_alerts.py --token YOUR_TOKEN --chat YOUR_CHAT_ID

Usage:
    python3 telegram_alerts.py btc --token BOT_TOKEN --chat CHAT_ID
    python3 telegram_alerts.py btc --spread-alert 0.3 --price-above 100000
    python3 telegram_alerts.py eth --price-below 3000 --interval 30
"""

import os
import sys
import json
import time
import signal
import argparse
from datetime import datetime
from statistics import mean
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AlertConfig:
    """Configuration for price alerts."""
    spread_threshold: float = 0.3          # Alert if spread exceeds this %
    price_above: Optional[float] = None    # Alert if price goes above
    price_below: Optional[float] = None    # Alert if price goes below
    price_change_pct: float = 2.0          # Alert on X% change in window
    price_change_window: int = 300         # Window for price change (seconds)
    cooldown_seconds: int = 300            # Min time between same alert type
    status_interval: Optional[int] = None  # Send status every X seconds (None = disabled)
    
@dataclass
class AlertState:
    """Track alert state to prevent spam."""
    last_spread_alert: float = 0
    last_price_above_alert: float = 0
    last_price_below_alert: float = 0
    last_price_change_alert: float = 0
    last_status_update: float = 0
    price_history: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, price)


# =============================================================================
# SYMBOL MAPPINGS (from main script)
# =============================================================================

COINGECKO_SYMBOL_MAP = {
    'btc': 'bitcoin', 'eth': 'ethereum', 'sol': 'solana',
    'ada': 'cardano', 'xrp': 'ripple', 'doge': 'dogecoin',
    'dot': 'polkadot', 'matic': 'polygon', 'link': 'chainlink',
    'avax': 'avalanche-2', 'ltc': 'litecoin', 'uni': 'uniswap',
    'bnb': 'binancecoin', 'shib': 'shiba-inu',
}

BINANCE_QUOTE_MAP = {'usd': 'USDT', 'eur': 'EUR', 'gbp': 'GBP'}
COINBASE_QUOTE_MAP = {'usd': 'USD', 'eur': 'EUR', 'gbp': 'GBP'}


# =============================================================================
# TELEGRAM API
# =============================================================================

class TelegramBot:
    """Simple Telegram bot using only standard library."""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured chat."""
        url = f"{self.base_url}/sendMessage"
        
        payload = json.dumps({
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }).encode('utf-8')
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'CryptoAlertBot/1.0'
        }
        
        try:
            request = Request(url, data=payload, headers=headers, method='POST')
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get('ok', False)
        except Exception as e:
            print(f"  ⚠ Telegram error: {e}")
            return False
    
    def send_alert(self, title: str, body: str, emoji: str = "🚨") -> bool:
        """Send a formatted alert message."""
        message = f"{emoji} <b>{title}</b>\n\n{body}\n\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        return self.send_message(message)
    
    def send_startup_message(self, symbol: str, config: AlertConfig) -> bool:
        """Send a message when bot starts monitoring."""
        alerts = []
        if config.spread_threshold:
            alerts.append(f"• Spread > {config.spread_threshold}%")
        if config.price_above:
            alerts.append(f"• Price > ${config.price_above:,.2f}")
        if config.price_below:
            alerts.append(f"• Price < ${config.price_below:,.2f}")
        if config.price_change_pct:
            alerts.append(f"• {config.price_change_pct}% move in {config.price_change_window//60}min")
        
        status_info = f"\n<b>Status updates:</b> Every {config.status_interval}s" if config.status_interval else ""
        
        message = f"""🤖 <b>Crypto Alert Bot Started</b>

<b>Monitoring:</b> {symbol.upper()}
<b>Active Alerts:</b>
{chr(10).join(alerts)}

<b>Cooldown:</b> {config.cooldown_seconds}s between alerts{status_info}

Send /stop to this chat to receive shutdown confirmation."""
        
        return self.send_message(message)


# =============================================================================
# PRICE FETCHING (from main script)
# =============================================================================

def make_request(url: str, timeout: int = 10) -> Optional[Dict]:
    """Make an HTTP GET request and return JSON response."""
    headers = {'User-Agent': 'CryptoAlertBot/1.0', 'Accept': 'application/json'}
    
    try:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        return None


def fetch_coingecko(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """Fetch price from CoinGecko."""
    coin_id = COINGECKO_SYMBOL_MAP.get(symbol.lower(), symbol.lower())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={base_currency}"
    data = make_request(url)
    if data and coin_id in data and base_currency in data[coin_id]:
        return data[coin_id][base_currency], "CoinGecko"
    return None, "CoinGecko"


def fetch_binance(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """Fetch price from Binance."""
    quote = BINANCE_QUOTE_MAP.get(base_currency.lower(), 'USDT')
    pair = f"{symbol.upper()}{quote}"
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
    data = make_request(url)
    if data and 'price' in data:
        try:
            return float(data['price']), "Binance"
        except ValueError:
            pass
    return None, "Binance"


def fetch_coinbase(symbol: str, base_currency: str = 'usd') -> Tuple[Optional[float], str]:
    """Fetch price from Coinbase."""
    quote = COINBASE_QUOTE_MAP.get(base_currency.lower(), 'USD')
    pair = f"{symbol.upper()}-{quote}"
    url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
    data = make_request(url)
    if data and 'data' in data and 'amount' in data['data']:
        try:
            return float(data['data']['amount']), "Coinbase"
        except ValueError:
            pass
    return None, "Coinbase"


def fetch_all_prices(symbol: str, base_currency: str = 'usd', delay: float = 0.1) -> Dict[str, Optional[float]]:
    """Fetch prices from all providers."""
    providers = [
        ('CoinGecko', fetch_coingecko),
        ('Binance', fetch_binance),
        ('Coinbase', fetch_coinbase),
    ]
    
    results = {}
    for name, fetch_func in providers:
        price, _ = fetch_func(symbol, base_currency)
        results[name] = price
        time.sleep(delay)
    
    return results


# =============================================================================
# ALERT LOGIC
# =============================================================================

def check_spread_alert(
    prices: Dict[str, Optional[float]], 
    config: AlertConfig, 
    state: AlertState,
    bot: TelegramBot,
    symbol: str,
    currency: str
) -> bool:
    """Check if spread exceeds threshold and send alert."""
    valid_prices = {k: v for k, v in prices.items() if v is not None}
    
    if len(valid_prices) < 2:
        return False
    
    price_list = list(valid_prices.values())
    spread = max(price_list) - min(price_list)
    avg_price = mean(price_list)
    spread_pct = (spread / avg_price) * 100
    
    # Check threshold
    if spread_pct < config.spread_threshold:
        return False
    
    # Check cooldown
    now = time.time()
    if now - state.last_spread_alert < config.cooldown_seconds:
        return False
    
    # Find min/max exchanges
    min_exchange = min(valid_prices, key=valid_prices.get)
    max_exchange = max(valid_prices, key=valid_prices.get)
    min_price = valid_prices[min_exchange]
    max_price = valid_prices[max_exchange]
    
    # Calculate potential profit
    # Assume 0.1% fee per trade (buy + sell = 0.2%)
    fee_pct = 0.2
    net_profit_pct = spread_pct - fee_pct
    net_profit_usd = (net_profit_pct / 100) * avg_price
    
    body = f"""<b>Spread: {spread_pct:.3f}%</b>

💰 <b>Buy on {min_exchange}:</b> ${min_price:,.2f}
💸 <b>Sell on {max_exchange}:</b> ${max_price:,.2f}

<b>Difference:</b> ${spread:,.2f}
<b>Net profit (after ~0.2% fees):</b> ${net_profit_usd:,.2f} per {symbol.upper()}

<b>All Prices:</b>
{chr(10).join(f'• {k}: ${v:,.2f}' for k, v in valid_prices.items())}"""
    
    if bot.send_alert(f"SPREAD ALERT — {symbol.upper()}/{currency.upper()}", body, "📊"):
        state.last_spread_alert = now
        print(f"  📊 Spread alert sent! ({spread_pct:.3f}%)")
        return True
    
    return False


def check_price_threshold_alerts(
    avg_price: float,
    config: AlertConfig,
    state: AlertState,
    bot: TelegramBot,
    symbol: str,
    currency: str
) -> bool:
    """Check if price crossed above/below thresholds."""
    now = time.time()
    sent = False
    
    # Price above alert
    if config.price_above and avg_price > config.price_above:
        if now - state.last_price_above_alert >= config.cooldown_seconds:
            body = f"""<b>Current Price:</b> ${avg_price:,.2f}
<b>Threshold:</b> ${config.price_above:,.2f}

{symbol.upper()} has broken above your target! 🚀"""
            
            if bot.send_alert(f"PRICE ABOVE ${config.price_above:,.0f} — {symbol.upper()}", body, "🟢"):
                state.last_price_above_alert = now
                print(f"  🟢 Price above alert sent!")
                sent = True
    
    # Price below alert
    if config.price_below and avg_price < config.price_below:
        if now - state.last_price_below_alert >= config.cooldown_seconds:
            body = f"""<b>Current Price:</b> ${avg_price:,.2f}
<b>Threshold:</b> ${config.price_below:,.2f}

{symbol.upper()} has dropped below your target! ⚠️"""
            
            if bot.send_alert(f"PRICE BELOW ${config.price_below:,.0f} — {symbol.upper()}", body, "🔴"):
                state.last_price_below_alert = now
                print(f"  🔴 Price below alert sent!")
                sent = True
    
    return sent


def check_price_change_alert(
    avg_price: float,
    config: AlertConfig,
    state: AlertState,
    bot: TelegramBot,
    symbol: str,
    currency: str
) -> bool:
    """Check for significant price changes over time window."""
    now = time.time()
    
    # Add current price to history
    state.price_history.append((now, avg_price))
    
    # Remove old entries outside window
    cutoff = now - config.price_change_window
    state.price_history = [(t, p) for t, p in state.price_history if t > cutoff]
    
    # Need at least 2 data points
    if len(state.price_history) < 2:
        return False
    
    # Calculate change from oldest to newest
    oldest_price = state.price_history[0][1]
    change_pct = ((avg_price - oldest_price) / oldest_price) * 100
    
    # Check if change exceeds threshold
    if abs(change_pct) < config.price_change_pct:
        return False
    
    # Check cooldown
    if now - state.last_price_change_alert < config.cooldown_seconds:
        return False
    
    direction = "📈 UP" if change_pct > 0 else "📉 DOWN"
    emoji = "🚀" if change_pct > 0 else "🔻"
    
    body = f"""<b>Change: {change_pct:+.2f}%</b>

<b>From:</b> ${oldest_price:,.2f}
<b>To:</b> ${avg_price:,.2f}
<b>Time window:</b> {config.price_change_window // 60} minutes

Significant {direction.split()[1].lower()} movement detected!"""
    
    if bot.send_alert(f"{direction} {abs(change_pct):.1f}% — {symbol.upper()}", body, emoji):
        state.last_price_change_alert = now
        print(f"  {emoji} Price change alert sent! ({change_pct:+.2f}%)")
        return True
    
    return False


def send_status_update(
    prices: Dict[str, Optional[float]],
    avg_price: float,
    spread_pct: float,
    config: AlertConfig,
    state: AlertState,
    bot: TelegramBot,
    symbol: str,
    currency: str
) -> bool:
    """Send periodic status update to Telegram."""
    if config.status_interval is None:
        return False
    
    now = time.time()
    
    # Check if it's time for a status update
    if now - state.last_status_update < config.status_interval:
        return False
    
    valid_prices = {k: v for k, v in prices.items() if v is not None}
    
    # Build price list
    price_lines = []
    for provider, price in valid_prices.items():
        price_lines.append(f"• {provider}: ${price:,.2f}")
    
    # Calculate min/max for arbitrage info
    if len(valid_prices) >= 2:
        min_exchange = min(valid_prices, key=valid_prices.get)
        max_exchange = max(valid_prices, key=valid_prices.get)
        arb_info = f"\n💡 <b>Buy:</b> {min_exchange} → <b>Sell:</b> {max_exchange}"
    else:
        arb_info = ""
    
    message = f"""📊 <b>{symbol.upper()}/{currency.upper()} Status</b>

<b>Average:</b> ${avg_price:,.2f}
<b>Spread:</b> {spread_pct:.3f}%

<b>Prices:</b>
{chr(10).join(price_lines)}{arb_info}

<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"""
    
    if bot.send_message(message):
        state.last_status_update = now
        print(f" 📤")
        return True
    
    return False


# =============================================================================
# MAIN MONITORING LOOP
# =============================================================================

running = True

def signal_handler(signum, frame):
    global running
    print("\n  🛑 Shutting down...")
    running = False

def format_price(price: float, currency: str = 'usd') -> str:
    """Format price with currency symbol."""
    symbols = {'usd': '$', 'eur': '€', 'gbp': '£'}
    symbol = symbols.get(currency.lower(), '$')
    if price >= 1:
        return f"{symbol}{price:,.2f}"
    else:
        return f"{symbol}{price:.6f}"


def run_alert_monitor(
    symbol: str,
    base_currency: str,
    bot: TelegramBot,
    config: AlertConfig,
    interval: int = 15,
    delay: float = 0.1
) -> None:
    """Main monitoring loop with alerts."""
    global running
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    state = AlertState()
    
    # Send startup message
    bot.send_startup_message(symbol, config)
    
    print()
    print("=" * 60)
    print(f"  🤖 Telegram Alert Bot Started")
    print("=" * 60)
    print(f"  Asset: {symbol.upper()}/{base_currency.upper()}")
    print(f"  Interval: {interval}s")
    print(f"  Spread threshold: {config.spread_threshold}%")
    if config.price_above:
        print(f"  Alert if above: ${config.price_above:,.2f}")
    if config.price_below:
        print(f"  Alert if below: ${config.price_below:,.2f}")
    print(f"  Change alert: {config.price_change_pct}% in {config.price_change_window//60}min")
    print(f"  Cooldown: {config.cooldown_seconds}s")
    if config.status_interval:
        print(f"  Status updates: Every {config.status_interval}s")
    print("=" * 60)
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    fetch_count = 0
    alerts_sent = 0
    
    while running:
        fetch_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Fetch prices
        prices = fetch_all_prices(symbol, base_currency, delay)
        valid_prices = [p for p in prices.values() if p is not None]
        
        if not valid_prices:
            print(f"  [{timestamp}] ⚠ No data received")
            time.sleep(interval)
            continue
        
        avg_price = mean(valid_prices)
        spread_pct = ((max(valid_prices) - min(valid_prices)) / avg_price) * 100 if len(valid_prices) > 1 else 0
        
        # Display current status
        print(f"  [{timestamp}] {format_price(avg_price, base_currency)} | Spread: {spread_pct:.3f}% | Alerts: {alerts_sent}", end="")
        
        # Check all alert conditions
        alert_sent = False
        
        if check_spread_alert(prices, config, state, bot, symbol, base_currency):
            alerts_sent += 1
            alert_sent = True
        
        if check_price_threshold_alerts(avg_price, config, state, bot, symbol, base_currency):
            alerts_sent += 1
            alert_sent = True
        
        if check_price_change_alert(avg_price, config, state, bot, symbol, base_currency):
            alerts_sent += 1
            alert_sent = True
        
        # Send periodic status update
        if send_status_update(prices, avg_price, spread_pct, config, state, bot, symbol, base_currency):
            pass  # Already printed in function
        elif not alert_sent:
            print()  # End the line if no alert or status
        
        # Wait for next interval
        if running:
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)
    
    # Send shutdown message
    bot.send_message(f"🛑 <b>Alert Bot Stopped</b>\n\nMonitored {symbol.upper()} for {fetch_count} intervals.\nTotal alerts sent: {alerts_sent}")
    print(f"\n  ✅ Bot stopped. {alerts_sent} alerts sent in {fetch_count} checks.")


# =============================================================================
# CLI
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Telegram alert bot for cryptocurrency prices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Setup Instructions:
  1. Open Telegram and search for @BotFather
  2. Send /newbot and follow the instructions
  3. Copy the bot token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
  4. Search for @userinfobot and send /start to get your chat ID
  5. Start a chat with your new bot (search its username)
  6. Run this script with your token and chat ID

Examples:
  %(prog)s btc --token YOUR_TOKEN --chat YOUR_CHAT_ID
  %(prog)s btc --spread-alert 0.5 --price-above 100000
  %(prog)s eth --price-below 3000 --cooldown 600

Environment Variables:
  TELEGRAM_BOT_TOKEN    Bot token (alternative to --token)
  TELEGRAM_CHAT_ID      Chat ID (alternative to --chat)
        """
    )
    
    parser.add_argument('symbol', help='Cryptocurrency symbol (btc, eth, sol)')
    parser.add_argument('base_currency', nargs='?', default='usd', help='Quote currency (default: usd)')
    
    # Telegram config
    parser.add_argument('--token', '-t', help='Telegram bot token (or set TELEGRAM_BOT_TOKEN)')
    parser.add_argument('--chat', '-c', help='Telegram chat ID (or set TELEGRAM_CHAT_ID)')
    
    # Alert thresholds
    parser.add_argument('--spread-alert', type=float, default=0.3, help='Spread threshold %% (default: 0.3)')
    parser.add_argument('--price-above', type=float, help='Alert when price exceeds this value')
    parser.add_argument('--price-below', type=float, help='Alert when price drops below this value')
    parser.add_argument('--change-alert', type=float, default=2.0, help='Price change %% to trigger alert (default: 2.0)')
    parser.add_argument('--change-window', type=int, default=300, help='Window for price change in seconds (default: 300)')
    
    # Timing
    parser.add_argument('--interval', '-i', type=int, default=15, help='Check interval in seconds (default: 15)')
    parser.add_argument('--cooldown', type=int, default=300, help='Cooldown between same alerts in seconds (default: 300)')
    parser.add_argument('--delay', '-d', type=float, default=0.2, help='Delay between API calls (default: 0.2)')
    parser.add_argument('--status-interval', '-s', type=int, default=None, 
                        help='Send status update every X seconds (default: disabled)')
    
    # Test mode
    parser.add_argument('--test', action='store_true', help='Send a test message and exit')
    
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    # Get token and chat ID from args or environment
    token = args.token or os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = args.chat or os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ Error: Telegram bot token and chat ID are required.")
        print()
        print("Provide them via arguments:")
        print("  --token YOUR_BOT_TOKEN --chat YOUR_CHAT_ID")
        print()
        print("Or set environment variables:")
        print("  export TELEGRAM_BOT_TOKEN='your_token'")
        print("  export TELEGRAM_CHAT_ID='your_chat_id'")
        print()
        print("Run with --help for setup instructions.")
        sys.exit(1)
    
    # Create bot
    bot = TelegramBot(token, chat_id)
    
    # Test mode
    if args.test:
        print("📤 Sending test message...")
        success = bot.send_alert(
            "Test Alert",
            f"✅ Your Telegram alert bot is configured correctly!\n\nReady to monitor {args.symbol.upper()}/{args.base_currency.upper()}",
            "🧪"
        )
        if success:
            print("✅ Test message sent successfully!")
        else:
            print("❌ Failed to send test message. Check your token and chat ID.")
        sys.exit(0 if success else 1)
    
    # Create config
    config = AlertConfig(
        spread_threshold=args.spread_alert,
        price_above=args.price_above,
        price_below=args.price_below,
        price_change_pct=args.change_alert,
        price_change_window=args.change_window,
        cooldown_seconds=args.cooldown,
        status_interval=args.status_interval,
    )
    
    # Run monitor
    run_alert_monitor(
        symbol=args.symbol,
        base_currency=args.base_currency,
        bot=bot,
        config=config,
        interval=args.interval,
        delay=args.delay,
    )


if __name__ == '__main__':
    main()
