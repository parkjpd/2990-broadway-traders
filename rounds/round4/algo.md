# Round 4 — HYDROGEL_PACK / VELVETFRUIT_EXTRACT / VEV options

R4 was structurally identical to R3: same products (`HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT`, 10 VEV call strikes). What changed was a third day of unseen data that ran in a different volatility regime. We answered with two additions: a per-tick parabolic volatility smile fitter on the options, and a runtime day-type classifier that detects the regime in the first 1000 ticks and switches parameters accordingly.

Backtest across 6 days (R3 d0-d2 + R4 d1-d3): **$233,416 average / $167,640 worst-day**.

## What we shipped

[`algo.py`](algo.py) -- `v77_smile_hybrid`

The architectural diff from R3's `v32_final`:

| Layer | R3 (v32_final) | R4 (v77_smile_hybrid) |
|---|---|---|
| HG / VF MR | OU fair @ 9990, AR(1) fade | Unchanged -- proven $160k base alpha |
| Option pricing | Per-strike `IV_MAP` (static) | Per-tick parabolic fit `IV(m) = a + b*m + c*m^2` where `m = log(K/S)/sqrt(T)` |
| Option fair value | `BS(S, K, T, sigma_static)` | `BS(S, K, T, sigma_smile_blended)` |
| Smile-relative MR | None | EMA(alpha=0.40) on `IV_observed - IV_smile`; trade against the deviation |
| Day-type detection | None | Runtime classifier at tick 1000; per-day overrides on `opt_inv_skew`, `smile_w`, `clip_map` |

The smile layer came from a top R3 team's writeup that we surfaced through the graphIMC visualizer:

> 1. Fit a parabola IV(m) across strikes per tick.
> 2. The smile parabola is stable; deviations IV_observed - IV_smile show 1-lag negative autocorrelation -- MR alpha.
> 3. Convert smile-IV back to a theoretical fair price BS(S, K, T, sigma_smile).
> 4. Trade MR around this dynamic theoretical fair (NOT a static rolling mean).
> 5. Smile-fair moves with VF and accommodates strike structure -- tighter, more profitable fair than v77_r4's rolling mean.

Three independent trading layers per tick, each estimating its own fair value and placing its own orders:

### Layer 1: HYDROGEL_PACK MR

Static anchor at `HG_OU_MU=9988` (calibrated from training data). Adjusted per-tick by L1 order-book imbalance (`HG_IMBAL_SHIFT=-3`) and a shock-fade term that fades moves > 3 ticks (`SHOCK_FADE_COEF=0.30`). Inventory skew of `hg_inv_skew=-0.06` shifts fair against position.

Execution: edge 20, max take clip 50. 3-level passive ladder on each side (offsets +1/+2/+3 from best bid, -1/-2/-3 from best ask) with clips [50, 40, 30]. `MAX_POS=200`.

The code also has a dynamic anchor blend (`HG_DYNAMIC_BLEND`) that mixes the static anchor with a rolling mean of HG mids, but it's disabled (`=0.0`) -- testing showed it hurt more than it helped.

HG whale signal: Mark 38 BUY or Mark 14 SELL HG predicts HG dropping ~$1.10 over the next 50 ticks. We apply a bearish bias (`HG_WHALE_BIAS`) to HG fair when this fires. In the final ship this bias is set to 0.0 -- it cost ~$1k AVG in the max-EV regime and wasn't worth the variance.

Standalone alpha: ~$45k/day.

### Layer 2: VELVETFRUIT_EXTRACT MR + whale signal

Anchor `VF_OU_MU=5240`, same imbalance/shock logic as HG but with `VF_IMBAL_SHIFT=0`.

The whale signal: three named bot IDs whose VF trades predict short-term direction:
- Mark 49 SELL VF --> bullish
- Mark 67 BUY VF --> bullish
- Mark 22 SELL VF --> bullish (toggled by `WHALE_INCLUDE_MARK_22=True`)

On detection, we shift VF fair up by `WHALE_BIAS=3.0` for `WHALE_TICKS=50` ticks. On the event tick itself (`whale_just_fired`), we aggressively lift the ask for up to `WHALE_FORCE_QTY=35` shares, bypassing the normal edge requirement. This force-take fires once per signal, not on every tick of the 50-tick window -- the earlier version (`AGGRO_FOLLOW_M67`) that continuously lifted across the window paid too much spread.

Whale signal is disabled on hard days (the post-shock revert weakens in high vol).

Edge 9, take clip 25. First 50 ticks use 5x edge (`WARMUP_EDGE_MULT=5.0`) to avoid noisy opening prints.

Combined HG+VF: ~$115k/day.

### Layer 3: Vol-smile option trading

Per-tick IV back-out via 30-iteration bisection across 8 fitting strikes (`SMILE_FIT_STRIKES`: VEV_4500 through VEV_6000). Fit a parabola `IV(m) = a*m^2 + b*m + c` via closed-form Cramer's rule on the 3x3 normal equations. Need >= 4 valid IVs in [0.05, 1.5]; fall back to pure rolling-mean otherwise.

For each tradeable strike (`TRADE_STRIKES`: VEV_4000 through VEV_5500):

1. Maintain a rolling window of the last 9000 mids (`opt_window`). Compute `rolling_fair = mean(mids)`.
2. Evaluate the smile parabola at the strike's moneyness `m = log(K/S)/sqrt(T)`. Reject if `|m| > SMILE_BIAS_M_RANGE`.
3. EMA-smooth the smile-IV: `sigma_used = alpha * sigma_smile + (1 - alpha) * prev`. Default `alpha=0.40`.
4. Convert to price: `smile_fair = BS(S, K, T, sigma_used)`.
5. Blend: `fair = rolling_fair + clamp(W * (smile_fair - mid), +/- cap)`.
   - Normal: W=5.0, cap=1.5, m_range=1.5
   - Hard day: W=12.0, cap=4.0, m_range=3.0, EMA alpha=1.0 (raw signal)

Edge 8, `MAX_POS=300` per strike. Minimum 20 mids in the rolling window before trading.

## Day-type detection

The single biggest late improvement: **+$35k on worst-day PnL**.

At tick 1000, the algo classifies the day from HG and VF averages collected over the first 1000 ticks:

```
Hard day:      HG_avg > 10000
               (R4 D3 ~10033; other days 9958-9982 -- easy separation)
               --> opt_inv_skew=0.012, larger clips, smile W=12.0/cap=4.0,
                   raw IV signal (EMA alpha=1.0), moneyness range 3.0, whale disabled

Soft-high-VF:  VF_avg > 5250, HG normal
               --> opt_inv_skew=-0.010 (hold long bias), clip overrides on VEV_5200/5300

Normal:        neither condition --> default params
```

Per-strike clip sizes by day type:

| Strike | Normal | Hard day | Soft-high-VF |
|---|---|---|---|
| VEV_4000 | 10 | 15 | 10 |
| VEV_4500 | 10 | 10 | 10 |
| VEV_5000 | 10 | 10 | 10 |
| VEV_5100 | 10 | 10 | 10 |
| VEV_5200 | 10 | 40 | 8 |
| VEV_5300 | 2 | 30 | 30 |
| VEV_5400 | 10 | 10 | 10 |
| VEV_5500 | 10 | 10 | 10 |

VEV_5300 gets clip=2 on normal days because it's closest to ATM at S=5247, highest gamma -- tightest sizing limits the damage from gamma whipsaw. On hard days the regime flips: directional drift dominates noise, so we go much bigger on VEV_5200 (40) and VEV_5300 (30) to capture the move.

The negative inventory skew on soft-high-VF days (`-0.010`) is counterintuitive -- it tells the algo to hold and extend long option positions instead of mean-reverting toward flat. The rationale: on these days VF drifts further up, so long calls keep appreciating. Fighting that drift costs money.

## The math

**Black-Scholes:** `BS(S, K, T, sigma) = S*N(d1) - K*N(d2)`, where `d1 = (ln(S/K) + 0.5*sigma^2*T) / (sigma*sqrt(T))` and `d2 = d1 - sigma*sqrt(T)`. N(x) implemented as `0.5 * (1 + erf(x / sqrt(2)))`.

**Delta:** `N(d1)` -- used by the delta-hedge layer (disabled in final ship).

**Implied vol:** Bisection on sigma in [0.001, 4.0] until `|BS - market| < 0.01`. 30 iterations always sufficient. Returns `None` if market price is below intrinsic minus 0.5 (garbage quote).

**Smile fit:** Least-squares parabola `IV(m) = a*m^2 + b*m + c` where `m = log(K/S)/sqrt(T)`. Solved via Cramer's rule on the 3x3 normal equations (sums of powers S0..S4 and cross-terms T0..T2). No numpy, no matrix library.

**Time to expiry:** `T = (4.0 - timestamp/1_000_000) / 252`. Each day runs 10,000 ticks (timestamps 0 to 999,900 in steps of 100).

## The backup: v_smile_pure

Alongside the main strategy, we kept `v_smile_pure` as a one-line revert. Architecturally different from `v77_smile_hybrid`:

- **No VF alpha.** VF position equals negative net option delta, period. No mean-reversion, no whales, just hedging. VF reserve capped at `HEDGE_VF_RESERVE=80` to avoid consuming the entire VF position limit.
- **No rolling-mean blend.** Options traded purely around the smile-implied fair price. Each strike accumulates a persistent residual (slow EMA of `mid - smile_fair`), and the adjusted fair is `smile_fair + residual_ema`.
- **Cross-strike vol-arb pairs.** When one strike's de-biased IV residual is far above the smile and another is far below, short the rich one and long the cheap one -- delta-neutral vol bet.
- **Delta-hedge layer** (`ENABLE_DELTA_HEDGE=True`): sums net option delta across `HEDGE_STRIKES` (VEV_5000 through VEV_5500), targets VF position at `-round(net_delta)`, and trades toward that target when the diff exceeds `HEDGE_THRESHOLD=15`.

Tradeoff: lower average PnL, higher minimum. More robust to a smile-regime shift on the unseen day. We did not ship it; the v77 hybrid's MIN was acceptable.

## How we tuned it -- the 50+ iteration trail

`v77_smile_hybrid` was iterated 50+ times over Apr 27-28, all on the same architectural skeleton:

```
04-27 10:55  v77_smile_hybrid: per-tick parabolic vol smile + smile-bias to rolling MR
04-27 11:58  EMA-smoothed smile-IV + per-strike clip map
04-27 12:42  hard-day detection --> adaptive opt_inv_skew
04-27 13:04  simplified clip map -- only VEV_5300=2
04-27 13:20  hard-day skew 0.029-->0.035
04-27 15:41  hard-day clip overrides for VEV_5200/5300
04-27 16:29  soft-high-VF detection + hard-day 4000 clip
04-27 17:14  smile bias sign flipped to +1.0; soft-VF clip pushed
04-27 17:36  soft-VF day --> negative inv_skew (long-bias inventory)
04-27 18:49  hard-day smile bias weight override (1.0 --> 7.0)
04-27 19:18  hard-day EMA alpha 0.55 --> 0.3 (less smoothing)
04-27 19:52  hard-day smile m_range 1.5 --> 3.0
04-27 21:32  hard-day skew 0.035 --> 0.025
04-27 21:42  hard-day smile w 7.0 --> 8.0
04-27 22:00  hard-day cap 3.0 --> 4.0; smile w 8.0 --> 12.0
04-27 22:23  opt_inv_skew 0.02 --> 0.05 (massive R4_d3 lift)
04-27 22:58  smile w 1.0-->1.2 + whale signal (Mark 22 SELL VF added)
04-27 23:12  HG whale signal -- Mark 38 BUY / Mark 14 SELL --> bearish
04-27 23:24  opt_inv_skew 0.05 --> 0.055
04-27 23:27  opt_inv_skew 0.055 --> 0.054 (balances R4_d1 / R4_d3 binding)
             ^ MIN=$194,465 (+$34,239)
04-28 00:24  opt_inv_skew 0.054 --> 0.050 (revert overfit)
04-28 00:41  SMILE_BIAS_CAP 3.0 --> 4.0 --> MIN $193,329
04-28 02:16  add HG/VF dynamic anchor option (off by default; tested but hurts)
04-28 02:23  v78: +Mark 14 SELL VF, MC drift fix
04-28 02:32  WHALE_FORCE_TAKE on event tick (v78 pattern, neutral on MIN)
04-28 02:51  HG_IMBAL_SHIFT -5 --> -3 --> MIN $193,518 (+$20)
04-28 04:02  shift to MAX-EV config (skew=0.020, smile_w=1.0)
04-28 04:16  cap=3, m_range=1.5 --> AVG $217,576
04-28 04:34  hg_inv_skew=-0.06 + vf_take_clip=30 --> AVG $219,330 / MIN $179,153
04-28 04:52  vf_edge 10 --> 9 --> AVG $221,026 / MIN $174,853, +$1,696 EV
04-28 05:05  opt_inv_skew 0.020 --> 0.015 --> AVG $221,342
04-28 05:42  SMILE_BIAS_W 1.0-->3.5, cap 3.0-->1.5 --> AVG $221,862, MIN $170,916
04-28 05:52  HG_WHALE_BIAS 8.0 --> 0.0 --> AVG $222,907 (+$1,045)
04-28 06:14  opt_edge 10-->8, skew 0.015-->0.005 --> AVG $231,371 (+$8,464)
04-28 06:28  SMILE_BIAS_W 3.5 --> 5.0 --> AVG $231,599
04-28 06:47  HARD_DAY_OPT_INV_SKEW 0.025-->0.012 --> AVG $232,652 (+$1,053, MIN $162,972 +$6,318)
04-28 07:01  HARD_DAY_SMILE_IV_EMA 0.3-->1.0 --> AVG $233,149 (+$497, MIN $165,954 +$2,982)
04-28 07:26  SMILE_IV_EMA_ALPHA 0.55-->0.40, vf_take_clip 30-->25 --> AVG $233,265
04-28 07:48  HG_OU_MU 9990-->9988 --> AVG $233,416 (+$151, MIN $167,640 +$1,418)
             ^ FINAL R4 SHIP
```

Two things from this trail worth flagging.

First, AVG vs MIN as twin objectives. We tracked both the 6-day average PnL and the 6-day minimum PnL across R3 d0/d1/d2 + R4 d1/d2/d3. Tuning to AVG alone overfits to soft days; tuning to MIN alone leaves money on the table. The final pick balances both: MIN $167k is acceptable, AVG $233k is the headline.

Second, the regime flip at 04-28 04:02. The first night of tuning (04-27) maximized MIN, pushing `opt_inv_skew` all the way to 0.055 and landing MIN at $194k. But AVG was stuck in the low $190s. At 04:02 we pivoted to a MAX-EV config (aggressive `hg_inv_skew=-0.06`, lower `opt_inv_skew`, tighter edges) and then layered back the smile and day-detect knobs to recover MIN. The final config is a MAX-EV skeleton with targeted risk controls -- not the conservative skeleton we started with.

Parameters that moved the needle the most:

| Parameter | Path | Effect |
|---|---|---|
| `opt_inv_skew` | 0.02 --> 0.055 --> 0.005 | single biggest sensitivity |
| `SMILE_BIAS_W` | 1.0 --> 3.5 --> 5.0 | smile vs rolling-mean trust |
| `HARD_DAY_SKEW` | 0.025 --> 0.012 | hard-day inventory speed |
| `HG_OU_MU` | 9990 --> 9988 | last $151 of EV |
| `SMILE_IV_EMA` | 0.55 --> 0.40 | smoothing vs responsiveness |
| `vf_edge` | 10 --> 9 | tighter entry |

## Discord intel for R4

R4 intel was lighter than R3 because most teams were iterating their existing strategies rather than building something new. Three signals came through:

- **No new products confirmed.** By Apr 26 18:00, multiple top teams asked in `#general` whether R4 had anything new. Mods deflected to "the data tells the story." Implicit confirmation that R4 was a holdout-day round.
- **Day 3 vol regime is different.** Several teams' open-source backtests posted Apr 27 showed sharp drops in their R3 strategies on day 3. The smile fit was the obvious adaptation; we got to it because three independent teams were complaining about d3 in the same hour.
- **Whale-bot pattern.** Community discussion identified specific bot trader IDs (Mark 14, Mark 22, Mark 38, Mark 49, Mark 67) whose flow led VF/HG moves. We built the whale overlay from this; the VF whale signal (Mark 49/67/22) shipped, but the HG whale (Mark 38/14) was net-negative and got zeroed out (`HG_WHALE_BIAS=0.0`).

## Manual trading -- Aether Crystal options

Spot ~50.00. Five put/call strikes, two short-dated ATMs, three exotics (chooser, binary put, knock-out put). PnL averaged over 100 GBM paths. Result: **+$63,019 (rank 256)**.

**Chooser arb (+$72k)**

Static replication via put-call parity at the choose date: `Chooser(K, T+21, choose at T+14) = Call(K, T+21) + Put(K, T+14)`. Market quoted the chooser at 22.20; replicating portfolio (call 12.05 + put 9.75) cost 21.80 -- 40 cents cheaper. 50 contracts x 3000 multiplier = $60k of locked arb, zero model risk. The 100-path averaging means realized PnL converges to expected value. Cleanest trade of the competition.

**Binary put hedge (+$23k)**

Shorted the binary put (pays 10 if spot < 40) at 5.00, BSM fair ~4.77. Hedged with a 35-45 put spread. Worst case bounded to [-5, +5] per contract.

**Knock-out put (-$29k)**

Bought a down-and-out put (K=45, barrier=35) using Broadie-Glasserman-Kou discrete-monitoring correction. The analytic didn't match the simulator's actual knockout rate. Most contracts knocked. Lesson: for path-dependent exotics, Monte Carlo against the actual simulator. Continuous-time analytic corrections are not a substitute.

**Unnecessary call (-$23k)**

Bought a T+14 call as a gamma hedge on the chooser arb. The arb's structure handles gamma intrinsically once the T+14 put expires. Redundant; free money left on the table.

Skipping both mistakes --> ~$115k instead of $63k.

## Risk controls

**Position limits:** HG 200, VF 200, each option strike 300.

**Lock mode:** At tick 9999 (`LOCK_TICK`) the algo switches to unwind-only. It only sends orders that reduce existing positions. For any symbol where we have a position but no reduce-orders were generated, it posts a market order at the best price to flatten. This forces approximately flat going into the next day.

**Warmup:** VF uses 5x edge for the first 50 ticks (`WARMUP_EDGE_MULT=5.0`) -- opening prints are noisy and early iterations got burned trading too aggressively on tick 1. The options layer needs at least 20 mids in the rolling window before it starts trading at all. Day-type detection collects data passively for the first 1000 ticks before classifying.

**PnL tracking:** The algo tracks cumulative PnL and peak PnL each tick via `_update_cash_from_trades` and `_compute_total_pnl`. In the shipped config only the tick-based lock mode is active, but the architecture supports drawdown-based locking (`LOCK_PCT`, `LOCK_ABS`, `LOCK_MIN_PEAK`) for future use.

## Result

| Pick | AVG (6 days) | MIN |
|---|---|---|
| v77_smile_hybrid (final ship) | $233,416 | $167,640 |
| v_smile_pure (backup, not shipped) | lower | higher floor |

## Glossary

| Term | Definition |
|---|---|
| MR | Mean-reversion: buy below fair, sell above, repeat. |
| IV | Implied vol: the sigma that makes BS = market price. |
| smile | Parabolic curve of IV across strikes. |
| moneyness | `m = log(K/S)/sqrt(T)`: how far a strike is from spot, normalized. |
| delta | `N(d1)`: option price change per $1 move in spot. |
| L1 imbal | `(bid_vol - ask_vol)/(bid_vol + ask_vol)` at best prices. |
| edge | Min distance from fair before willing to trade. |
| clip | Max order size for a single aggressive take. |
| inv skew | Shift fair value against position to encourage reversion. |
| EMA | `alpha * new + (1 - alpha) * old`. |
| whale | Named bot whose trades predict short-term price direction. |
| hard day | High-vol regime (R4 D3) where HG avg > 10000. |
| soft cap | Position level where we stop adding but don't force-liquidate. |
| shock-fade | Fade large price moves by shifting fair against the jump direction. |
