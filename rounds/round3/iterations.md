# Round 3 Strategy Iterations

Our round 3 consisted of long sequences of small embarrassments, corrections, and sudden breakthroughs. Early on, we were simply trying to prove that the pipeline worked. Then VF mean reversion began to make real money. Options added a little more. But hedging destroyed the edge. Then OU fair value changed the structure of HG. Then the position-limit mistake exploded the whole scale of the strategy. Finally, the 1k and 10k horizons split into two different worlds.

This table is the trail of that process. It shows not just which versions made money, but what each version taught us about the round.

| Version | Products | Total PnL (3d) | Max DD | Avg Sharpe | Fills | Notes |
|---|---|---:|---:|---:|---:|---|
| v02 | HG | **−$651** | $10,378 | −0.008 | 631 | First baseline. The pipeline worked, but the slow rolling window could not handle drift. It was useful only because it showed the weakness of the initial fair-value logic. |
| v03 | HG + VF | **+$21,175** | $9,174 | +0.489 | 1,356 | The first real jump. Inventory skew plus VF AR(1) fade turned the round from a weak HG experiment into a real strategy. |
| v04 | HG + VF + 6 VEV | **+$24,692** | $14,829 | +0.395 | 1,467 | Added long ATM options. The unhedged gamma contributed about +$3.5k, but the Sharpe fell because the strategy was now carrying more delta exposure. |
| v05 | HG + VF hedge + 6 VEV | **−$295** | $9,582 | +0.008 | 643 | Regression. The full delta hedge saturated the VF limit and destroyed the mean-reversion alpha. This was the first warning that VF could not be both hedge and alpha vehicle. |
| v06 | HG + VF + 6 VEV | **+$24,692** | $14,829 | +0.395 | 1,467 | v04 converted into proper IMC format, with Logger and traderData persistence. Submission-ready, but still carrying the same model assumptions. |
| v07 | HG + VF + 6 VEV | **+$27,502** | $14,829 | +0.435 | 1,444 | Added dynamic initial fair value, warm-up edge, and MAKE orders. It partially fixed v06’s day-2 bootstrap disaster, moving the 1000-tick result from about −$3.3k to −$2.1k. |
| v08 | HG + VF + 6 VEV | **+$19,321** | - | - | - | A safer, less aggressive v07 variant for the 1000-tick horizon. It still lost −$1,006 there and cost $8.2k on the 10k run, so it was safer but weaker. |
| v09 | HG OU + VF + 6 VEV IV_MAP | **+$44,973** | $6,836 | **+1.104** | 1,245 | First serious model breakthrough. HG moved from rolling mean to OU equilibrium fair value, and options moved to a per-strike IV map. It scored +$1,774 on the 1000-tick horizon too, positive on both horizons. |
| v10 | v09 + sweep-tuned | **+$60,857** | $6,958 | **+1.410** | 1,262 | Parameter sweep winner: `hg_edge=10`, `hg_soft_cap=60`, `hg_inv_skew=0.25`, `opt_soft_cap=50`. It made +$3,726 on 1000 ticks, with HG alone contributing about +$38k. |
| v11 | v10 + `vf_edge=8` | **+$67,586** | $6,742 | **+1.571** | 844 | Widened VF edge. It traded less, but each trade had better edge. The 1000-tick result was +$3,384, only −$342 below v10, a small short-horizon tradeoff for better full-run PnL. |
| v12 | v11 + `vf_soft_cap=80`, `opt_edge_abs=4` | **+$72,394** | $7,290 | **+1.624** | 902 | Pushed VF toward the hard limit on high-conviction signals. At this stage, it was best on both horizons: +$3,768 at 1000 ticks and +$72k at 30k. |
| v13 | v12 + `hg_edge=18` | **+$76,974** | $7,116 | **+1.754** | 760 | HG became more selective, only trading larger OU dislocations. This reached +$4,828 at 1000 ticks, placing it around the $4.5k to $5k top-team range. |
| v14 | v13 + 3 agent signals | +$78,248 | $8,848 | +1.663 | 884 | Added HG/VF imbalance, shock fade, and wing sell MAKE. Slightly improved 3-day PnL, but regressed by −$826 at 1000 ticks. The signals were promising but not calibrated well enough. |
| v15 | v13 with **REAL limits 200/300** | **+$166,470** | $25,290 | +1.532 | 1,320 | The constant fix. Two P4 backtester repos pushed Round 3 with limits 200/200/300, not 80. Scaling v13 accordingly lifted PnL to +$166,470 and produced +$8,158 at 1000 ticks, with Day 2 at $5,780, above the expected top range. |
| v16 | v15 + drift-aware HG + wing makes | +$108,194 | $23,574 | +1.409 | 1,033 | Regression. Drift-aware HG fair value brought back the v02 problem by chasing trends, and the wings did not fill locally. Revert to v15. |
| v17 | v15 + taker signals + full VEV chain | **+$171,828** | $25,496 | +1.590 | 1,454 | Added post-shock fade, book imbalance skew, ITM strikes, and wing MAKE orders. The 1000-tick result improved to +$9,276. |
| v18 | v17 + sweep winners | **+$211,220** | $23,168 | **+1.722** | 1,550 | Major sweep winner: `hg_soft_cap=200`, `hg_edge=15`, `vf_edge=12`. It scored +$11,746 at 1000 ticks, Day 2 = $8,830, within $2k to $3k of the top-team $14k to $15k range. |
| v19 | v18 + per-strike option sizing, Lucas tiers | +$218,603 | $31,654 | +1.511 | 1,570 | Better for 10k, worse for 1k. Per-strike option sizing added +$7,383 on the long horizon, but lost −$1,075 at 1000 ticks because option gamma needed more time to pay off. Keep v18 for short-horizon submission. |
| v20 | v18 + ladder MAKE orders | +$211,220 | $23,168 | +1.722 | 1,550 | Identical backtest, since the runner cannot fill passive orders. Expected live boost was +$3k to $8k from deeper laddering. Submit only if trusting live MAKE fills. |
| v21 | v18 with `hg_edge=12`, `vf_edge=8` | +$206,164 | $23,602 | +1.678 | 1,972 | Shifted PnL between days, but the 1000-tick result was essentially flat at −$61. More activity, no real net improvement. |
| v22 | v18 with `hg_edge=10` | +$206,092 | $21,766 | +1.666 | 1,869 | Regression at 1000 ticks, down about −$3.5k. Dropping HG edge too low created noise trades. |
| v23 | v19 + adaptive HG fair + rolling IV | +$184,144 | $19,875 | +1.578 | 1,546 | Reduced drawdown by 37%, but lost −$34k in PnL. Adaptive HG fair value again chased drift. Useful only as a risk layer, not as an alpha improvement. |
| v24 | v19 + rolling IV only | +$208,234 | $22,604 | +1.569 | - | Marginal regression of about −$10k. Rolling IV was safer but lowered backtest PnL. |
| v25 | v19 + aggressive IV_MAP, 0.24→0.28 ATM | **+$223,838** | $43,893 | +1.114 | - | New 10k champion. Option PnL rose by about $5k through higher premium assumptions, with Day 2 option PnL at $20,204. But 1000 ticks lost about −$4k. |
| v26 | v19 + IV_MAP=0.30, peak sweep | **+$225,388** | $48,888 | +1.011 | - | More aggressive IV premium. Day 2 option PnL reached $22,712, the peak of the IV sweep. But drawdown escalated and Sharpe fell to 1.01. |
| v27 | v26 + HG/VF ladder makes | +$225,388 | $48,888 | +1.011 | - | Identical backtest because passive fills were not simulated. Live expectation was about +$16k from the MAKE ladder according to agent-5 sim, putting live near +$241k. |
| v28 | v27 + `vf_soft_cap=200`, hard limit | **+$229,239** | $48,468 | +1.025 | - | New 10k champion. Letting VF reach the hard limit added +$3,851. This became the candidate for the final 10k run. |
| v29 | v28 + option MAKE layer | +$229,239 | $48,468 | +1.025 | - | Identical local backtest, since option passive fills were not simulated. Agent-9 estimated only about +$140 live improvement. |
| v30 | v29 + `hg_edge=12` + `opt_edge_rel=0.03` | **+$229,888** | $49,686 | +0.999 | - | Marginal sweep winners combined. Added +$649 over v28, showing that the easy tuning gains were nearly exhausted. |
| v31 | v30 + delta hedge in VF, threshold 50 | **−$646,430** | $244,384 | −3.482 | - | Catastrophic. The delta hedge recreated the same failure as v05, but worse. VF could not be used as both the main mean-reversion alpha vehicle and a hedge. |
| v32 | v30 with `vf_inv_skew=0.02` | **+$230,096** | $49,478 | +0.990 | - | Final 10k champion. A tiny polish added +$208. Expected live result was about $246k to $250k with MAKE fills. |
| v34 | v30 with options disabled | +$201,996 | - | - | - | New 1000-tick champion at +$11,961, compared with only $1,313 when options were enabled. IMC live v30 showed HG/VF made +$8.8k while options lost $1.5k. Removing options saved the short horizon. |
| v35 | v34 + 1000t sweep winners | +$182,274 | - | - | - | Used `hg_edge=18`, `vf_edge=8`, `hg_inv_skew=0.2`. Scored +$16,664 at 1000 ticks. Live submission scored +$9,927, and the runner matched within 4%. |
| v37 | v35 + day-2 tuning | +$187,564 | - | - | - | Day 2 improved to $10,684 at 1000 ticks. Tuned `hg_inv_skew` from 0.2 to 0.15, `vf_edge` from 8 to 5, and `vf_inv_skew` from 0.03 to 0.01. |
| v38 | v37 + `vf_edge=3` | +$179,505 | - | - | - | Day 2 improved again to $11,395, even though 3-day PnL fell. |
| v39 | v38 + **HG_OU_MU 9990.95→9950** | +$117,018 | - | - | - | Breakthrough. The observed Day 2 first-1000-tick HG mean was 9979, not 9990. Calibrating μ lower captured the drift and pushed Day 2 to $21,233, a +$9,838 jump. |
| v40 | v39 + `hg_edge 18→15`, `hg_inv_skew 0.15→0.10` | +$117,747 | - | - | - | Day 2 improved to $23,570. |
| v41 | v40 + `HG_OU_MU 9950→9955` | - | - | - | - | Day 2 improved to $24,972. |
| v42 | v41 + `hg_inv_skew 0.10→0.06` | - | - | - | - | Day 2 improved to $26,005. |
| v43 | v42 + `HG_OU_MU 9955→9962` | - | - | - | - | Day 2 reached $26,749, with 3-day PnL at $50,296. |
| v44 | v43 + `hg_inv_skew 0.06→0.04` | - | - | - | - | Day 2 improved to $27,704, with 3-day PnL at $53,694. |
| v45 | v44 + `HG_OU_MU 9962→9965` | - | - | - | - | Day 2 improved to $28,630, with 3-day PnL at $55,452. |
| v46 | v45 + `hg_inv_skew 0.04→0.01` | - | - | - | - | Day 2 jumped to $30,799, with 3-day PnL at $59,284. |
| v47 | v46 + `hg_edge 15→13` | - | - | - | - | Day 2 reached $32,487, with 3-day PnL at $61,980. Live submission 383274 scored +$32,152, a 1% match. |
| v48 | v47 + `hg_inv_skew 0.005→0` | - | - | - | - | Day 2 edged up to $32,523, with 3-day PnL at $62,292. |
| v49 | v48 + `vf_take_clip 30→40` | - | - | - | - | Day 2 rose to $32,826, with 3-day PnL at $62,668. |
| v50 | v49 + `hg_edge 13→12` | $173,748 | - | - | - | Current 1000-tick champion. Day 2 reached $34,021, 3-day PnL reached $63,470, and live submission 383539 scored +$33,999, a 99.9% match. |

## Live Submission Log

Live submissions mattered because they told us whether the local runner was fantasy or reality. In Round 3, the match was surprisingly strong.

- `v06`: IMC live scored **−$3,269**, the first submission, damaged by the bootstrap fair-value bug.
- `v30` (`380112`): IMC live scored **+$7,280**.
- `v35` (`380602`): IMC live scored **+$9,927**, while the runner predicted $9,539, within 4%.
- `v43`: expected live was around **$27,000**, based on Day 2 backtest $26,749 plus live bonus.

The lesson: for taking trades, it was close enough to trust the backtester. The missing piece was passive MAKE fills, which the runner could not fully represent.

## Critical Reframe: Final IMC Scoring Was 10,000 Ticks

This changed the meaning of the whole iteration log.

For much of the round, the 1000-tick submissions looked like the main battlefield. But Jasper’s mod intel reframed the scoring: the 1000-tick runs were for the **intermediate leaderboard only**. Final ranking used the **10k-tick round-end run**.

That meant the true final-score champion was not `v18`, even though `v18` was stronger on 1000 ticks. For final scoring, the correct branch was the 10k options-aware branch:

```text
v18 → v19 → v25 → v26 → v28 → v30 → v32
```

So the final submission champion became **v32 at +$230,096**, not the short-horizon `v18`.

## Live IMC vs. Local Backtest

The clearest diagnostic came from `v06`.

Submitted live, it scored **−$3,269 on Day 2, 1000 ticks**. The local runner matched at **−$3,277**. This was almost identical, which made the failure more useful than a lucky win. The bug was not random. It came from a hardcoded bootstrap mismatch at the start of Day 2, combined with the rolling-mean fair value chasing drift.

`v09` fixed both problems by moving HG to an OU equilibrium fair value.

That was one of the first moments where the round shifted from adding features to interpreting the product correctly.

## 1000-Tick Horizon Comparison

At the time, IMC appeared to be using the 1000-tick horizon, so we compared the early candidates directly across Day 0, Day 1, and Day 2.

| Strategy | Day 0 | Day 1 | Day 2 | Sum |
|---|---:|---:|---:|---:|
| v07 | −2,788 | +2,797 | −2,096 | **−$2,088** |
| v08 | −1,508 | +2,330 | −1,827 | **−$1,006** |
| **v09** | **+868** | **−412** | **+1,318** | **+$1,774** |

The comparison made the OU pivot obvious. v07 and v08 were attempts to patch the old logic. v09 changed the underlying interpretation, and that was why it became positive across the short horizon.

## Backlog

The immediate next steps were:

- `v10`: sweep HG and option parameters on top of v09 to push the OU/IV-map strategy further.
- `v11`: reconsider a partial delta hedge now that option positions were smaller.

The second idea would later prove dangerous. The deeper lesson, repeated by both `v05` and `v31`, was that VF could not be treated casually as a hedge. It was already one of the main alpha sources. When the hedge fought the alpha, the strategy did not become safer. It collapsed.
