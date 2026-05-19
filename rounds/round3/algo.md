# Round 3: HYDROGEL_PACK, VELVETFRUIT_EXTRACT & 10× VEV options

When we first opened our data capsules for round 3, we realized that the problems no longer felt like simple market making. R3 gave us two underlying products, HYDROGEL_PACK and VELVETFRUIT_EXTRACT, along with ten European call options on VELVETFRUIT_EXTRACT. We thought that this initially was another layer of compleixty IMC added but once the mods confirmed that options were fair-value-liquidated at round end, not exercised, the entire round changed. These options were thus mispriced synthetic exposure and understanding them properly became the difference maker between an ordinary P3-style "let's make markets and sweep" strategy and a real options-aware strategy worth tens of thousands more. 

Over five days, we shipped 224 named iterations plus roughly 1,000 sweep variants. The main live-shipped progression ran from v02 → v50, while a parallel track, v18 → v32, developed into the 10k-tick final-scoring strategy.


## Products

| Product | Position limit | Profile |
|-|-|-|
| **HYDROGEL_PACK (HG)** | 200 | Mean-reverting around an OU equilibrium (μ ≈ 9990.95 on full data, but ≈ 9979 on the first 1k ticks of day 2, see "calibration pivot" below) |
| **VELVETFRUIT_EXTRACT (VF)** | 200 | Underlying with AR(1) ρ ≈ −0.16 tick-level reversion, plus ntra-day drift |
| **VEV_4000 .. VEV_6500** (10 strikes) | 300 each | European calls on VF, fair-value-liquidated at round end (not exercised) |

At first, the visualizer told us that all position limits were 80. So we began sizing trades, setting caps, and controling risk around a false constraint. But the real limits, confirmed by both kevin-fu1/imc-prosperity-4-backtester and jmerle/imc-prosperity-3-backtester, and later by the mod, were 200/200/300.

That discovery came mid-round, around v15, and it more than doubled our PnL! We realized that nothing beautiful had to be added. No elaborate new model was needed. One mistaken constant was corrected, and the whole round opened up.

## What we shipped

- **For the 1k-tick intermediate leaderboard**: [`algo.py`](algo.py) — `v170_hg_sell_aggro` our latest live-shipped variant.
- **For the 10k-tick final scoring, we shipped**: [`algo_10k.py`](algo_10k.py) — `v32_final` which scored $230,096 local, with an expected ~$246k–$250k live after MAKE fills.

Both were single-file IMC-compliant submissions using the standard `Logger` log-compression helper.

## How we got there 
The full table is in [`iterations.md`](iterations.md) (verbatim from `graphIMC/algos/iterations.md`). The shape:

```
v02 HG baseline            -$651    SR -0.01   (proof of pipeline)
v03 + VF MR               +$21,175  SR  0.49   (inventory skew + AR(1) fade)
v04 + long ATM options    +$24,692  SR  0.40   (un-hedged gamma adds $3.5k)
v05 delta-hedge attempt    -$295    SR  0.01   (REGRESSED: hedge saturates VF cap)
v06 IMC format wrapping   +$24,692  SR  0.40   (= v04, IMC-submission ready)
v09 OU fair + IV map      +$44,973  SR  1.10   (model-fit-agent breakthrough)
v10 sweep-tuned           +$60,857  SR  1.41
v13 hg_edge 10→18         +$76,974  SR  1.75   (top of "small-limits" era)

  ← position-limit pivot: real limits 200/200/300, not 80 →

v15 REAL limits          +$166,470  SR  1.53   (2.2× from a constant change)
v18 sweep winners        +$211,220  SR  1.72   (1k champion +$11,746)
v19 per-strike opt size  +$218,603  SR  1.51   (10k champion, regresses on 1k)
v32 vf_inv_skew=0.02     +$230,096  SR  0.99   (10k champion final pick)

  ← horizon split: ship v34 (no options) for 1k, v32 for 10k →

v34 options DISABLED     +$201,996  SR  N/A    (1k +$11,961, options drag at short horizon)
v35 day-2 sweep          +$182,274  SR  N/A    (1k +$16,664; live +$9,927 — 96% match)
v47 hg_edge 15→13        +$132,184  SR  N/A    (live +$32,152)
v50 hg_edge 13→12        +$173,748  SR  N/A    (live +$33,999 — 99.8% match)

  ← second pivot: HG dynamic μ + book/flow signals →

v60 + multi-day window   +$53,080 live (1k baseline for second iteration phase)
v83 depth-weighted L1+L2 imbalance on HG
v86 VF trade-flow signal
v92 HG μ EMA blend
v97 9-axis grid sweep winner: vf_edge=2, vf_inv_skew=0, vf_take_clip=50
v101 stacked v97 + v92 + per-strike opt_edge → +$54,728 day 2 1k
v104 VF_IMBAL_SHIFT 1.0→0.0 → +$54,928 day 2 1k

  ← latest live-ship pick →

v170 hg_sell_aggro       Day 2 1k expected $62,461 (+$9,381 vs v60 live $53,080)
```

## Three breakthroughs that drove the jumps

### 1. HG is OU, not rolling-mean

`v06` used a rolling-mean fair value for HYDROGEL_PACK. At first, this seemed reasonable. If the product was mean-reverting, then a rolling mean felt like a natural way to approximate fair value. 

But this was deceptive!

The rolling mean chased drift. When HG ticked upward for 50 samples in a row, the rolling mean followed it upward. Instead of anchoring us to fair value, it trained the bot to buy high. Live IMC scored that submission at −$3,269 on the 1k run. The local backtest matched almost perfectly at −$3,277.

`v09` made the crucial correction we needed. Instead of letting the fair value move with noise, it fixed HG around a constant OU equilibrium of 9990.95, fitted on all 30k ticks. On the same 1k run, the strategy scored +$1,774.

One better interpretation of fair value gave us a $5k swing. 

### 2. Real position limits are 200/200/300.

This was probably the most brutal, time-consuming, but most useful discovery of the round. 

The graphIMC visualizer showed 80-unit limits because we had forked the position-limit constant from `Ctrl-Alt-DefeatTheMarket`’s tutorial-round defaults. For a while, that false number quietly constrained us. We were trading smaller and thinking smaller too. Then we cross-checked two third-party Round 3 backtesters,(`kevin-fu1`, `jmerle`, and both used 200/200/300. They were right and The visualizer was wrong! We scaled up. 

The `v13 → v15` diff was almost embarrassingly simple: same logic, but replace `min(soft_cap=60, position+80)` with `min(soft_cap=200, position+200)`. Our PnL jumped from +$76,974 to +$166,470. 

### 3. The 1k vs 10k horizon split

The next realization was more subtle: the best strategy depended on the horizon.

`v18` was the 1k champion at +$11,746. `v19` added per-strike option sizing and improved the 10k result to +$218,603. But it lost $1,075 on 1k, because the options needed at least 5k ticks to settle into their edge.

This forced a split. For the short horizon, we followed the v18-derived path:

- 1k pick: `v18`-derived → eventually `v34` with options disabled → `v50` with day-2 calibration → `v170_hg_sell_aggro`.
- 10k pick: `v19`-derived → `v32_final`.

This split persists into Round 4. This also told us that a strategy can be correct in its structure but wrong in time. 

## Local backtest vs. live IMC accuracy

The broader methodology is documented in [`../methodology.md`](../methodology.md), but Round 3 gave us unusuallty clean confirmation that the backtester was trustworthy. 


| Submission | Local backtest expected | Live IMC scored | Match |
|-|-|-|-|
| v06 | −$3,277 | −$3,269 | 99.8% |
| v30 | +$7,280 expected | +$7,280 | 100% |
| v35 | +$9,539 expected | +$9,927 | 96% |
| v47 | +$32,452 expected | +$32,152 | 99% |
| v50 | +$33,940 expected | +$33,999 | 99.8% |

The main missing piece was  **passive (MAKE) fills**. The runner does not simulate cases where our quote sits inside the spread and another participant crosses it. Because of this, strategies that added MAKE depth , such as v20, v27. v73, v93, and v102, were tagged as d "backtest neutral but +$5–15k live expected".

Several of those were shipped even without backtest support, becuase the structural reasoning was strong enough. The backtester could confirm the taking edge but it could not fully measure the value of being patiently present inside the spread. 

## Discord intel 

Some of the most important information did not come from our code but rather from monitoring the Discord carefully. 

- **Lucas's per-strike PnL leak**
Lucas posted the following in Discord  `#open-source`, 2026-04-24 17:49 UTC):
  > "VEV_4000: 5,702 / VEV_4500: 7,986 / VEV_5000: 20,117 / VEV_5100: 21,506 / VEV_5200: 18,310 / VEV_5300: 9,828 / VEV_5400: 3,873 / VEV_5500: 920"
  
  Our v18 was making $13,474 on options. Lucas's number was $88,342. The gap was too large for us to just ignore. we recongized that the isuse was sizing. We were using a flat `opt_soft_cap=200` vs. a per-strike `OPT_SOFT_CAP_MAP` proportional to expected edge. Lucas’s leak showed that the option edge was not evenly distributed. The right move was to size each strike according to expected edge Thus, `v19` rebuilt the option-size logic around this leak

- **Tomas (mod) on options mechanics**
Tomas, the moderator, clarified that options mechanics on (2026-04-24 17:49 UTC):
  > "Options are European + fair-value-liquidated at round end (NOT exercised)."
  
  This told us that **deep ITM options behave like delta-1 long VF positions** and **deep OTM options price at zero at round end**. Both edges are exploitable. Thus, we created `v75` and `v90+wings`.

- **Matthew's 154k claim**
Matthew's claim in (Discord, `#general`) was simple:
  > "MM the fair price"
  
  We took this seriously and shipped `v74_vf_heavy_mm.py` a 7-level HG/VF MAKE ladder. It was backtest-neutral but live-positive, precisely because the backtester could not fully capture passive fills.

## Manual challenge

See [`manual.md`](manual.md).

## Result

| Pick | Horizon | Local | Live | Notes |
|-|-|-|-|-|
| v50 (intermediate ship) | 1k | $33,940 | $33,999 | Match 99.8% |
| v170 (latest 1k ship) | 1k | $62,461 (Day 2) | _TBD_ | Latest pre-R4 ship |
| v32_final | 10k | $230,096 | _TBD_ | + ~$16k live expected from MAKE fills |

Round-end totals from the IMC dashboard go in [`../../README.md`](../../README.md) results table.
