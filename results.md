# Results

## Final standings

Out of 18,800+ teams in IMC Prosperity 4:

| Category | Global | NA |
|-|-|-|
| Overall | #164 (top 0.87%) | #46 |
| Algorithmic | #253 (top 1.35%) | #73 |
| Manual (cumulative across 3 rounds) | #65 (top 0.35%) | #24 |
| Cumulative XIREC | $519,728 | — |

R5 manual round alone: rank 28 globally (top 0.15%, +$123,354). Our standout single result.

## How we got here

We did not formally participate in tutorial / R1 / R2, so our XIREC entering R3 was $0.

- Round 3 ($166,599, 313th overall): the round that established our iteration pipeline. Manual was the sealed two-bid auction (442nd, +$70,444). Algo iterated v02 → v50 (282nd, +$96,155).
- Round 4 ($227,023, 154th overall, **+159 spots**): manual was the keystone with the chooser arb (+$60k of structural edge, total +$63,019 at 256th). Algo was 168th at +$164,004.
- Round 5 ($519,728, 164th overall, −10 spots): manual ranked **28th globally** (+$123,354), our best round of the competition. Algo regressed to 977th (+$2,752). The rank drop is entirely from the algo, not from manual.

## Honest take

#164 isn't top-tier. The interesting result is the manual side: #65 cumulative globally, #24 NA, and a single-round 28th on R5. That is where the thesis carries — math plus Discord signal beating naive vibe-trading. The algo side underperformed our own backtests, especially on R5 (a roughly 600× gap between $1.6M local PnL and $2.7k live). That is the cost we paid for overfitting on three days of data.

The full per-round story is in `rounds/round3/algo.md`, `rounds/round4/algo.md`, `rounds/round5/algo.md` and the corresponding `manual.md` files.
