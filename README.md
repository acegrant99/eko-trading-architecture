# Eko Trading Architecture

Autonomous crypto trading system with **Eko** as the controller.

> ⚠️ **Live trading involves real money and real risk.**  
> Paper mode is the default. Live mode is opt-in and requires explicit activation.

## Features
- Live market data (Coinbase public ticker + CoinGecko + DexScreener)
- SMA crossover strategy
- Risk-first gate (kill switch, position limits, confidence floor, daily loss limit)
- **Paper execution** (default) with position tracking
- **Live execution** via Coinbase Advanced Trade API
- Natural-language Eko commands
- Dark dashboard UI

## Architecture
```
Data → Strategy → Risk Gate → Execution (Paper | Live) → Monitoring
         ↑
    EkoController (mode switch + conscience + memory)
```

## Quick Start (Paper)
```bash
pip install -r requirements.txt
python server.py
# open http://localhost:8000
```

## Live Trading Setup

1. Create a **Coinbase Advanced Trade** API key (CDP / Coinbase Developer Platform):
   - https://portal.cdp.coinbase.com/
   - Create an API key with **Trade** permission
   - Prefer **ECDSA** keys if using the official Python SDK

2. Export the keys (never commit them):
```bash
export COINBASE_API_KEY="organizations/..."