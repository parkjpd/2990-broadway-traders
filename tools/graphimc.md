# graphIMC — backtester, visualizer, sweep harness

graphIMC is the project where every single strategy iteration we ran lived (roughly 1,700 named versions across rounds 3 and 5 alone), alongside the local backtester, the browser-based visualizer, and the parameter-sweep tooling that made it possible to iterate at that volume in the first place. The source isn't public, but the visualizer is — drop in any IMC CSV bundle and submission log at **https://imc-prosperity-visualizer.vercel.app** to see it run.

So why did this tool exist, and why was it worth maintaining? Moreover, why is the visualizer named after a Bloomberg terminal of all things?

## What's in it

```
graphIMC/
├── algos/                    ← per-round strategy work
│   ├── runner.py             ← local backtest runner (IMC Trader interface)
│   ├── runner_passive.py     ← variant with passive (MAKE) fill simulation
│   ├── runner_makefill.py    ← + per-tick make-fill model
│   ├── sweep.py              ← single-axis parameter sweep
│   ├── tools/                ← sweep_3day.py, iterate_loop.py, quick_test.py
│   ├── strategies/           ← v02 → v224, _temp_t3_*, etc (~1,700 files)
│   ├── results/              ← per-strategy JSON results
│   ├── research/             ← cross-round digests
│   ├── r5/                   ← round-5 specific work
│   │   ├── strategies/       ← 50+ named candidates
│   │   ├── findings/         ← ~40 research docs
│   │   ├── walkforward.py    ← walkforward harness
│   │   └── verify_submission.py  ← continuous audit cycle
│   ├── iterations.md         ← round-3 v02→v50 progression table
│   └── README.md             ← round-3 ship picks + breakthroughs
├── index.html                ← Bloomberg-terminal-style dashboard
├── prices_round_*_day_*.csv  ← IMC data drops
└── trades_round_*_day_*.csv
```

## The visualizer (index.html)

The visualizer is a single ~500KB HTML file with no build system. Open it in a browser, drag in the IMC CSVs alongside your submission log, and a multi-panel dashboard renders out of the box. Across the months of the competition, I rewrote the layout of this dashboard three different times before I settled on the version we used.

What ended up in the final layout:

- A TradingView-style price chart with overlays for bid/ask depth, mid price, the fair-value model (if it was logged into `traderData`), realized vol, and RSI.
- An order book panel with live and historical depth, color-coded by side.
- A PnL chart showing cumulative + per-product, alongside Sharpe (raw and t-stat) and Sortino summary cards.
- An inventory chart, per-product position over time.
- A "Bot Analyzer" panel that clustered anonymous market-trade patterns and let us visually identify the same bot trader showing up across days.
- A "Strategy Lab" panel where you can paste a `Trader` class, hit run, and watch it execute against any day, inline.
- A "Parameter Lab" for single and multi-parameter sweeps with response curves.
- A Monte Carlo panel for bootstrap-resampled fills.
- Drag-and-drop layout, so every panel can be rearranged; layout presets save to localStorage.

The visualizer set the pace of the entire competition. Every iteration cycle looked the same: `runner.py strategies/vXX.py → log → drop in viz → look at PnL/inventory → tune → repeat`. Without the viz, the cycle takes ten minutes per iteration and you fall behind on the third day; with it, the cycle drops to roughly a minute, and the third day is where you actually start finding alpha.

### Matching engine alignment

The local matching engine took three rewrites to actually match IMC's live behavior, which is a long enough story that it deserves its own list.

First, the naive "fill at touch" version. This was the first cut, and it diverged from IMC by roughly 5–10% on take-side PnL. The issue was that IMC's engine consumes the order book in a specific order (by price, then by time within a price level), and the naive version was getting that wrong on partial fills.

Second, a version with passive-fill simulation plus simple cross-detection. This was better, but still 2–3% off, because IMC simulates MAKE fills with a probability model that depends on the spread, the position, and the bot trader behavior, none of which our second version was tracking.

Third, the version that actually worked: a wholesale port from [`kevin-fu1/imc-prosperity-4-backtester`](https://github.com/kevin-fu1/imc-prosperity-4-backtester). The commit message reads `29249c9: "Rewrite order matching engine to match kevin-fu1/imc-prosperity-4-backtester"`, and that is exactly what happened. The take-side match dropped to <1% after this port.

The remaining gap is on passive (MAKE) fills, which neither our engine nor kevin-fu1's can fully replicate without simulating the IMC bot traders themselves. See [`../methodology.md`](../methodology.md) for more on the live-vs-backtest divergence we tracked.

### Submission log replay

The visualizer can also ingest the IMC `submission.log` directly, which is the JSON-per-tick log format IMC produces after every backtest. Drag in `submission.log` and the viz reconstructs the full per-tick state from IMC's perspective. This mattered every time we needed to answer the question "did IMC see the same order book we did in our local runner?" The answer after the kevin-fu1 port was always yes, which gave us the confidence to trust the local backtester for parameter tuning.

### The Bloomberg terminal aesthetic

After the third rewrite of the dashboard, the visual style consolidated on a Bloomberg-terminal aesthetic: fixed-width fonts, cyan and amber and orange accents, dark background, dense data. This is also why the repo is named `graphIMC` and not something more generic like `imc-viz`. The inspiration was an FX desk's intraday monitoring screen; I wanted the iteration loop to feel like watching a market in real time, not like running a test harness.

## The backtester (runner.py)

`runner.py` is a single-file Python harness that:

1. Loads any number of `prices_round_*_day_*.csv` and `trades_round_*_day_*.csv` files.
2. Reconstructs the full `TradingState` per tick, including order depths plus own/market trades plus observations.
3. Calls a user-supplied `Trader().run(state)`.
4. Applies the submitted orders against the order book using the kevin-fu1 matching engine.
5. Tracks per-product PnL, position, and fills.
6. Emits a `submission.log` in IMC's format, so the result is viewable in the visualizer.

Usage looks like this:

```bash
cd algos/
python3 runner.py strategies/v50_edge12.py 2          # day 2 only
python3 runner.py strategies/v50_edge12.py            # all days
python3 runner.py strategies/v50_edge12.py 2 --ticks 1000   # 1k tick horizon
```

The `--ticks 1000` flag is critical because IMC's 1k vs 10k horizon split is the single most important scoring fact across the entire competition (see [`../methodology.md`](../methodology.md)).

## The sweep harness

`tools/sweep.py` runs a single parameter through a list of values and emits a response curve:

```bash
python3 tools/sweep.py strategies/v50_edge12.py hg_edge 5 7 10 12 15
```

The output is a table of `(value, PnL, drawdown, Sharpe)` rows per value swept. The visualizer's Parameter Lab consumes the same sweep output and renders the response curve interactively, which is how we eyeballed plateau-versus-cliff parameter responses without staring at numbers.

For multi-parameter sweeps we used `tools/sweep_3day.py` (parallelized across days) and `tools/iterate_loop.py` (full coordinate descent across all axes). Round 3 alone ran roughly 1,000 single-parameter sweeps, most of which are still visible in `algos/results/`. Round 5 ran several thousand walkforward splits via `algos/r5/walkforward.py`.

The visualizer is the piece of the tooling that made the most difference per hour spent building it. If we had to keep one tool from this entire competition for next year, the Discord scraper is the obvious answer; the visualizer is the close second, because it is the difference between a strategy iteration loop that takes ten minutes and one that takes one.

(If we ever cleaned this up to publish, `runner.py`, the visualizer's `index.html`, `tools/sweep.py`, and `algos/r5/verify_submission.py` are the four pieces that generalize. The ~1,700 strategy files and the per-round findings docs are too round-specific to be worth releasing.)

---

**The visualizer is live at https://imc-prosperity-visualizer.vercel.app** — drop in any IMC CSV bundle and submission log to see the dashboard.
