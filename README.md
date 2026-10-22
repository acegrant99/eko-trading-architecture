# Eko Trading Architecture

Autonomous crypto trading system with **Eko** as the controller.

> ⚠️ **Live trading involves real money and real risk.**  
> Paper mode is the default. Live mode is opt-in and requires explicit activation + API keys.

## Features
- Live market data (Coinbase public ticker + CoinGecko + DexScreener)
- SMA crossover strategy
- Risk-first gate (kill switch, position limits, confidence floor, daily loss limit)
- **Paper execution** (default) with position tracking + trade log
- **Live execution** via Coinbase Advanced Trade API (`coinbase-advanced-py`)
- Natural-language Eko commands
- Dark dashboard UI

## Architecture
```
Data → Strategy → Risk Gate → Execution (Paper | Live) → Monitoring
         ↑
    EkoController (mode switch + conscience + memory)
```

## Quick Start (Paper — safe default)
```bash
pip install -r requirements.txt
python server.py
# open http://localhost:8000
```

## Live Trading Setup

### 1. Create API keys
1. Go to [Coinbase Developer Platform](https://portal.cdp.coinbase.com/)
2. Create an API key with **Trade** permission
3. Prefer **ECDSA** keys when using the official Python SDK

### 2. Set environment variables (never commit these)
```bash
export COINBASE_API_KEY="organizations/your-org-id/apiKeys/your-key-id"
export COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----
...
-----END EC PRIVATE KEY-----
"
```

Or copy `.env.example` → `.env` and fill in the values (python-dotenv loads it automatically).

### 3. Start the server
```bash
python server.py
```

### 4. Activate live mode
In the UI chat (or via API):
```
live
```
Eko will only switch to live if the keys are valid and the client initializes successfully.

Switch back anytime:
```
paper
```

## Safety Controls
| Control | Description |
|---------|-------------|
| **Paper default** | System always starts in paper mode |
| **Explicit live** | Must type `live` (or call the command) after keys are set |
| **Kill switch** | `kill switch` immediately blocks all new orders |
| **Tight risk** | Smaller max position % and higher confidence floor in live |
| **Forced size cap** | Forced/live trades use very small size by default |

## Talk to Eko
| Command | Action |
|---------|--------|
| `status` | Full system status |
| `live` / `paper` | Switch execution mode |
| `kill switch` / `kill switch off` | Halt or resume trading |
| `force buy` / `force sell` | Manual trade (tiny size in live) |
| `accounts` | Show Coinbase balances (live mode only) |
| `remember <note>` | Store a note |
| `recall` | Show recent memory |
| `search <query>` | CoinGecko search |
| `market memory BTC` | Fetch live ticker |

## Project Layout
```
├── data/
│   ├── live_data.py
│   ├── models.py
│   └── trade_log.jsonl          # runtime
├── strategy/
│   ├── base.py
│   └── sma_crossover.py
├── risk/
│   └── risk_manager.py
├── execution/
│   ├── paper_executor.py
│   ├── live_executor.py         # Coinbase Advanced Trade
│   └── trade_logger.py
├── ui/
│   └── 3d-architecture.html
├── eko_controller.py
├── server.py
├── requirements.txt
└── .env.example
```

## Important Warnings
- Start with the smallest possible sizes.
- Test thoroughly in paper mode first.
- The kill switch is your primary emergency control.
- This is experimental software — use at your own risk.
- Never commit API keys or `.env` files.
