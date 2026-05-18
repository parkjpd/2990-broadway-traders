# Round 4 — HYDROGEL_PACK / VELVETFRUIT_EXTRACT / VEV options

R4 was structurally identical to R3: same products (`HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT`, 10 VEV call strikes). What changed was a third day of unseen data that ran in a different volatility regime. We answered with two additions: a per-tick parabolic volatility smile fitter on the options, and a runtime day-type classifier that detects the regime in the first 1000 ticks and switches parameters accordingly.

Backtest across 6 days (R3 d0–d2 + R4 d1–d3): **$233,416 average / $167,640 worst-day**.

## What we shipped

[`algo.py`](algo.py) — `v77_smile_hybrid`

Three independent trading layers per tick, each estimating its own fair value and placing its own orders:

- **`HYDROGEL_PACK` MR** — static anchor 9988, L1 imbalance adjustment, shock-fade on moves > 3 ticks. Edge 20, max take clip 50, 3-level passive ladder each side. Inventory skew against position. `MAX_POS=200`. ~$45k/day standalone.
- **`VELVETFRUIT_EXTRACT` MR + whale signal** — anchor 5240, same imbalance/shock logic. Named bot IDs (Mark 49, Mark 67, Mark 22) predict +$2–3 moves in VF over 50 ticks; on event tick we shift fair +3.0 and aggressively buy 35 at market regardless of edge. Whale signal disabled on hard days. Edge 9, clip 25, 5× edge warmup for the first 50 ticks. Combined HG+VF: ~$115k/day.
- **Vol-smile option layer** — per-tick IV back-out via 30-iteration bisection, parabolic smile fit across 8 fitting strikes (VEV_4500–VEV_6000), MR around per-strike smile residuals. Final fair: `rolling_mean + clamp(W × (smile_fair − mid), ±cap)`. Normal: W=5.0, cap=1.5. Hard day: W=12.0, cap=4.0. `MAX_POS=300` per strike.

Backup [`algo_backup.py`](algo_backup.py) — `v_smile_pure` — drops VF alpha entirely, uses VF position as a pure delta hedge, trades options only around smile-implied fair with cross-strike vol-arb pairs. Lower average PnL, higher floor. Not shipped; kept as a one-line revert.

## Day-type detection

The single biggest late improvement: **+$35k on worst-day PnL**.

At tick 1000, the algo classifies the day from HG and VF averages across the first 1000 ticks:

```
Hard day:      HG_avg > 10000
               (R4 D3 ~10033; other days 9958–9982 — easy separation)
               → opt_inv_skew=0.012, larger clips, smile W=12.0/cap=4.0,
                 raw IV signal (skip EMA), moneyness range 1.5→3.0, whale disabled

Soft-high-VF:  VF_avg > 5250, HG normal
               → opt_inv_skew=−0.010 (hold long bias), clip overrides on VEV_5200/5300

Normal:        neither condition → default params
```

## The math

**Black-Scholes:** `BS(S, K, T, σ) = S·N(d₁) − K·N(d₂)`, where `d₁ = (ln(S/K) + 0.5σ²T) / (σ√T)` and `d₂ = d₁ − σ√T`.

**Implied vol:** Bisection on σ ∈ [0.001, 4.0] until `|BS − market| < 0.01`. 30 iterations always sufficient. No vega needed.

**Smile fit:** Least-squares parabola `IV(m) = a·m² + b·m + c` where `m = log(K/S)/√T`. Solved via Cramer's rule on the 3×3 normal equations — no numpy. Need ≥4 valid IVs in [0.05, 1.5]; fall back to rolling mean otherwise.

**Time to expiry:** `T = (4.0 − timestamp/1_000_000) / 252`. Each day runs 0 → 999 900 (step 100).

**EMA smoothing:** α=0.40 on per-strike smile-IV. On hard days α=1.0 — raw signal is better.

## Manual trading — Aether Crystal options

Spot ~50.00. Five put/call strikes, two short-dated ATMs, three exotics (chooser, binary put, knock-out put). PnL averaged over 100 GBM paths. Result: **+$63,019 (rank 256)**.

**Chooser arb (+$72k)**

Static replication via put-call parity at the choose date: `Chooser(K, T+21, choose at T+14) = Call(K, T+21) + Put(K, T+14)`. Market quoted the chooser at 22.20; replicating portfolio (call 12.05 + put 9.75) cost 21.80 — 40 cents cheaper. 50 contracts × 3000 multiplier = $60k of locked arb, zero model risk. The 100-path averaging means realized PnL converges to expected value. Cleanest trade of the competition.

**Binary put hedge (+$23k)**

Shorted the binary put (pays 10 if spot < 40) at 5.00, BSM fair ~4.77. Hedged with a 35–45 put spread. Worst case bounded to [−5, +5] per contract.

**Knock-out put (−$29k)**

Bought a down-and-out put (K=45, barrier=35) using Broadie-Glasserman-Kou discrete-monitoring correction. The analytic didn't match the simulator's actual knockout rate. Most contracts knocked. Lesson: for path-dependent exotics, Monte Carlo against the actual simulator. Continuous-time analytic corrections are not a substitute.

**Unnecessary call (−$23k)**

Bought a T+14 call as a gamma hedge on the chooser arb. The arb's structure handles gamma intrinsically once the T+14 put expires. Redundant; free money left on the table.

Skipping both mistakes → ~$115k instead of $63k.

## How we tuned it

50+ backtests over Apr 27–28 on the same skeleton. Twin objectives: **AVG** (6-day mean) and **MIN** (worst single day). Target: AVG > $230k with MIN > $160k.

Parameters that moved the needle:

| Parameter | Path | Effect |
|---|---|---|
| `opt_inv_skew` | 0.02 → 0.055 → 0.005 | single biggest sensitivity |
| `SMILE_BIAS_W` | 1.0 → 3.5 → 5.0 | smile vs rolling-mean trust |
| `HARD_DAY_SKEW` | 0.025 → 0.012 | hard-day inventory speed |
| `HG_OU_MU` | 9990 → 9988 | last $151 of EV |
| `SMILE_IV_EMA` | 0.55 → 0.40 | smoothing vs responsiveness |
| `vf_edge` | 10 → 9 | tighter entry |

## Risk controls

Position limits: HG 200, VF 200, each option strike 300. Lock mode at tick 9999 switches to unwind-only — only orders that reduce existing positions, forcing approximately flat going into the next day. Options warmup: rolling-mean window requires ≥20 mids before the smile layer starts trading; VF uses 5× edge for the first 50 ticks.

## Result

| Pick | AVG (6 days) | MIN |
|---|---|---|
| v77_smile_hybrid (final ship) | $233,416 | $167,640 |
| v_smile_pure (backup, not shipped) | lower | higher floor |

## Glossary

| Term | Definition |
|---|---|
| MR | Mean-reversion: buy below fair, sell above, repeat. |
| IV | Implied vol: the σ that makes BS = market price. |
| smile | Parabolic curve of IV across strikes. |
| moneyness | `m = log(K/S)/√T`: how far a strike is from spot, normalized. |
| delta | `N(d₁)`: option price change per $1 move in spot. |
| L1 imbal | `(bid_vol − ask_vol)/(bid_vol + ask_vol)` at best prices. |
| edge | Min distance from fair before willing to trade. |
| clip | Max order size for a single aggressive take. |
| inv skew | Shift fair value against position to encourage reversion. |
| EMA | `α × new + (1 − α) × old`. |
| whale | Named bot whose trades predict short-term price direction. |
| hard day | High-vol regime (R4 D3) where HG avg > 10000. |
