# Coinbase Crypto Trading Bot

A modular Python trading bot for cryptocurrency trading on Coinbase using the official Coinbase Advanced Trade API.

## Features

- **CLI Interface**: Buy/sell cryptocurrencies directly from command line
- **Modular Strategies**: SMA Crossover, RSI, and Volatility Breakout algorithms
- **Sandbox Support**: Test strategies safely in sandbox environment
- **Risk Management**: Position sizing and stop-loss mechanisms
- **Real-time Data**: Live price feeds and technical indicators
- **Backtesting**: Test strategies against historical data

## Quick Setup

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env with your Coinbase Advanced Trade API credentials
```

### 3. Basic Usage

```bash
# Get account balance
crypto-bot balance

# Get current price
crypto-bot price BTC-USD

# Buy cryptocurrency (dry run)
crypto-bot buy BTC-USD 100 --dry-run

# Sell cryptocurrency (dry run)
crypto-bot sell BTC-USD 0.001 --dry-run

# Run trading strategy
crypto-bot strategy run sma_crossover BTC-USD --amount 1000 --dry-run

# Check system health
crypto-bot health
```

## Available Strategies

### 1. SMA Crossover
- **Logic**: Buys when short-term MA crosses above long-term MA
- **Parameters**: `short_window`, `long_window`
- **Best for**: Trending markets

### 2. RSI Strategy  
- **Logic**: Buys when RSI < 30, sells when RSI > 70
- **Parameters**: `rsi_period`, `oversold_threshold`, `overbought_threshold`
- **Best for**: Range-bound markets

### 3. Volatility Breakout
- **Logic**: Trades on price breakouts from volatility bands
- **Parameters**: `lookback_period`, `volatility_multiplier`
- **Best for**: High volatility periods

## Configuration

Edit `config/config.yaml` and `config/strategies.yaml` to customize trading parameters and strategy settings.

## Security

- Always start with `COINBASE_SANDBOX=true` for testing
- Never commit API keys to git
- Use environment variables for credentials
- Test thoroughly before live trading
- Set appropriate position limits

## Disclaimer

⚠️ **WARNING**: Cryptocurrency trading involves substantial risk of loss. This bot is for educational purposes. Always:
- Start with small amounts
- Test in sandbox environment  
- Never invest more than you can afford to lose
- Understand the risks involved
