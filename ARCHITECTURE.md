# Architecture — Eko Evosystem

```
Data → Strategy (per symbol) → Conscience + Subconscious → Risk Gate → Execution
                                    ↑
                         Evosystem autonomous loop
```

## Evosystem
Eko’s multi-asset domain. Default watchlist:

`BTC-USD · ETH-USD · SOL-USD · LINK-USD · DOGE-USD`

Configurable via: `evosystem BTC ETH SOL XMR`

## Autonomous loop
- `auto` — continuous trading across the Evosystem
- Full **ecosystem cycle** every 3rd tick (all symbols)
- Round-robin single-symbol ticks in between
- Every decision still requires **risk + conscience** approval

## Conscience Brain
Feeling: mood · aggression · trust_signal  
Biased by volatility, regime, outcomes, and memory seeds.

## Commands
| Command | Action |
|---------|--------|
| `auto` | Start Evosystem autonomy |
| `stop` | Stop autonomy |
| `evosystem` / `cycle` | One full multi-asset pass |
| `evosystem BTC ETH SOL` | Set watchlist |
| `think` | Single BTC cognitive cycle |
| `live` / `paper` | Execution mode |
| `kill switch` | Freeze all orders |
