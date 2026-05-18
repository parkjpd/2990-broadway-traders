# Round 5 — Manual: Ignith Portfolio (+$123,354, rank 28 globally)

This is the one. Of all five rounds, R5 manual is the one I would put on a billboard for the team. We finished 28th globally out of the 18,800+ teams in the competition on this round alone, which is the top 0.15%, and made +$123,354 in a single submission. And although I want to argue the strategy was the result of weeks of preparation, the honest answer is that the math agreed with the Discord scraper at the right moment, and we listened.

So what actually happened? Why did this round work when R3 and R4 manuals (442nd and 256th respectively) did not? Moreover, why should the closed-form solution we used be seen as something more than a textbook exercise? Those are the three questions this writeup tries to answer.

## The setup

We were given 9 news articles about made-up volcanic-themed products on a market called "Ignith." Each article tells you something about a product, whether bullish, bearish, or deliberately ambiguous. The task is to allocate up to 100% of a $1,000,000 budget across them, with each integer percentage point carrying a quadratic fee, and your PnL coming back as `sum(side · realized_return · investment) − fees`, averaged across 100 GBM simulations.

The 9 products: Pyroflex Cells, Lava Cake, Thermalite Core, Obsidian Cutlery, Magma Ink, Scoria Paste, Ashes of the Phoenix, Volcanic Incense, and Sulfur Reactor. Six of them had clear directional signal in the article text; three of them were traps where the math said "do nothing."

## The actual math

The allocation $\pi_i$ is an integer percentage. With side $s_i \in \{+1, -1\}$ and realized return $R_i$:

- Investment: $\pi_i \cdot 10{,}000$ dollars, on a $1M budget
- Gross PnL: $s_i \cdot R_i \cdot \pi_i \cdot 10{,}000$
- Fee: $\pi_i^2 \cdot 100$, and this is the whole game
- Net: gross − fee

Quadratic fees mean concentration is punished. You cannot simply pile 100% on your single best pick, because the fee on a 100% allocation alone is $\$1,000,000$, which wipes out your investment regardless of direction.

The fee formula was confirmed against Adi's example in Discord (`prosperity-intel`, 04-28 16:06), where 5% allocation on a $50k budget yielded a $125 fee, matching $(5/100)^2 \cdot 50000$ exactly. Alongside that, Hrvoje (mod) confirmed that returns are anchored on **news sentiment** with a small player-positioning correction:

> "If our range is [x, y] and people mostly submit buy, it will be closer to y. We have an anchor value, that we think it's most fair."

So consensus drives the realized $R$ toward the favorable bound. That mattered enormously for sizing, because it meant the right portfolio was the one that matched what other people would also submit, not the one that "felt right" from reading the article in isolation.

### The optimal-π closed form

We modeled direction uncertainty with $p_i = $ P(our chosen side wins). The realized side matches our pick with probability $p$, opposes with $1-p$. Plugging that into expected net per leg:

$$
\mathbb{E}[\text{Net}_i] = (2p_i - 1)\cdot R_i \cdot \pi_i \cdot 10{,}000 - \pi_i^2 \cdot 100
$$

Taking $\partial / \partial \pi_i$ and setting to zero gives:

$$
\boxed{\pi_i^* = (2p_i - 1)\cdot R_i \cdot 50}
$$

Two corollaries dropped out of this and ended up driving the whole strategy:

First, when our direction is certain ($p = 1$), $\pi^* = 50 R$, meaning a 20% expected move translates to a 10% allocation. Second, when our prior is a coin flip ($p = 0.5$), $\pi^* = 0$. Do not trade what you do not have a view on. That second corollary is what killed Magma Ink, Volcanic Incense, and Scoria Paste for us, because once we sat down and assigned honest $p$ values to each, both BUY and SELL had negative expected EV on those three products.

We verified the closed form against a `cvxpy` Clarabel solve of the full 9-product objective with $\text{cp.norm}(\pi, 1) \leq 100$. The two agreed to within ±1 integer rounding on every leg.

## Where the priors came from

Three sources stacked on top of each other to give us our $R_i$ and $p_i$ values: first, the article text itself; second, a Prosperity 3 Round 5 → Prosperity 4 Round 5 product mapping that three independent top-tier Discord users converged on the night before submission; and third, Hrvoje's hints about "priced in from the past" sentiment.

The mapping was the alpha. Three independent players on `#general` arrived at the same translation between this year's products and last year's, and they did so without coordinating with each other.

Mosho (`༺ mosho ༻`) at 04-30 00:24, after five edit-iterations all preserved in the deletions table:
> Cutlery: bullish, ~20% [last year red flag move 50%, but previous hype]
> Pyroflex: bearish, -9% [last year confirmed]
> Thermalite: bullish, 20% [last year confirmed]
> Lava Cake: strong bearish, -60% [last year confirmed]
> Sulfur: bullish, perhaps priced in, ~5%?

Zain at 04-30 00:30:
> obsidian cutlery = red flags a little bit
> lava cake = quantum coffee
> thermalite is just like vr from last year
> solar panels = pyroflex
> we got a 300kish on the backtester

Suahs at 04-30 00:00–00:33:
> red flags = cutlery
> vs = therma
> yea my highest move is lava
> I said tax one would go down like 15%
> i might j go like 20-25% bullish
> real life doesn't matter its how ppl think it'll move

That last line from Suahs is the entire game. The seed maker anchors on **news sentiment** plus **prior-edition return distributions**, not on real-world fundamentals; therefore the right portfolio is the one that matches the previous-year analog product, not the one that "feels right" from the article alone.

P3R5's actual realized moves were public on Timo Diehm's repo: Solar Panels −8.9%, Quantum Coffee −66.79%, VR Monocle +22.40%, Red Flags +50.90%, Striped Shirts +0.21%. That was our reference table, and once we trusted the mapping, the magnitudes mostly fell out of it.

## Per-product write-up

### Pyroflex Cells — SELL 5

> "The Ignith Tax Authority is facing mounting pressure from energy-sector representatives following its decision to discontinue the Pyroflex Cell Tax Cut, **effective tomorrow**. The effectiveness of the 50% PCTC ... has been the subject of **increasing public criticism in recent months**. ... the **abrupt cancellation of the cut, which effectively doubles the current levy**, will disrupt consumer upgrade cycles and slow new purchases."

The direction here is obvious: tax doubles, demand drops, so SELL. The harder question, and the one we initially got wrong, was magnitude.

The article has three "priced-in" tells. "Following its decision" is past tense. "Recent months of public criticism" indicates a known issue. "Effective tomorrow" means only the calendar trigger is fresh, not the news itself. Together, those three phrases shine a light on the fact that this product had already absorbed most of the bear pricing before the article dropped.

That maps Pyroflex to Solar Panels in P3R5, which moved −8.9%. Zain explicitly said *"solar panels = pyroflex,"* Mosho independently arrived at "−9%," and Suahs went slightly more aggressive at "−15%."

We took $R = -12\%$ and $p = 0.95$. The closed form gives $\pi^* = 0.9 \cdot 12 \cdot 50 / 100 = 5.4$, rounded to **5**.

This was actually a late-stage downsize. Our original portfolio had Pyroflex SELL **25**, because we were treating it like a fresh shock with $R \approx -50\%$. One of our team members pushed back hard, arguing that *"the tax cut removal was announced months ago — only the effective date is new. This is priced in."* He was right. That single re-read saved us roughly $21k (more on this in "What worked" below).

### Lava Cake — SELL 28 (the big one)

> "Health authorities have launched a formal review after laboratory tests **confirmed traces of actual lava** in the wildly popular Lava Cakes. The discovery prompted an **immediate halt in sales** ... civil lawsuits are already piling up and **vendors are quick to return their stock with lawyer letters attached.**"

Sales halted, lawsuits piling up, supply-chain abandonment. This is breaking news, not priced-in. The direction is strong SELL, and the magnitude is large.

P3R5 analog: Quantum Coffee, which moved −66.79%. Zain spelled it out as *"lava cake = quantum coffee."* Mosho wrote *"strong bearish, −60% [last year confirmed]."* Suahs at 04-30 00:14 said *"yea my highest move is lava."*

We took $R = -60\%$ and $p = 0.97$. The closed form gives $\pi^* = 0.94 \cdot 60 \cdot 50 / 100 = 28.2 \rightarrow$ **28**.

This single position was 80% of our P&L. If we got Lava Cake wrong, the rest of the portfolio would not have mattered. We got it right; the realized $R$ came in at −63.35%, almost exactly the Quantum Coffee analog magnitude, for +$98,990 on this leg alone.

### Thermalite Core — BUY 9

> "Active projected users **rising from 1.42 million this quarter to 3.89 million next quarter** ... 16 hours and 42 minutes per day, indicating more sustained household use ... analysts to speculate about a **very strong next quarter**."

A 2.74× user growth combined with sticky usage is a bullish setup. P3R5 analog is VR Monocle (+22.4%). Zain said *"thermalite is just like vr from last year,"* Mosho wrote *"bullish, 20%,"* Suahs said *"i might j go like 20-25% bullish ig,"* and fantan at 04-29 22:36 said *"im fullporting thermalite calls."*

We took $R = +22\%$ and $p = 0.92$, which gives $\pi^* = 0.84 \cdot 22 \cdot 50 / 100 = 9.24 \rightarrow$ **9**.

Like Pyroflex, this was downsized from an original BUY 22 (we had assumed $R \approx +45\%$). Same priced-in logic: the forecast was the news, but the underlying growth story has been visible for a while.

### Obsidian Cutlery — BUY 4 (the controversial flip)

> "A large-scale manufacturing facility **suspended obsidian cutlery production** after completed blades **sliced through portions of the chemical assembly line** ... industry experts warned **the incident could have implications for other manufacturing facilities.**"

This is the trade I am still most proud of, because the naïve read of the article is wrong in a really specific way.

The naïve interpretation: "production halt + contamination = bad news = SELL." And that read is correct if you are trading the company stock (Eternal Cutlery Ltd.). However, we were not trading the company. We were trading the **commodity**. Less production with stable demand means the commodity becomes scarce and the price goes up, not down. The P3R5 analog is Red Flags (+50.9%), where the same supply-shock dynamic played out.

Discord was split on direction, and that split is the entire reason this trade was hard. The BUY camp:

- **Suahs:** *"its a supply shock... the factory broke down."*
- **Zain:** *"obsidian cutlery = red flags a little bit... also supply scarcity. no comment from factory staff either, potential for other manufacturing plants to shut down ... hence an increase, but less so than red flags [because there's no prior hype]."*
- **Mosho:** *"Cutlery: bullish, ~20%."*
- Plus Loser, Ben, Sean, Weavedis, narwhalsaregreat, for nine voices in total.

The SELL camp:

- **!John:** *"isn't it a manufacturing halt with contamination? How does that map to Red Flags?"*
- **ChummyBigfoot86, gafa, Devgamer_05** (conflicted), for four in total.

Vote tally was 9 BUY against 4 SELL, which gives $P(\text{BUY correct}) \approx 9/13 \approx 0.69$. The math then says $R = +20\%$, $p = 0.69$, so $\pi^* = 0.38 \cdot 20 \cdot 50 / 100 = 3.8 \rightarrow$ **4**.

Our original portfolio had **SELL 2** on Obsidian. Flipping it from SELL to BUY was the single largest direction change we made on any product, in any round, of the entire competition. The math justified the flip at any $P(\text{BUY correct}) > 0.46$, and with 0.69 we were confidently above that threshold; however, we kept the size small because direction was contested, and the responsible thing to do with a contested call is to let the position size reflect that contest.

One team member DM'd us *"1-2 are quite different to ours but yeah seems good"*, referring to his team's portfolio. Reading between the lines, Obsidian direction was almost certainly one of those one or two.

### Sulfur Reactor — BUY 2

> "Elemental Index 118 will add Sulfur Ltd. in its upcoming rebalance ... Funds tracking the index are expected to adjust their holdings accordingly **once the rebalance takes effect later this cycle**."

The direction is BUY (index inclusion forces fund buying). Two issues kept the size small.

The first issue: "later this cycle." Ben in `prosperity-intel` (04-30 03:39) said *"later this cycle for sulfur means likely out of our timeframe."* If the rebalance happens after the simulator's window, the realized return goes to zero.

The second issue: Sulfur Reactor versus Sulfur Ltd. Pine1pple at 04-29 03:08 raised the question directly: *"do funds tracking the elemental index buy the physical reactors, or do they buy equity in Sulfur Ltd.? In real markets it'd be equity."* If the funds buy equity in the parent company, the commodity price barely moves.

Mosho wrote *"Sulfur: bullish, perhaps priced in, ~5%?"*, which matches both of these uncertainties.

We took $R = +5\%$ and $p = 0.85$, so $\pi^* = 1.75 \rightarrow$ **2**. The realized $R$ came in at +17.4%, which means we were way under here. See "What we missed" later.

### Ashes of the Phoenix — SELL 4

> "Public concern escalated after a recently resurfaced video shows the sourcing method ... 'birds who, we would like to emphasize once more, are **actually immortal**.'"

PR scandal plus an absurd "actually immortal" defense reads as SELL. Mosho: *"bearish, ~10%?"* Ben: *"sells Lava Cake 1, Ashes 2."*

We took $R = -12\%$ and $p = 0.80$, so $\pi^* = 3.6 \rightarrow$ **4**.

### The three skips

| Product | Why we skipped |
|-|-|
| **Magma Ink** | "Was sold **yesterday**" combined with "hot drop." Hrvoje called this *"priced in from the past."* Expected $R \approx 0$. |
| **Volcanic Incense** | "Whiff Nostralico" plus "concentrated buying within narrow time windows" plus "follow his lead and buy." Classic pump-and-dump structure. The mod's range setting was genuinely 50/50 ambiguous, which meant both LONG and SHORT carried negative EV. |
| **Scoria Paste** | "Lava D. Ray, **self-proclaimed market medium** ... 'took its temperature'." Article was clearly mocking. Mosho mapped it to P3R5 Striped Shirts (+0.21%), which is statistically zero. |

For Volcanic Incense, the math is worth showing explicitly. At $\pi = 3$ LONG with $P(\text{positive } R) = 0.55$ and $R = \pm 10\%$:

$$
\mathbb{E}[\text{Net}] = 0.55 \cdot 3000 + 0.45 \cdot (-3000) - 900 = -\$600
$$

SHORT at $\pi = 3$ with the symmetric prior gives $-\$1,200$. Both directions have negative EV. The EV-max choice is to skip, and that is what we did. (Three teams we know about did *not* skip and lost money on it.)

## The submission

| Product | Side | $\pi$ | Investment | Fee | Closed-form $\pi^*$ |
|-|-|-|-|-|-|
| **Lava Cake** | SELL | **28** | $280,000 | $78,400 | 28.20 |
| **Thermalite Core** | BUY | **9** | $90,000 | $8,100 | 9.24 |
| **Pyroflex Cells** | SELL | **5** | $50,000 | $2,500 | 5.40 |
| **Obsidian Cutlery** | BUY | **4** | $40,000 | $1,600 | 3.80 |
| **Ashes of the Phoenix** | SELL | **4** | $40,000 | $1,600 | 3.60 |
| **Sulfur Reactor** | BUY | **2** | $20,000 | $400 | 1.75 |
| Magma Ink | SKIP | 0 | $0 | $0 | 0 |
| Volcanic Incense | SKIP | 0 | $0 | $0 | 0 |
| Scoria Paste | SKIP | 0 | $0 | $0 | 0 |
| | | **52** | **$520,000** | **$92,600** | |

Every $\pi$ in the submission rounds the closed-form $\pi^*$ to the nearest integer. Total allocation is 52%, total fee is $92,600.

## How we got to v4

It took us four versions to land on the submitted portfolio. I think the gaps between versions are worth showing, because they illuminate which prior changes actually moved the needle.

**v1 — own-magnitudes.** Pyroflex SELL 25, Lava SELL 25, Therm BUY 22, Obsidian SELL 2, Sulfur 5, Ashes 5, Magma 2. We were 86% allocated with $172k in fees. We had assumed strong-news translates to ±50% moves; we were wrong on Obsidian direction, and wrong on Pyroflex magnitude.

**v2 / v3 — after the Discord mapping landed.** Pyroflex SELL 11, Lava SELL 30, Therm BUY 12, Obsidian BUY 7, Sulfur 2, Ashes 5. We were 67% allocated with $147k in fees. Direction was correct on every leg now (Obsidian had flipped to BUY), but we were still slightly over-sized; we had not pushed hard enough on Hrvoje's "priced in" hint for Pyroflex.

**v3.5 — partial-pivot compromise.** Pyroflex 7, Lava 30, Therm 10, Obsidian 5, Sulfur 2, Ashes 5. 59% allocated, $110k in fees. One team member preferred this; he saw it as a middle ground between v3 and the cvxpy optimum.

**v4 — math optimum (shipped).** (5, 28, 9, 4, 2, 4). 52% allocated, $93k in fees. This is exactly what the closed form said to do. Before shipping, we ran a 5,000-draw Monte Carlo against all three versions:

| Metric | v3 | v3.5 | **v4 (shipped)** |
|-|-|-|-|
| Mean EV | $86,893 | $88,478 | **$89,729** |
| Median EV | $85,483 | $86,983 | **$88,349** |
| 5%ile downside | $46,194 | $47,891 | **$51,907** |
| 95%ile | $129,345 | $131,038 | $129,436 |
| P(v4 ≥ alt) | 100% | 75% | — |

v4 dominated v3 across all 5,000 MC draws. v4 beat v3.5 in 75% of them. Mean improvement against v3 was +$2,836, and most of that improvement comes from saving fees ($117k → $93k = $24k saved) at the cost of negligible EV.

The thing that finally tipped the decision: chrispyroberts (#7 globally, P3R5) had used exactly this cvxpy convex-optimization approach to win 1st in NA on the previous edition. We replicated his code on Nirav's P3R5 sentiments and got $174,562 continuous optimum and $134,881 realized on the actual P3R5 returns; chrispyroberts reported $138,274 actual, matching within $4k. So the framework itself was validated against a known winner.

## Realized P&L

| Product | Side | $\pi$ | Predicted $R$ | **Realized $R$** | P&L |
|-|-|-|-|-|-|
| Lava Cake | SELL | 28 | −60% | **−63.35%** | **+$98,990** |
| Thermalite Core | BUY | 9 | +22% | **+22.16%** | **+$11,844** |
| Pyroflex Cells | SELL | 5 | −12% | **−19.53%** | **+$7,267** |
| Sulfur Reactor | BUY | 2 | +5% | **+17.43%** | **+$3,085** |
| Obsidian Cutlery | BUY | 4 | +20% | **+9.92%** | **+$2,366** |
| Ashes of the Phoenix | SELL | 4 | −12% | **−3.50%** | **−$198** |
| Magma Ink | SKIP | 0 | priced in | — | $0 |
| Volcanic Incense | SKIP | 0 | trap | — | $0 |
| Scoria Paste | SKIP | 0 | flat | — | $0 |
| | | | | **TOTAL** | **+$123,354** |

The realized $R$ values are recoverable from the IMC results table via $R_i = (\text{net}_i + \text{fee}_i) / (s_i \cdot \pi_i \cdot 10{,}000)$. For example on Lava Cake: $(98990 + 78400) / (1 \cdot 28 \cdot 10000) = 177390 / 280000 = 0.6335 = 63.35\%$.

Direction accuracy: **6 of 6 traded legs correct.** Five winners plus one small loss on Ashes, where the realized magnitude was smaller than our prior so the fee just edged out the gross.

## What worked

The Lava Cake position at 28% was the single best decision of the entire competition for us. $98,990 of $123,354, which is 80% of total, came from this one leg. The closed form said 28.2 and we shipped 28. Realized $R$ came in at −63.35%, which is squarely within Zain's "lava cake = quantum coffee" mapping range (P3R5 Quantum Coffee was −66.79%). And if we had shipped the v1 portfolio with Lava SELL 25, we would have made $87,500 on this leg, which is $11k less.

The Obsidian flip held. Direction was right (+9.92% realized) even though magnitude undershot the +20% mapped estimate. If we had kept v1's SELL 2 instead of flipping to BUY 4, we would have lost roughly $1,500 against the +$2,366 we actually made; that is a $4k swing on the flip alone.

The Pyroflex priced-in catch was worth the most relative to its position size. v1 had SELL 25 expecting $R \approx -50\%$. The actual $R$ came in at −19.5%. At $\pi = 25$ with $R = -19.5\%$, the net is $25 \cdot 19.5 \cdot 100 - 62500 = -\$13,750$. At $\pi = 5$, the net is $+\$7,267$. The catch alone saved us roughly $21k.

The three skips were correct. Volcanic Incense and Scoria Paste both ended up with realized $R$ that confirmed "trap" (we know from post-game Discord); skipping them on negative EV math was the right call.

## What we missed

Sulfur Reactor was a lot bigger than we expected. Realized $R$ was +17.4% against our +5% prior. At the post-hoc optimal $\pi^*(R = 17.4\%) = 0.7 \cdot 17.4 \cdot 50 / 100 \approx 6$, we should have been at 6% rather than 2%. The net at $\pi = 6$ would have been around $\$8,500$; we made $\$3,085$. Roughly $5,400 left on the table because we trusted Ben's "later this cycle is out of timeframe" interpretation too hard.

Obsidian was about half what we mapped. +9.9% realized vs. +20% mapped. Direction was right; magnitude underperformed because Zain's "less than Red Flags because no prior hype" caveat hit harder than we accounted for.

Ashes was almost flat. −3.5% vs. our −12% prior. The "actually immortal" defense apparently calmed the seed maker's bear pricing more than we thought it would.

## The 48% buffer was the right hedge

This is the part of the strategy I would defend hardest if pushed on it. We left 48% of the budget unspent. Some other top teams used 90%+. Why we did not:

First, the fee curve is convex ($\text{fee} = \pi^2 \cdot \$100$), so over-allocation costs disproportionately. Going from $\pi = 5$ to $\pi = 10$ doubles your gross but quadruples your fee.

Second, even with the Discord mapping, the probability of getting the mapping wrong on any given product is non-trivial; we estimated roughly 30% across the portfolio. Leaving room means we do not pay fees on weak-conviction legs.

Third, Hrvoje had confirmed in R4 that the simulator punishes over-hedging. Under-utilization is fine; over-utilization burns fees with no marginal upside.

The buffer saved us $24k in fees against v3 alone. That is almost 20% of our final P&L right there, just from not over-allocating.

## Tools that mattered

`prosperity-intel` was the Discord scraper running on a DigitalOcean droplet with hourly LLM extraction into SQLite. 161,801 messages were indexed at submission time. The entire P3R5 → P4R5 mapping insight came from this tool, not from our own first-principles analysis. See [`tools/prosperity-intel.md`](../../tools/prosperity-intel.md).

`cvxpy` (Clarabel) verified the closed-form $\pi^* = (2p-1)\cdot R \cdot 50$ against the full convex objective. The two answers agreed to ±1 integer rounding on every leg.

A 5,000-draw Monte Carlo validated v4 against v3 and v3.5 under prior uncertainty. This is what gave us the confidence to ship the mathematically optimal portfolio rather than a more conservative compromise.

Full intel dump and sensitivity runs are in [`findings/`](findings/).

## Looking back

The math was always going to be the easy part. The closed-form $\pi^* = (2p-1)\cdot R \cdot 50$ falls out of a single derivative, and the convex-optimization framework had already been validated by chrispyroberts in P3R5. What was hard was the inputs, the $R_i$ and $p_i$ for each of the nine products, and we only got those right because three Discord users we had never met fed us the P3R5 → P4R5 mapping in real time. The Obsidian flip in particular would never have happened without that consensus signal.

The math said what to do, but it could only say it because the priors were good. And the priors were good because we were listening.

## Final placement

| Metric | Value |
|-|-|
| Manual P&L (R5 round) | **+$123,354** |
| R5 round manual rank | **28th globally** |
| Direction accuracy | 6/6 |
| Total invested | $520,000 / $1,000,000 |
| Total fee | $92,600 |
| Cumulative manual rank (3 rounds) | **#65 global / #24 NA** |
| Cumulative XIREC after R5 | $519,728 |
| Final overall position | #164 global / #46 NA |
