# Methodology

This file is about the habits that kept repeating across IMC Prosperity 4: the mistakes we made more than once, the tools that ended up mattering, and the scoring details that quietly changed how every strategy should have been judged. The per-round writeups in `rounds/<n>/README.md` cover the specific decisions; this file is the layer underneath.

The single thing I would tell someone running this competition for the first time is that IMC is not just a strategy competition. It is also a calibration competition. You have to know what the simulator is actually scoring, what the backtester can and cannot reproduce, what the crowd is converging on, and which parts of your own backtest are lying to you. We spent a lot of weeks figuring this out the slow way.

## The two-horizon problem

IMC scores submissions at two horizons: an intermediate 1,000-tick run that drives the in-round leaderboard, and a final 10,000-tick run at round close that determines the actual round-end PnL. Jasper, the mod, confirmed this in `#announcements` during Round 3, and it turned out to be the single most important scoring fact of the competition.

We learned the hard way. Our Round 3 `v06` submission scored −$3,269 live at 1k ticks. At first glance, it looked like a bad strategy. The same code at 10k ticks would have made +$24,692. The issue was not that the strategy was broken; the issue was that the fair-value bootstrap failed early and only stabilized after several thousand ticks. So a strategy could be terrible at 1k and strong at 10k, or the other way around, and the leaderboard you happened to be looking at would tell you the opposite of the truth.

After that, we treated each round as two related games. The 1k pick was aggressive, low warm-up, biased toward TAKE orders; the 10k pick had wider position cycling, more MAKE-ladder depth, designed to let mean reversion fully play out. Round 3's `iterations.md` tracks both horizons in parallel. `v18` was the 1k champion at +$11,746, while `v32_final` became the 10k champion at +$230k. Two different strategies, same problem, scored on different leaderboards.

## Sweep-then-decide, and the trap inside it

We rarely tuned parameters by hand. The normal flow was: write a strategy with 3–6 hyperparameters exposed at the top of the file, run `tools/sweep.py strategies/vXX.py <param> <value1> <value2> ...` against all three days of IMC data, inspect the response curve in the dashboard, and pick the value that maximized PnL only if the curve was smooth around it.

That last condition mattered most. We were not just looking for the highest number; we were looking for a parameter region that behaved as if the signal was real. If a setting spiked at exactly one value and collapsed everywhere around it, that was almost never alpha. It was usually the backtest flattering us, and we paid for ignoring it more than once (see the overfitting section below).

Round 3 ran about 1,000 sweeps. Round 5 ran several thousand parallel walkforward splits. The volume was fine. The discipline around what sweeping should and should not be used for is what mattered: sweeping should size a signal we already believe in, and it should not invent a signal for us.

## The backtester gap

Our local runner (`graphIMC/algos/runner.py`) matched IMC live PnL on the TAKE side to within about 1%. The clearest matches were in Round 3:

| Submission | Local backtest | Live IMC | Match |
|-|-|-|-|
| R3 v06 | −$3,277 | −$3,269 | 99.8% |
| R3 v35 | +$9,539 expected | +$9,927 | 96% |
| R3 v47 | +$32,452 expected | +$32,152 | 99% |
| R3 v50 | +$33,940 expected | +$33,999 | 99.8% |

These matches gave us permission to trust the runner, but only in a limited way. The runner was strong on taking trades, and much weaker on passive MAKE fills, the case where our quote sits at the inside price and another participant crosses it. In live IMC those fills happened; in our local runner, they often did not. That is why a lot of `vXX` versions ended up labeled "backtest neutral, +$5–15k live expected" — the local runner showed no improvement because TAKE behavior was unchanged, but the version added MAKE depth that we expected to matter live.

## The position-limit story

This one is worth telling in detail because it was the largest single PnL jump of the entire competition, and it came from correcting a constant, not from writing better code.

The IMC visualizer initially reported Round 3 position limits of 80 for every product. That was wrong. The real limits, later confirmed by two independent third-party Round 3 backtesters and eventually by the mod, were 200 for HG, 200 for VF, and 300 for the options. We discovered this mid-round, around `v15`. Strategy `v15` simply lifted the position-limit cap from `min(soft_cap=60, position+80)` to `min(soft_cap=200, position+200)`, and our PnL more than doubled:

```
v13: +$76,974
v15: +$166,470
```

That was not a new model. It was not a beautiful discovery. It was a constant correction. The painful part is that the error shaped the way we thought before it shaped the code; we were not only trading smaller, we were imagining a smaller feasible strategy. After `v15`, every published position limit got cross-checked against at least one third-party source. Never trust a visualizer constant when a one-line cap can change the entire round.

## Single-file submission discipline

IMC's sandbox accepts a single Python file with a restricted import allowlist (`__future__`, `json`, `typing`, `math`, `collections`, `datamodel`). No `sys.path.insert`. No filesystem writes. No multi-file imports.

We kept a `verify_submission.py` script in `graphIMC/algos/r5/` that re-ran static and behavioral checks on every md5 change of `<round>_submission.py`, and preserved `<round>_submission_lastgood.py` and `<round>_submission_baseline.py` for rollback. This caught one near-disaster in Round 5: a multi-file `r5_arb_split_cap.py` ranked highly in our local leaderboard, but it used `sys.path.insert` to import seed modules. That would have been disqualified live. The verifier caught it before submission.

## Discord intel as a signal source

The deep version of this is in [`tools/prosperity-intel.md`](tools/prosperity-intel.md). The short version is that manual rounds in IMC are anchored on other teams' consensus far more than they are on real-world fundamentals, and the only way to read that consensus at scale is to scrape the Discord. One top team summarized it during R5:

> "real life doesn't matter, it's how ppl think it'll move"

That sentence is the whole manual-game problem in fifteen words. The market is not asking what is objectively true; it is asking what participants will believe, and how the simulator will reward that belief. The `prosperity-intel` pipeline existed so we could read that belief in something close to real time.

We also tracked deletions, which turned out to be one of the highest-signal pieces of the whole system. People delete what they regret sharing. The selfbot mirrored deleted content into a `deletions` table, and the messages deleted within five minutes of posting were repeatedly more valuable than the messages that were left standing. R5 manual leaned hardest on this; see [`rounds/round5/manual.md`](rounds/round5/manual.md).

## Parallel research streams

Several rounds, especially R3 and R5, used multiple parallel research streams that each produced a digest, with the useful pieces funneled back into the strategy file. Round 3's `algos/research/` has 6 digests; Round 5's `algos/r5/findings/` has about 40.

The streams that mattered most:

- A strategy stream that kept iterating on `vXX_<name>.py` against the runner.
- A data stream that produced `data_analysis_report.md` with FFT, AR(1), realized volatility, and regime detection.
- An intel stream that pulled `prosperity_intel_digest.md` from the Discord database.
- A reference stream that read prior winners (`Ctrl-Alt-DefeatTheMarket`, `jmerle/imc-prosperity-3`, `chrispyroberts`) and produced digests like `ctrl_alt_defeat_digest.md`.
- A verifier stream that ran `verify_submission.py` every 30 minutes against the current submission file md5, continuously through the last 7 hours before each round close.

The point was not to make the process look elaborate. The point was to separate tasks that interfere with each other if you try to do them on the same machine in the same brain at the same time. Strategy iteration, data analysis, Discord monitoring, prior-solution reading, and submission verification all want different kinds of attention.

## The mistake we kept making: overfitting beats clever modelling

Almost all of our self-inflicted losses across the competition came from the same mistake. We picked the version that scored highest on the 3-day backtest, instead of the version that traded the strongest signal. The mistake showed up in three different disguises across three rounds.

The R5 algo result was the cleanest example. R5 algo finished at +$2,752, rank 977th, against an algo backtest of around $1.6M. The 600× gap is the signature of an overfit. We had around 50 candidate parameter configurations from sweeps, most clustered in the $800k–$1.1M backtest range, and we shipped one near the top of that distribution. Pair-trading 50 new products with only 3 days of data is a textbook overfitting setup, and we did the textbook thing. A smaller, dumber strategy — raw pair mean reversion on the 4–5 most stable spreads, ignoring the marginal ones — would have shown lower backtest PnL and higher live PnL.

The R4 KO put long was the same mistake in different clothing. We bought 500 KO put contracts using a Broadie-Glasserman-Kou discrete-monitoring analytic. The model was clever; that was part of the problem. It fit the simulator's continuous-time SDE, but we had not validated it against the simulator's actual realized paths. The analytic looked strong, the realized barrier hits did not, and the position lost $29k.

R3's options sub-strategy had the same shape. Several iterations, especially `v22–v28`, chased per-strike option-sizing tweaks that improved the backtest by $5k–$15k but added little structural edge. Most of those gains were noise; the final 10k champion, `v32`, ended up not depending on the most fragile versions of those tweaks. The issue was never that sweeping was bad. The issue was that we let the sweep start deciding what the strategy was.

The underlying confusion is that "scored well in the sweep" and "captures real edge" are not the same thing. Sweeping is useful when you already know the signal and want to size it. It is dangerous when you use it to choose between strategies, because the strategy with the most fitting flexibility will often win the sweep regardless of out-of-sample performance.

## What I would do differently next time

A few habits I would put in place from day one if we ran this again.

Pick the signal first, then size it. Before opening the sweep harness, write down what the strategy is actually trading in one sentence ("this strategy trades HG OU dislocation," "this strategy trades stable pair mean reversion"). Only after that should the sweep run, and only on sizing parameters like z-threshold, position cap, or fade rate. Never sweep the signal definition itself; if you do, the strategy will become whatever the backtest wants.

Sanity-check against the dumbest baseline. If a dumb baseline gets within 30% of the sweep-optimal strategy, ship the dumb baseline. For R5 pairs that would have meant something like trading the top 3 cointegrated pairs with a fixed z = 2 threshold and a simple position cap, ignoring marginal pairs. If the dumb version gets close to the "optimal" version, the extra PnL is probably fit noise.

Treat sweep PnL more than 5× the analytic baseline as a red flag. A huge backtest improvement should make you suspicious before it makes you excited. If a strategy beats the analytic or dumb baseline by 5× or more, the gap needs to come from a real edge you can name in one sentence. If the only explanation is "the sweep liked this corner," it is probably curve-fit.

Always hold out a day. We trained on Day 2 and Day 3, then shipped without properly checking Day 4. A single held-out day would have caught the R5 algo overfit before submission. It would not have made the model perfect, but it would have stopped us from trusting a strategy that only worked on the exact paths we had just optimized against.

Start the visualizer earlier, and treat position limits as config rather than constants. We rebuilt graphIMC's order-matching engine three times before it matched live; in hindsight, we should have pulled `kevin-fu1/imc-prosperity-4-backtester`'s engine wholesale on Day 1. The `v13 → v15` jump came almost entirely from discovering the real position limits were higher than the visualizer reported — that was luck, not method. Next time, position limits should be configurable from the start, and every strategy should be easy to rerun under alternative caps.

Start manual prep earlier. R5 manual collapsed into the last 6 hours. We got away with it because the Discord consensus became clean by then, but in a noisier round we would have shipped a much worse decision. Manual rounds should have had dedicated prep days, not just whatever hours were left after the algo work.

## Math was necessary. It was not sufficient.

The strongest strategies we shipped were not the most complicated ones. They were the ones with a signal we could explain in one sentence, a backtest that behaved smoothly around the chosen parameters, and a live-scoring interpretation that matched how IMC actually filled orders. The weakest strategies had the opposite shape: too many knobs, too much faith in the highest sweep score, and too little respect for the difference between a real edge and a flattering sample path.

The hard part was learning when the number was telling the truth.
