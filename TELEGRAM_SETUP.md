# Telegram Alert Bot Setup Guide

## 🚀 Quick Setup (5 minutes)

### Step 1: Create Your Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "My Crypto Alerts")
4. Choose a username (must end in `bot`, e.g., `my_crypto_alerts_bot`)
5. **Copy the token** — looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

![BotFather Screenshot](https://core.telegram.org/file/811140327/1/zlN4goPTupk/9ff2f2f01c4bd1b013)

### Step 2: Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Send `/start`
3. **Copy your ID** — a number like `123456789`

### Step 3: Start a Chat With Your Bot

1. Search for your bot's username (e.g., `@my_crypto_alerts_bot`)
2. Press **Start** or send `/start`
3. This is required before the bot can message you!

### Step 4: Test the Connection

```bash
python3 telegram_alerts.py btc --token YOUR_TOKEN --chat YOUR_CHAT_ID --test
```

You should receive a test message in Telegram. ✅

---

## 📱 Usage Examples

### Basic Monitoring
```bash
# Monitor BTC with default settings (spread > 0.3% alerts)
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID
```

### Price Level Alerts
```bash
# Alert when BTC goes above $100,000
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID --price-above 100000

# Alert when ETH drops below $3,000
python3 telegram_alerts.py eth --token TOKEN --chat CHAT_ID --price-below 3000

# Both directions
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID \
    --price-above 100000 --price-below 80000
```

### Spread Arbitrage Alerts
```bash
# Alert when spread exceeds 0.5%
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID --spread-alert 0.5

# More sensitive (0.2% spread)
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID --spread-alert 0.2
```

### Price Movement Alerts
```bash
# Alert on 3% moves within 10 minutes
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID \
    --change-alert 3.0 --change-window 600
```

### Adjust Timing
```bash
# Check every 30 seconds, 10-minute cooldown between alerts
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID \
    --interval 30 --cooldown 600
```

---

## 🔧 Using Environment Variables

To avoid typing your token every time:

```bash
# Add to ~/.bashrc or ~/.zshrc
export TELEGRAM_BOT_TOKEN='123456789:ABCdefGHIjklMNOpqrsTUVwxyz'
export TELEGRAM_CHAT_ID='987654321'

# Then simply run:
python3 telegram_alerts.py btc
```

---

## 🖥️ Run in Background (24/7 Monitoring)

### Option 1: Using nohup
```bash
nohup python3 telegram_alerts.py btc \
    --token TOKEN --chat CHAT_ID \
    --spread-alert 0.3 --price-above 100000 \
    > alerts.log 2>&1 &

# Check if running
pgrep -fl telegram_alerts

# View logs
tail -f alerts.log

# Stop
pkill -f telegram_alerts
```

### Option 2: Using screen
```bash
# Start a screen session
screen -S crypto_alerts

# Run the bot
python3 telegram_alerts.py btc --token TOKEN --chat CHAT_ID

# Detach: Press Ctrl+A, then D
# Reattach later: screen -r crypto_alerts
```

### Option 3: Using systemd (Linux server)

Create `/etc/systemd/system/crypto-alerts.service`:
```ini
[Unit]
Description=Crypto Price Alerts Bot
After=network.target

[Service]
Type=simple
User=your_username
Environment="TELEGRAM_BOT_TOKEN=your_token"
Environment="TELEGRAM_CHAT_ID=your_chat_id"
ExecStart=/usr/bin/python3 /path/to/telegram_alerts.py btc --spread-alert 0.3
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable crypto-alerts
sudo systemctl start crypto-alerts
sudo systemctl status crypto-alerts
```

---

## 📊 Alert Types

| Alert | Trigger | Use Case |
|-------|---------|----------|
| **Spread Alert** | Exchange price difference > X% | Arbitrage opportunities |
| **Price Above** | Average price > target | Take profit signals |
| **Price Below** | Average price < target | Buy opportunities, stop loss |
| **Price Change** | X% move in Y minutes | Volatility alerts |

---

## 📨 Sample Alert Messages

### Spread Alert
```
📊 SPREAD ALERT — BTC/USD

Spread: 0.47%

💰 Buy on Coinbase: $87,234.00
💸 Sell on Binance: $87,645.12

Difference: $411.12
Net profit (after ~0.2% fees): $236.65 per BTC

All Prices:
• CoinGecko: $87,456.00
• Binance: $87,645.12
• Coinbase: $87,234.00

2025-12-31 14:32:05
```

### Price Above Alert
```
🟢 PRICE ABOVE $100,000 — BTC

Current Price: $100,234.56
Threshold: $100,000.00

BTC has broken above your target! 🚀

2025-12-31 14:32:05
```

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| "Chat not found" | Make sure you started a chat with your bot first! |
| "Unauthorized" | Check your bot token is correct |
| No messages received | Verify chat ID, try @userinfobot again |
| Rate limited | Increase `--interval` and `--cooldown` |
| Bot stops unexpectedly | Check logs, use systemd for auto-restart |

---

## 🔒 Security Tips

1. **Never share your bot token** — anyone with it can control your bot
2. **Don't commit tokens to git** — use environment variables
3. **Your chat ID is semi-private** — not secret, but don't share publicly
4. **Consider a dedicated bot** for alerts (not one you use for other things)

---

## 📚 Full Command Reference

```
python3 telegram_alerts.py --help

positional arguments:
  symbol               Cryptocurrency symbol (btc, eth, sol)
  base_currency        Quote currency (default: usd)

options:
  --token, -t          Telegram bot token
  --chat, -c           Telegram chat ID
  --spread-alert       Spread threshold % (default: 0.3)
  --price-above        Alert when price exceeds this
  --price-below        Alert when price drops below this
  --change-alert       Price change % to trigger (default: 2.0)
  --change-window      Window for price change in seconds (default: 300)
  --interval, -i       Check interval in seconds (default: 15)
  --cooldown           Cooldown between alerts in seconds (default: 300)
  --delay, -d          Delay between API calls (default: 0.2)
  --test               Send test message and exit
```
