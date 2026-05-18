# Manual rounds — the cross-round story

We played three manual rounds across Prosperity 4. On the surface they look like three different games (a sealed auction, an options chain, and a 9-product portfolio allocation), and they are. The meta underneath all three is the same, though: the seed maker publishes a brief, the math has a closed form sitting in plain sight, and the alpha that closes the gap between "decent result" and "top-30 result" comes from the Discord.

Combined manual P&L was **+$256,817 across 3 rounds**, and the cumulative manual leaderboard came in at **#65 globally and #24 NA** out of the 18,800+ teams in the competition (top 0.35% globally). R5 manual was our best single round (rank 28 globally, top 0.15%), and 24% of our entire cumulative XIREC came from that one round alone.

## Headline numbers

| Round | Manual P&L | Round rank | Format | Our take |
|-|-|-|-|-|
| R3 | +$70,444 | 442nd | Sealed two-bid auction | OK result. Cost us $13k by under-bidding the global mean. |
| R4 | +$63,019 | 256th | Options chain (vanillas + chooser + binary + KO) | Single trade carried the round: a chooser arbitrage worth +$60k structural. Two losing legs ate the rest. |
| R5 | **+$123,354** | **28th** | 9-product portfolio allocation | Best round of the competition. Discord scraper, closed-form sizing, all six directions correct. |
| **Cumulative** | **+$256,817** | **#65 global / #24 NA** | | |

## What the three rounds had in common

Two patterns repeated across all three rounds, and both of them are worth pulling out explicitly.

The first pattern: the math has a closed form. R3's auction had gradient ascent on $F(b_1)(920 - b_1) + (F(b_2) - F(b_1))(920 - b_2)$. R4's chooser had the Rubinstein static replication identity, $\text{Chooser} = \text{Call}(K, T) + \text{Put}(K, t)$. R5's allocation had $\pi^* = (2p-1) \cdot R \cdot 50$, which falls out of $\partial / \partial \pi$ of the expected net per leg. Every round had a textbook closed-form sitting on the table; and the rounds where we actually solved it are the rounds where we got the most lift.

The second pattern: the realized parameters came from Discord, not the brief. The brief tells you the rules. But the brief does not tell you the simulator's σ, or the discrete vs. continuous monitoring rule, or the path-averaging mechanic, or the fairness factor, or which products map to which previous-year analogs. All of those came from mod responses in `#announcements` and from competitor convergence in `#general`. By R5 we had `prosperity-intel` indexing the entire Discord 24/7, and that is the single biggest reason R5 outperformed R3 and R4.

## What the three rounds did not share

Each round had its own distinct failure mode, and the failure modes are honestly more instructive than the wins.

| Round | Failure mode | What it cost us |
|-|-|-|
| R3 | Below-mean bidding triggered a fairness penalty (~3% per point) | $13k missed (55.84% of naïve second-bid P&L) |
| R4 | Path-dependent option pricing on a discrete-monitoring simulator | $29k on the KO put long; the Broadie-Glasserman correction underestimated empirical barrier hits |
| R5 | Magnitude uncertainty on one priced-in leg | $5k missed on Sulfur (R was 3× our estimate); we trusted "out-of-timeframe" too hard |

Three different failures across three rounds, and not a single one of them came from the closed-form math being wrong; every one of them came from a prior that turned out to be miscalibrated.

## The R5 step-change

R5 (+$123k, rank 28) was an order of magnitude better than R3 (+$70k, 442nd) and R4 (+$63k, 256th). The number is striking enough that it deserves explanation. Three things changed between R4 and R5.

First, better tooling. By R5 we had `prosperity-intel` running on a DigitalOcean droplet with hourly LLM extraction. The P3R5 → P4R5 mapping was visible to us within 30 minutes of Zain's first post. We could see Mosho iterating his portfolio in real time via the `deletions` table; he edited his post five times in ten minutes, and each edit's "before" version was preserved.

Second, better math discipline. The R5 portfolio was verified two separate ways: the closed-form $\pi^* = (2p-1) \cdot R \cdot 50$, alongside a `cvxpy` Clarabel solve on the full convex objective. The two answers agreed to ±1 integer rounding on every leg. Furthermore, we Monte-Carlo'd 5,000 random prior draws and confirmed that v4 dominated v3 across all of them. The confidence we shipped with was math, not vibes.

Third, better consensus weighting. R5 was the first round where we explicitly Bayes-updated our priors on the top-team consensus, rather than relying primarily on our own first-principles fundamental read. The Obsidian flip is the clearest example: 9 top players said BUY, 4 said SELL, our own prior was SELL, and the math said the flip was +EV at any $P(\text{BUY}) > 0.46$. Vote count gave $P \approx 0.69$. We took the math over the gut and flipped.

## The chooser arbitrage (R4 deep dive)

This is the trade I am proudest of across the entire competition, because it is model-independent. Under $r = 0$:

$$
\text{Chooser}(K, T_\text{full}, t_\text{choose}) = \text{Call}(K, T_\text{full}) + \text{Put}(K, t_\text{choose})
$$

The proof relies on put-call parity alone. At the choose date $t$:

$$
\max(C, P) = \max(C, C + K - S_t) = C + (K - S_t)^+
$$

using parity $P = C + K e^{-r(T-t)} - S_t$ at $r = 0$.

So holding "+1 Call(T) + 1 Put(t)" from $t = 0$ replicates the chooser modulo a single zero-cost rebalance at $t$. The mod was quoting the chooser **40 cents above** that replication price. We sold the chooser, bought the replication:

$$
0.40 \cdot 3{,}000 \cdot 50 = +\$60{,}000
$$

Structural edge, no model dependence, no Greeks, no path noise (because the residual has zero risk-neutral expectation under $r = 0$ GBM, and the 100-sim averaging crushes the variance further).

This was originally caught by hand on the manual side. We were pricing each option through Black-Scholes on paper, when one of us noticed that the chooser's fair value equaled $C + P$ exactly. We cross-checked against the cvxpy work on the other side and recognized the static-rep identity together. It is the one time in the entire competition where a hand calculation beat the algorithmic search.

## The R5 portfolio in one equation

For each of 9 products, with allocation $\pi_i$, side $s_i \in \{+1, -1\}$, signed expected return $R_i$, and direction confidence $p_i$:

$$
\mathbb{E}[\text{net portfolio}] = \sum_{i=1}^{9} \left[ (2p_i - 1) \cdot R_i \cdot \pi_i \cdot 10{,}000 - \pi_i^2 \cdot 100 \right]
$$

subject to $\sum_i |\pi_i| \leq 100$ and $\pi_i \in \mathbb{Z}_{\geq 0}$. Maximize leg-by-leg:

$$
\pi_i^* = \lfloor (2p_i - 1) \cdot R_i \cdot 50 \rceil
$$

That is the whole game. Our submission rounded the closed form for every product, and realized 6 of 6 traded legs correct on direction for a total of +$123,354.

## Discord intel was the secret sauce

`prosperity-intel` scraped the official IMC Discord 24/7. The mechanics:

- A selfbot logged into Discord using a competition-team account, mirroring every message into a local SQLite database. Timestamps, authors, channels, edit history, and delete history were all preserved.
- An hourly LLM extraction pass via DeepSeek-V3.2 pulled structured insights into an `llm_insights` table, including instrument, direction, magnitude, and confidence.
- Roughly 162,000 messages were indexed by R5 submission night.

The `deletions` table was especially high-signal, because people delete what they regret sharing. We caught real-time portfolio shifts from top players through this table; Mosho's R5 portfolio went through five `BEFORE: ... AFTER: ...` edits as Zain and Suahs fed him P3R5 mapping data, and every iteration was preserved.

Per-round Discord alpha looked like this:

| Round | Discord-derived alpha |
|-|-|
| R3 | Lucas's per-strike P&L leak — drove R3 algo `v18 → v19` (option-sizing rebuild). Manual round had no specific intel; we were under-tooled here. |
| R4 | Mod-confirmed simulator params: σ=251%, 4 ticks/day, 100-sim averaging. Without these the chooser arb math would have been guesswork. |
| R5 | The full P3R5 → P4R5 mapping (Zain, Suahs, Mosho independently converging). Every direction call came from this. |

If we had to keep one tool from this competition for next year, it is the Discord scraper. Build it on day one. Do not wait.

## What we would repeat

The R4 chooser arb. Model-independent, structural, +$60k EV captured at low variance. We would do this every round if the chain offered it; furthermore, we would specifically look for it.

The R5 Obsidian flip from SELL to BUY. This was the most controversial single call in any round of any manual. The math said it was +EV at $P(\text{BUY}) > 0.46$; the community vote gave $P \approx 0.69$; the realized direction was correct. Took the math over the gut.

The R5 skipping of the trap products (Volcanic Incense, Scoria Paste). Both directions had negative EV under the trap setup ($\pi = 3$ LONG ≈ −$600 EV, SHORT ≈ −$1,200 EV). Doing nothing was the EV-maximizing choice. Three top-tier teams we know about did YOLO Volcanic and lost.

## What we would not repeat

The R3 below-mean bidding. Single-handedly cost us $13k. The fix is structural: in any sealed auction with a fairness mechanism, bid the upper half of the distribution. Period.

The R4 KO put position. We shipped 500 contracts of a discrete-monitoring path-dependent put on an analytic that assumed continuous-time SDE dynamics. The Broadie-Glasserman-Kou correction worked on continuous-time SDE assumptions; the realized empirical barrier hits on the discrete simulator diverged. Cost $29k. The fix is "MC against the simulator's exact dynamics, not against an analytic approximation."

The R4 T+14 ATM call long, which we added as a "vol diversifier" on top of the chooser arb. The chooser arb already handles gamma intrinsically; the extra call leg was an unnecessary directional bet. Cost $23k. The fix is "stop adding hedges to clean structural arbs."

The R5 under-sizing of Sulfur Reactor. We trusted Ben's "later this cycle = out of our timeframe" interpretation too hard and shipped $\pi = 2$ when the realized $R$ supported $\pi \approx 6$. Cost $5k.

## The thing we keep relearning: overfitting beats clever modelling

Across all three manual rounds, the pattern of our self-inflicted losses is the same. The pattern is: picking the cleverer model over the boring well-known signal.

In R3, we modelled the per-unit margin optimization, but we did not model the fairness factor (which we should have *assumed* exists in any sealed auction even if the brief does not publish it). The boring well-known signal, "bid the upper half of the distribution in any anti-collusion auction," would have caught it. We chose modelling over heuristics, and we paid for it.

In R4 on the KO put, we ran the Broadie-Glasserman-Kou discrete-monitoring analytic, which is a sophisticated correction. But the boring well-known signal, "do not price path-dependent options on a simulator you cannot directly MC against," would have caught it. We chose modelling sophistication over operational caution, and we paid for it again.

In R5 on the traps (Volcanic, Scoria), we actually did the right thing and skipped them. The well-known signal, "if both directions are negative EV under uncertainty, the EV-max choice is doing nothing," held. And although three top-tier teams went LONG on Volcanic anyway, our team's experience from R3 and R4 had drilled the heuristic into us by then.

The R5 algo result (rank 977) was the same lesson on the algorithmic side: we shipped a configuration that scored $1.1M on the 3-day backtest and got $2.7k live. We picked the version that fit the backtest hardest, rather than the version that traded the most structural signal. Pair-trading on 50 new products with 3 days of data is a textbook overfit setup.

The fix isn't to be smarter; it is to default to the strongest well-known signal and only deviate when there is a clear structural reason. The chooser arb (R4) is what this looks like at its best: zero clever modelling, just the Rubinstein parity identity, provable in two lines. We caught $60k of structural edge with high school option math; meanwhile the more elaborate KO leg in the same round lost $29k.

The R5 manual worked because we deferred to the consensus mapping (well-known signal) over our own first-principles read (clever modelling). The Obsidian flip from SELL to BUY came from listening to three top teams convergently saying "this is the Red Flags analog," not from re-reading the article harder.

The meta of all three manual rounds is the same: the math is the easy part; the priors are the hard part; and the priors come from listening, not from solving. We listened best on R5, and R5 is the round that defined our competition.

## Per-round writeups

- [`rounds/round3/manual.md`](rounds/round3/manual.md) — Sealed two-bid auction, fairness-factor recovery from realized fills
- [`rounds/round4/manual.md`](rounds/round4/manual.md) — Aether Crystal options chain, chooser arbitrage proof
- [`rounds/round5/manual.md`](rounds/round5/manual.md) — Ignith 9-product portfolio, closed-form sizing, P3R5 mapping
