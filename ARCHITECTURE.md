# Architecture

Risk-first modular design:

```
Data → Strategy → Conscience + Subconscious → Risk Gate → Execution → Monitoring
```

## EkoController
Analyzes the system and adjusts risk/signals autonomously.

## Conscience Brain
Enforces capital-protection principles and forms a **Feeling**:
- mood: calm | cautious | confident | fearful | greedy
- aggression: 0–1 size multiplier
- trust_signal: how much to trust the strategy

Principles:
- Never risk ruin for a single idea
- Reduce size when uncertain or losing
- Respect the kill switch above all
- Prefer survival over opportunity
- Let memory of pain slow the next decision

## Subconscious
Accumulates:
- Price history → volatility + regime (uptrend / downtrend / range)
- Trade outcomes → recent PnL + win rate
- Free-form notes (`remember …`)

These bias the next Feeling.

## Autonomous loop
`auto` starts continuous `think_and_act` cycles.  
Each cycle: sense market → strategy proposes → conscience feels → risk checks → execute only if both risk and conscience approve.
