# IMC Prosperity 4 — 2990 Broadway Traders

<!--
  Team photos live in .github/team/. Replace those files with real headshots
  to swap each avatar; see .github/team/README.md for filename conventions.
-->
<table>
<tr>
<td align="center">
  <a href="https://www.linkedin.com/in/parkjpd/">
    <img src=".github/team/davidpark.jpg" width="90" height="90" /><br />
    <sub><b>David Park</b></sub>
  </a><br />
  <sub>algo · manual · graphIMC · discord intel</sub>
</td>
<td align="center">
  <a href="https://www.linkedin.com/in/oliverzhou77/">
    <img src=".github/team/oliverzhou.jpg" width="90" height="90" /><br />
    <sub><b>Oliver Zhou</b></sub>
  </a><br />
  <sub>algo · manual · methodology</sub>
</td>
<td align="center">
  <a href="https://www.linkedin.com/in/taffy-jackson-cfa-8b6a4a22a/">
    <img src=".github/team/taffyjackson.jpg" width="90" height="90" /><br />
    <sub><b>Taffy Jackson</b></sub>
  </a><br />
  <sub>algo · chooser arb · lessons</sub>
</td>
<td align="center">
  <a href="https://www.linkedin.com/in/jaidkamdar/">
    <img src=".github/team/jaikamdar.jpg" width="90" height="90" /><br />
    <sub><b>Jai Kamdar</b></sub>
  </a><br />
  <sub>algo · auction · manual</sub>
</td>
<td align="center">
  <a href="https://www.linkedin.com/in/heomin/">
    <img src=".github/team/minheo.jpg" width="90" height="90" /><br />
    <sub><b>Min Heo</b></sub>
  </a><br />
  <sub>R3 + R5 algos · writeup</sub>
</td>
</tr>
</table>

**Final standings (May 13, 2026):**

Out of **18,800+ teams** in IMC Prosperity 4:

| Category | Global | NA |
|-|-|-|
| Overall | **#164** (top 0.87%) | **#46** |
| Algorithmic | #253 (top 1.35%) | **#73** |
| Manual (cumulative) | **#65** (top 0.35%) | **#24** |
| Cumulative XIREC | $519,728 | |

R5 manual round alone: **rank 28 globally** (top 0.15%, +$123,354) — our standout single result.

---

## The biggest thing we learned

Closed-form solutions like the Rubinstein chooser identity or the portfolio optimum $\pi^* = (2p-1)\cdot R \cdot 50$ are the easy part of these rounds. The hard part is the inputs: the $R$, the $p$, the confidence levels. Those don't come from another sheet of paper. They come from reading how other top players are talking about a product on Discord at 2 AM.

The Obsidian flip is the cleanest example we have. The math was unambiguous (at any P(BUY correct) > 0.46, the flip is +EV), but P(BUY correct) is a human number, not a derived one. We did not compute it from first principles. We counted: 9 named players said BUY, 4 said SELL, weighted by how confident each post sounded (Suahs's *"its a supply shock, the factory broke down"* gets more weight than ChummyBigfoot86's two-word *"is a sell"*). Final tally was 9/13 = 0.69, well above 0.46. We flipped. Realized direction came in correct, +$2,366 P&L.

Pyroflex was the same kind of catch. The article said "tax doubles tomorrow," which sounds like a fresh shock. The reason we knew it wasn't came from re-reading the article as a human: "following its decision," "recent months of public criticism," "effective tomorrow." Three phrases that together mean "this is already in the price." No equation would have flagged that; a person noticed it. And we only knew to look that hard because Mosho's `BEFORE: ... -5%` → `AFTER: ... -9%` edit in the deletions table told us he had been wrestling with the same question.

The Discord scraper, in the end, was not just a research tool. It was a way to pull priors out of the only source that could supply them, which was other humans who knew something we didn't, were communicating it in real time, and occasionally let it slip in the form of an edited post or a 30-second-old deletion.

If we had to compress the entire competition into one line: **math sets the ceiling, humans fill in the priors.**

---

## Repos that supported this one

- **[graphIMC](https://github.com/parkjpd/graphIMC)** — our local backtester, browser-based visualizer ("Bloomberg-style" dashboard), parameter-sweep harness, and the home of every strategy iteration we ran (~1,700 versions across rounds 3 + 5 alone).
- **[prosperity-intel](https://github.com/parkjpd/prosperity-intel)** — Discord intel pipeline (selfbot → SQLite → LLM extractor → digest) that scraped the official IMC Prosperity Discord 24/7 to feed competitor signal into our research process.

---

## Results

### Profit / loss by round

We didn't formally participate in tutorial / R1 / R2 (no carry-forward PnL into R3). This writeup covers R3–R5, where our XIREC actually accumulated.

| Round | Manual | Algo | Round total | Cumulative |
|-|-|-|-|-|
| 3 | +$70,444 | +$96,155 | +$166,599 | $166,599 |
| 4 | +$63,019 | +$164,004 | +$227,023 | $393,622 |
| 5 | +$123,354 | +$2,752 | +$126,106 | $519,728 |

### Per-round leaderboard positions

| Round | Round overall | Round manual | Round algo |
|-|-|-|-|
| 3 | 313th | 442nd | 282nd |
| 4 | 154th | 256th | 168th |
| 5 | **164th** | **28th** | 977th |

### Round-by-round narrative

- **R3** ($166,599 / 313th): Established the iteration pipeline. Manual was a sealed two-bid auction (placed mid-pack, partly under-bid). Algo iterated `v02 → v50` on HYDROGEL_PACK + VELVETFRUIT_EXTRACT + 10× VEV_K options.
- **R4** ($227,023 / 154th, **+159 spots**): Manual was the keystone — chooser-option arbitrage via Rubinstein static replication (+$60k structural edge captured). Algo carried R3 strategy forward with smile-IV refinement.
- **R5** ($519,728 / 164th, −10 spots): Manual ranked **28th globally** (+$123k from a 9-product portfolio allocation), driven by Discord-mined P3R5→P4R5 product mapping. Algo regressed (50 new products + pair-trading model that diverged from live) — the rank drop is entirely from underperforming algo, not manual.

### Submissions

| Round | Algo file | Notes |
|-|-|-|
| 3 | [`rounds/round3/algo.py`](rounds/round3/algo.py) | HYDROGEL_PACK, VELVETFRUIT_EXTRACT, 10× VEV_K options |
| 4 | [`rounds/round4/algo.py`](rounds/round4/algo.py) | R3 carryover + smile-IV refinement |
| 5 | [`rounds/round5/algo.py`](rounds/round5/algo.py) | 50-product cluster universe + PEBBLES basket |

---

## Repository layout

```
.
├── README.md                  ← you are here
├── manuals.md                 ← cross-round manual story
├── methodology.md             ← cross-round process notes
├── rounds/
│   ├── round3/
│   │   ├── README.md
│   │   ├── algo.py
│   │   └── manual.md
│   ├── round4/    …
│   └── round5/    …
└── tools/
    ├── graphimc.md            ← backtester + visualizer overview
    └── prosperity-intel.md    ← discord intel pipeline overview
```

Every round folder is self-contained: the **writeup** explains the problem, what we tried, what shipped, and why; the **algo** is the exact file we submitted; the **manual** notes capture the manual-trading decision and the reasoning behind it.

For a cross-round view of the three manual rounds (and the math behind each), see [`manuals.md`](manuals.md).

---

## Process notes

A few things shaped how we worked, and they show up across every round:

1. **Sweep-then-decide.** We almost never tuned a parameter by hand. The flow was: write a strategy, expose 3–6 hyperparameters, sweep them with the runner against the 3 days of data IMC released, look at the response curve. The Round 3 README is full of `vXX → vYY` jumps that come straight out of these sweeps.
2. **Two horizons.** IMC scores submissions on a **1,000-tick** intermediate run during the round and a **10,000-tick** final run at the end. These two horizons want different strategies — short-horizon punishes drift exposure and rewards aggression, long-horizon rewards mean-reversion that needs time to play out. Almost every round we built a "1k pick" and a "10k pick" and decided which to ship based on the scoring rules in effect.
3. **Backtester vs. live divergence.** Our local runner (in `graphIMC/algos/runner.py`) hits 99–100% match with IMC's live PnL on the take side, but cannot fully simulate passive (MAKE) fills. We tracked this gap explicitly — see the Round 3 writeup for several `vXX` versions that were "backtest neutral, +$5–15k live expected".
4. **Discord intel as a signal source.** See the thesis section above. R5 manual is the marquee example.
5. **Single-file submission discipline.** IMC requires a single Python file with no `sys.path.insert` and a tight import allowlist. We had a `verify_submission.py` script that re-ran static + behavioral checks on every md5 change of `<round>_submission.py`.

See [`methodology.md`](methodology.md) for the full picture.

---

## Acknowledgements

- **IMC Prosperity team** — for an amazing competition.
- **Jasper (mod)** — for clear answers in `#announcements` that resolved several scoring ambiguities (notably the 1k-vs-10k horizon question).
- **The open-source backtester authors** — particularly [`jmerle/imc-prosperity-3-backtester`](https://github.com/jmerle/imc-prosperity-3-backtester) and [`kevin-fu1/imc-prosperity-4-backtester`](https://github.com/kevin-fu1/imc-prosperity-4-backtester), whose order-matching engines we studied to align ours with the live sandbox.
- **Discord regulars** — including the mod team, several top teams whose public discussion we tracked, and the `#open-source` contributors who shipped the visualizer and submitter ecosystems.
