# Round 5 — 50-product cluster universe + PEBBLES basket

R5 was a complete reset. The R3/R4 product set (HG/VF/VEV) was retired and replaced with **~50 new products organized into 9–10 clusters**:

```
PEBBLES_{XS,S,M,L,XL}        SNACKPACK_{CHOCOLATE,VANILLA,
UV_VISOR_{AMBER,RED,...}      PISTACHIO,RASPBERRY,STRAWBERRY}
GALAXY_SOUNDS_{...}          MICROCHIP_{SQUARE,TRIANGLE,
OXYGEN_SHAKE_{GARLIC,MINT,    RECTANGLE,OVAL,CIRCLE}
CHOCOLATE,EVENING_BREATH,     ROBOT_{DISHES,MOPPING,LAUNDRY,
MORNING_BREATH}                IRONING,VACUUMING}
PANEL_{2X4,...}              SLEEP_POD_{...}
TRANSLATOR_{...}
```

Each product had a **position limit of 10** (mod-confirmed). With 50 products that's a 500-unit total exposure cap, but the binding constraint per-position is small. The alpha came from **within-family pairs trading** (cointegrated co-movement within e.g. the MICROCHIP cluster) rather than from any single-product directional bet.

We worked the round across five days, with a verification cycle running on the final submission for the last seven hours before close.

## What we shipped

[`algo.py`](algo.py) — `r5_smooth_v1` (the locked ship per the `ship: r5_smooth_v1 final decision` commit on 2026-04-29 22:32 EST).

The architecture:

- **39 hand-curated within-family pair seeds** — each is a `(mu, sd)` tuple for the spread between two cointegrated products in the same cluster. Selected via per-pair attribution analysis with a `--ratio=4.0` threshold to filter out "d4-dependent" pairs (signals that only worked on the eval day).
- **Per-pair Z-score MR** — when `|z| > z_threshold`, take the rich leg short / cheap leg long. Per-pair `MAX_POS=10`.
- **MICROCHIP triplet overlay** — a verified 3-leg cointegration signal in the MICROCHIP cluster (TRIANGLE/OVAL/RECTANGLE). Smaller `TRIPLET_MAX_POS=2` and a hedge cap of 4. Standalone PnL across days 2–4: $1.22M.
- **No per-product seeds** — earlier versions had per-product mean overrides which were the source of catastrophic shift-loss (HYBRID_ROBUSTNESS.md). Stripping them was the dominant robustness win.

We also kept [`algo_alt.py`](algo_alt.py) — `r5_final` — a multi-layer ensemble (pair MR + PEBBLES H4 basket arb + structural bias) — as a swap candidate. It shipped to a swap branch but was held back from the final ship after the smooth_v1 audit cycle locked the safer pick.

## How we got here — the audit cycles

R5 had a verification harness (`algos/r5/verify_submission.py`) that re-ran five backtests plus static checks on every md5 change of `r5_submission.py`. It ran 17 cycles over the seven hours before the submission deadline; cycle logs went to `findings/VERIFICATION_LOG.md`.

The architectural progression on the strategy side:

```
r5_submission.py (baseline)        0% PnL: $305k    DD $46k    WF 3/6 positive
r5_aggressive_d4_seeds (yield)     0% PnL: $977k    DD $37k    Sharpe 4.74
                                   ★ but per-product seeds = shift-fragile

r5_hybrid_X_more_pairs (PICK A)    0% PnL: $868k    DD $39k    WF 6/6, shift 5/5
                                   ★ "double-safe" — never loses
r5_hybrid_Y_z17_alpha0002 (PICK B) 0% PnL: $1,239k  DD $59k    WF 5/6 (worst -$49k)
                                   ★ "yield-max" — accept 1/6 walkforward risk

r5_smooth_v1 (final ship)          39 hero pairs, no per-product seeds
                                   passes promotion gate cleanly + audit lock
```

The decision between **PICK A (X_more_pairs)** and **PICK B (Y_z17)** was the key call. PICK B had higher EV but a 1-in-6 chance of a moderate (~$50k) walkforward loss. PICK A was strictly worse on EV but never produced a negative scenario in any test. We landed on `r5_smooth_v1` — a derivative of PICK A that further filtered the pair seeds to "heroes" (positive on all three days, ratio < 4×).

The audit chain that locked `r5_smooth_v1`:

```
21:10  smooth: r5_smooth_v1 passes promotion gate cleanly
22:03  smooth: r5_smooth_v1 final pre-ship audit — LOCKED
22:32  ship: r5_smooth_v1 final decision — smooth_v1 vs combined vs cluster_aware audit complete
```

Subsequent experiments (`r5_taffy_framework`, `r5_taffy_avgseeds`, `r5_taffy_hybrid`) all PROMOTED on individual gates but were judged **not robust enough** to swap into the locked submission.

## Discord intel that mattered

R5 intel was unusually concentrated. Top teams (Zain, Suahs, Mosho, Fabian) were openly discussing strategy in `#general` because everyone knew the products were too new for any one team to have a unique edge. The two intel threads that mattered:

### 1. The "no Olivia" finding (algo round)

In **P3 R5**, the dominant alpha for top-25 teams was **insider trader-ID detection** ("Olivia") — `shellmaxxing` flagged in P4 Discord on 2026-04-28: *"we dont get counterparties for this round?"*. **No P4 R5 trader IDs were exposed**, so the P3 R5 playbook was inapplicable. That meant **architecture choice was the alpha**, and we needed to pick the most robust architecture.

The P3 R5 winners' conclusion translated to P4 R5 was actually a **negative-space finding** (TimoDiehm, P3 2nd):

> *"Reducing mean reversion exposure (which had generated losses in Round 4)... half-hedged the baskets... limited mean reversion strategy to minimize risk."*

That is, P3 winners did **not** lean on pair MR in R5. We took this as a robustness signal as pair-MR strategies can fail on the eval day in ways the sample doesn't show. It pushed us toward the more-robust `smooth_v1` over the higher-yield `Y_z17`.

### 2. The P3R5 → P4R5 product mapping (manual round)

See [`manual.md`](manual.md). Three independent top-tier players (Zain, Suahs, Mosho) converged on the same P3R5 → P4R5 product mapping the night before submission, which is what pushed us to flip Obsidian Cutlery from SELL to BUY.

## Manual challenge

See [`manual.md`](manual.md).

## Result

| Pick | 0% PnL | DD | Walkforward | Shift sweep |
|-|-|-|-|-|
| r5_smooth_v1 (FINAL SHIP) | _post-eval TBD_ | bounded | 6/6 positive | ±5/±10% all positive |
| r5_hybrid_X_more_pairs (PICK A backup) | $868,100 | $38,746 | 6/6 positive | min $820k |
| r5_hybrid_Y_z17_alpha0002 (PICK B alt) | $1,239,307 | $58,918 | 5/6 (1× -$49k) | min $1,117k |
| r5_aggressive_d4_seeds (high-yield, NOT shipped) | $977k | $37k | n/a | per-product fragility |
| r5_submission.py baseline | $305k | $46k | 3/6 | _dominated_ |

Round-end actuals from the IMC dashboard go in [`../../README.md`](../../README.md) results table.

## Findings docs (verbatim)

The full R5 research lives in [`findings/`](findings/) (copied from `graphIMC/algos/r5/findings/`). Highlights:

- [`FINAL_DECISION.md`](findings/FINAL_DECISION.md) — the PICK A vs PICK B writeup that drove the smooth_v1 lock.
- [`HYBRID_ROBUSTNESS.md`](findings/HYBRID_ROBUSTNESS.md) — why per-product seeds are shift-fragile.
- [`HISTORICAL_PRECEDENT.md`](findings/HISTORICAL_PRECEDENT.md) — the P3 R5 winners' lesson that argued against yield-max.
- [`COMPREHENSIVE_RANKING.md`](findings/COMPREHENSIVE_RANKING.md) — full leaderboard of 50+ candidates.
- [`PER_PAIR_ATTRIBUTION.md`](findings/PER_PAIR_ATTRIBUTION.md) — the "heroes vs d4-dependent" classification driving smooth_v1's pair selection.
- [`SMOOTH_VS_SKEWED.md`](findings/SMOOTH_VS_SKEWED.md) — why smooth (filtered pairs) beat skewed (more pairs, more variance).
