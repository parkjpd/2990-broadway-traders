# Round 4 — Same products as Round 3, plus Day 3 holdout

R4 was the round that surprised us in the opposite direction from how we expected. We had spent the week between R3 and R4 preparing for a new product chain; what we got instead was no new products, no new mechanics, and a single new day of data. The visualizer captured it cleanly:

> *"Round 4 — same products as R3: VELVETFRUIT_EXTRACT, HYDROGEL_PACK, 10 VEV_* call options. Days 1, 2, 3."*
>
> *"Round 4 ... days 1+2 are R3 days 1+2 renamed; day 3 = R3 holdout."*

So R4 was effectively a single-day extension of R3. That framing slightly understates how much of the field was caught off-guard, though; most of the top teams had spent the gap building strategies for products that did not arrive. The new alpha came from better calibration on the held-out day 3, not from a new product, and the teams that did well in R4 either re-tuned their R3 strategy on day 3 or added a vol-smile layer on top of the option-pricing logic.

We did both.

## What we shipped

[`algo.py`](algo.py) is `v77_smile_hybrid`, which extends the R3 line with a per-tick **parabolic vol-smile fitter** on the VEV options. The architectural diff from R3's `v32_final`:

| Layer | R3 (v32_final) | R4 (v77_smile_hybrid) |
|-|-|-|
| HG / VF MR | OU fair @ 9990, AR(1) fade | _unchanged_ — proven $160k base alpha |
| Option pricing | Per-strike `IV_MAP` (static) | Per-tick parabolic fit `IV(m_t) = a + b·m_t + c·m_t²` where `m_t = log(K/S)/√T` |
| Option fair value | `BS(S, K, T, σ_static)` | `BS(S, K, T, σ_smile_blended)` |
| Smile-relative MR | none | EMA(α=0.40) on `IV_observed - IV_smile`; trade against the deviation |
| Hard-day detection | none | When VF realized vol > threshold, switch to per-day overrides on `opt_inv_skew`, `smile_w`, `clip_map` |

The smile layer is the alpha, and the insight came from a top R3 team's writeup that we surfaced via `prosperity-intel`:

> 1. Fit a parabola IV(m_t) across strikes per tick.
> 2. The smile parabola is stable; deviations IV_observed − IV_smile show 1-lag negative autocorrelation → MR alpha.
> 3. Convert smile-IV back to a theoretical fair price `BS(S, K, T, σ_smile)`.
> 4. Trade MR around this dynamic theoretical fair (NOT a static rolling mean).
> 5. Smile-fair moves with VF and accommodates strike structure.

Alongside the main strategy, we kept a backup at [`algo_backup.py`](algo_backup.py), `v_smile_pure`, which is a delta-neutral smile-pure architecture that drops HG/VF entirely. It was lower-mean but more robust to a smile-regime shift on day 3. We did not ship it; however, we kept it as a one-line revert in case `v77_smile_hybrid` blew up in production.

## How we got there — the 50+ tuning iterations

`v77_smile_hybrid` was iterated 50+ times over Apr 27–28, all on the same architectural skeleton. The git log reads like a sweep:

```
04-27 10:55  v77_smile_hybrid: per-tick parabolic vol smile + smile-bias to rolling MR
04-27 11:58  EMA-smoothed smile-IV + per-strike clip map
04-27 12:42  hard-day detection → adaptive opt_inv_skew
04-27 13:04  simplified clip map — only VEV_5300=2
04-27 13:20  hard-day skew 0.029→0.035
04-27 15:41  hard-day clip overrides for VEV_5200/5300
04-27 16:29  soft-high-VF detection + hard-day 4000 clip
04-27 17:14  smile bias sign flipped to +1.0; soft-VF clip pushed
04-27 17:36  soft-VF day → negative inv_skew (long-bias inventory)
04-27 18:49  hard-day smile bias weight override (1.0 → 7.0)
04-27 19:18  hard-day EMA α 0.55 → 0.3 (less smoothing)
04-27 19:52  hard-day smile m_range 1.5 → 3.0
04-27 21:32  hard-day skew 0.035 → 0.025
04-27 21:42  hard-day smile w 7.0 → 8.0
04-27 22:00  hard-day cap 3.0 → 4.0; smile w 8.0 → 12.0
04-27 22:23  opt_inv_skew 0.02 → 0.05 (massive R4_d3 lift)
04-27 22:58  smile w 1.0→1.2 + whale signal (Mark 22 SELL VF added)
04-27 23:12  HG whale signal — Mark 38 BUY / Mark 14 SELL → bearish
04-27 23:24  opt_inv_skew 0.05 → 0.055
04-27 23:27  opt_inv_skew 0.055 → 0.054 (balances R4_d1 / R4_d3 binding)
            ↑ MIN=$194,465 (+$34,239)
04-28 00:24  opt_inv_skew 0.054 → 0.050 (revert overfit)
04-28 00:41  SMILE_BIAS_CAP 3.0 → 4.0 → MIN $193,329
04-28 02:16  add HG/VF dynamic anchor option (off by default; tested but hurts)
04-28 02:23  v78: +Mark 14 SELL VF, MC drift fix
04-28 02:32  WHALE_FORCE_TAKE on event tick (v78 pattern, neutral on MIN)
04-28 02:51  HG_IMBAL_SHIFT -5 → -3 → MIN $193,518 (+$20)
04-28 04:02  shift to MAX-EV config (skew=0.020, smile_w=1.0)
04-28 04:16  cap=3, m_range=1.5 → AVG $217,576
04-28 04:34  hg_inv_skew=-0.06 + vf_take_clip=30 → AVG $219,330 / MIN $179,153
04-28 04:52  vf_edge 10 → 9 → AVG $221,026 / MIN $174,853, +$1,696 EV
04-28 05:05  opt_inv_skew 0.020 → 0.015 → AVG $221,342
04-28 05:42  SMILE_BIAS_W 1.0→3.5, cap 3.0→1.5 → AVG $221,862, MIN $170,916
04-28 05:52  HG_WHALE_BIAS 8.0 → 0.0 → AVG $222,907 (+$1,045)
04-28 06:14  opt_edge 10→8, skew 0.015→0.005 → AVG $231,371 (+$8,464)
04-28 06:28  SMILE_BIAS_W 3.5 → 5.0 → AVG $231,599
04-28 06:47  HARD_DAY_OPT_INV_SKEW 0.025→0.012 → AVG $232,652 (+$1,053, MIN $162,972 +$6,318)
04-28 07:01  HARD_DAY_SMILE_IV_EMA 0.3→1.0 → AVG $233,149 (+$497, MIN $165,954 +$2,982)
04-28 07:26  SMILE_IV_EMA_ALPHA 0.55→0.40, vf_take_clip 30→25 → AVG $233,265
04-28 07:48  HG_OU_MU 9990→9988 → AVG $233,416 (+$151, MIN $167,640 +$1,418)
            ↑ FINAL R4 SHIP
```

Two things from this trail are worth flagging explicitly.

First, AVG vs MIN as twin objectives. We tracked both the 6-day average PnL and the 6-day minimum PnL across (R3 d0, d1, d2, R4 d1, d2, d3). Tuning to AVG alone overfits to soft days, and day 3 was the hard one; tuning to MIN alone leaves money on the table on soft days. The final pick balances both: MIN $167k is acceptable, AVG $233k is the headline.

Second, hard-day versus soft-day overrides. A handful of params get adaptive values based on a runtime "is this a hard day?" detection (VF realized-vol crossing a threshold). On hard days we go more conservative (lower `opt_inv_skew`, smaller clips, faster smile EMA). This adaptive switching was the single biggest lift in the late tuning cycle, and is the piece I would defend most if pushed on architectural decisions.

## Discord intel for R4

R4 intel was lighter than R3 because most teams were also iterating their R3 strategies, rather than building anything new. Even so, three notable signals came through `prosperity-intel`:

- **No new products confirmed.** By Apr 26 18:00, multiple top teams asked in `#general` "is there anything new in R4?" and mods deflected to "the data tells the story." That was implicit confirmation that R4 was a holdout-day round.
- **Day 3 vol regime is different.** Several teams' open-source backtests posted Apr 27 showed sharp drops in their R3 strategies on day 3. The smile fit was the obvious adaptation; we got to it because we saw three independent teams complaining about d3 in the same hour.
- **Whale-bot pattern.** Community discussion identified specific bot trader IDs ("Mark 14", "Mark 22", "Mark 38", "Mark 67") whose flow seemed to lead VF/HG moves. We tested a "follow the whale" overlay (`v77_smile_hybrid: WHALE_FORCE_TAKE`) but it was net-neutral and removed.

## Manual challenge

See [`manual.md`](manual.md).

## Result

| Pick | Local AVG (6 days) | Local MIN | Live | Notes |
|-|-|-|-|-|
| v77_smile_hybrid (final) | $233,416 | $167,640 | _TBD_ | Final R4 ship |
| v_smile_pure (backup) | _lower mean_ | _higher MIN_ | _N/A_ | Did not ship; kept as one-line revert |
