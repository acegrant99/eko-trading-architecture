# Eko Trading Architecture

Autonomous crypto trading system with **Eko** as the controller.

## Features
- Live market data (Coinbase public ticker + CoinGecko search + DexScreener)
- SMA crossover strategy (with warm-up)
- Risk-first gate (kill switch, position limits, confidence floor, daily loss limit)
- Paper execution with cash/position tracking and persistent trade log
- Natural-language Eko commands
- Clean dark UI with live metrics + chat

## Architecture
```
Data → Strategy → Risk Gate → Execution → Monitoring
         ↑
    EkoController (conscience + memory + commands)
```

## Quick Start
```bash
pip install -r requirements.txt
python server.py
# open http://localhost:8000
```

## Talk to Eko
| Command | Action |
|---------|--------|
| `status` | Full system status |
| `kill switch` / `kill switch off` | Halt or resume trading |
| `force buy` / `force sell` | Manual paper trade |
| `remember <note>` | Store a note in memory |
| `recall` | Show recent memory |
| `search <query>` | CoinGecko search |
| `market memory BTC` | Fetch live ticker |

## Project Layout
```
├── data/
│   ├── live_data.py      # Coinbase / CoinGecko / DexScreener
│   ├── models.py         # MarketState, Signal, Position, Trade
│   └── trade_log.jsonl   # created at runtime
├── strategy/
│   ├── base.py
│   └── sma_crossover.py
├── risk/
│   └── risk_manager.py
├── execution/
│   ├── paper_executor.py
│   └── trade_logger.py
├── ui/
│   └── 3d-architecture.html
├── eko_controller.py     # The brain
├── server.py             # FastAPI + WebSocket
└── requirements.txt
```

## Notes
- Everything runs in **paper** mode by default.
- No API keys required for the public data endpoints used.
- Kill switch is the highest-priority safety control.
