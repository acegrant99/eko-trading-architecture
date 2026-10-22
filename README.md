# Eko Trading Architecture

Autonomous crypto trading system with **Eko** as the controller.

> ⚠️ **Live trading involves real money and real risk.**  
> Paper mode is the default. Live mode is opt-in.

## Features
- Live market data (Coinbase + CoinGecko + DexScreener)
- SMA crossover strategy
- Risk-first gate with **tighter live-only rules**
- Paper execution (default)
- **Live execution** via Coinbase Advanced Trade
  - Market **and** Limit (GTC) orders
  - Position / balance sync from Coinbase
  - Cancel-all open orders
- Natural-language commands
- Dark dashboard UI with PAPER / LIVE badge

## Architecture
```
Data → Strategy → Risk Gate → Execution (Paper | Live) → Monitoring
         ↑
    EkoController (mode · limit preference · conscience · memory)
```

## Quick Start (Paper)
```bash
pip install -r requirements.txt
python server.py
# http://localhost:8000
```

## Live Trading Setup

1. Create a Coinbase Advanced Trade API key (Trade permission) at  
   https://portal.cdp.coinbase.com/  
   Prefer **ECDSA** keys for the official Python SDK.

2. Set environment variables (never commit them):
```bash
export COINBASE_API_KEY="organizations/.../apiKeys/..."
export COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----
...
-----END EC PRIVATE KEY-----
"
```
Or copy `.env.example` → `.env`.

3. Start the server and in the UI chat type:
```
live
```
Eko will sync balances/positions before enabling live mode.

## Safety Controls
| Control | Description |
|---------|-------------|
| Paper default | Always starts in paper |
| Explicit `live` | Required after keys are set |
| Kill switch | Blocks all new orders instantly |
| Live risk tighten | Smaller size %, lower daily loss, higher confidence, $ notional cap |
| Prefer limit | Autonomous live ticks prefer passive limit orders |
| Hard size cap | Autonomous live ticks capped to very small size |
| `cancel all` | Cancels open Coinbase orders |
| `sync` | Re-pulls balances & positions |

## Commands
| Command | Action |
|---------|--------|
| `status` | Full status |
| `live` / `paper` | Switch mode |
| `kill switch` / `kill switch off` | Emergency halt |
| `sync` | Refresh Coinbase positions |
| `cancel all` | Cancel open orders |
| `force buy` / `force sell` | Manual trade |
| `limit buy` / `limit sell` | Manual limit trade |
| `prefer limit` / `prefer market` | Default order type |
| `accounts` | Real balances (live) |
| `remember …` / `recall` | Memory |
| `search solana` | CoinGecko search |
| `market memory BTC` | Live ticker |

## Project Layout
```
├── data/
├── strategy/
├── risk/
├── execution/
│   ├── paper_executor.py
│   ├── live_executor.py
│   └── trade_logger.py
├── ui/
├── eko_controller.py
├── server.py
├── requirements.txt
└── .env.example
```

## Warnings
- Start with the smallest possible sizes.
- Test thoroughly in paper mode first.
- Experimental software — use at your own risk.
- Never commit API keys or `.env`.
