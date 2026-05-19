# Round 3 — Manual: Sealed Two-Bid Auction (+$70,444, rank 442)

R3 manual wasn't the most glamorous round. There was no beautiful arbitrage identity, no strange Discord leak, no moment where the whole market suddenly opened up. We submitted two bids, got filled, and walked away with **+$70,443.80**.

Our mistake was that we under-bid into a hidden **fairness factor**. In an ordinary sealed auction, lower bids give higher per-unit margin. But in this round, bidding too low reduced fill probability but more importantly, punished the second-bid fill count itself. We thought we were being disciplined. In reality, we were making ourselves look cheap to the mechanism.

That's why this round is worth writing up. The failure mode is not specific to IMC. Any sealed-bid auction with an anti-collusion or fairness adjustment can punish the exact strategy that looks mathematically clean on the surface.

## The Setup

We submitted **two bids** $(b_1 < b_2)$ into a population of 1,000 counterparties. Each counterparty had a private reserve price drawn from some unknown distribution $F$.

If a seller’s reserve was $\leq b_1$, they sold us one unit at the higher of their reserve and $b_1$. If their reserve was in $(b_1, b_2]$, they sold at the higher of their reserve and $b_2$. Every unit could then be immediately resold to the buy-back desk at a fixed price of **920**.

So, at first glance, the problem looked like a clean optimization:

bid low enough to preserve margin, but high enough to get filled.

The catch was the second bid. The **second-bid fill count was scaled** by a fairness factor comparing our average bid

$$
\bar{b}^{(i)} = \frac{b_1 + b_2}{2}
$$

to the global average bid $\bar{b}$. Teams below the global average received reduced second-bid fills.

The brief did not publish the reserve distribution $F$. It also did not publish the exact form of the fairness factor. That made the round feel simple, but slightly deceptive. The most important variable was not just what the sellers were willing to accept. It was where our bid sat relative to everyone else’s bid.

## Our Submission

We submitted:

$$
b_1 = 751, \quad b_2 = 846
$$

At the time, the reasoning was straightforward. We wanted strong per-unit margins, and we assumed the reserve distribution was centered somewhere in the 700–900 range. Our average bid was:

$$
\frac{751 + 846}{2} = 798.5
$$

The global average first bid was **768**. The global average second bid was **859**. That means the global average bid was:

$$
\frac{768 + 859}{2} = 813.5
$$

Our average bid was **798.5**.

So we were **15 points below the global mean**.

That was the hidden wound in the submission. We did not just bid low. We bid low enough to trigger a large fairness penalty on the second leg.

## Realized Fills

| Bid | Accepted | Rejected | Buy total | Sell total | P&L |
|-|-:|-:|-:|-:|-:|
| **$b_1 = 751$** | 320 | 680 | $240,320 | $294,400 | **+$54,080** |
| **$b_2 = 846$** | 396 | 604 | $335,016 | $364,320 | **+$16,363.80** |
| | | | | **TOTAL** | **+$70,443.80** |

The table looks fine at first. But the second row is where the round was lost.

## First Bid

The first bid behaved exactly the way we expected.

320 of 1,000 sellers had reserves $\leq 751$, so:

$$
F(751) = 0.320
$$

The average price paid was:

$$
\frac{240{,}320}{320} = 751.00
$$

That means every accepted seller on the first leg was paid exactly our bid price, not their reserve. The buy-back price was 920, so the per-unit profit was:

$$
920 - 751 = 169
$$

Thus:

$$
320 \cdot 169 = 54{,}080
$$

The first leg was clean. It did what it was supposed to do. Low bid, high margin, strong realized P&L.

## Second Bid

The second bid looked good in fill count but not in realized profit.

We got 396 additional sellers with reserves in $(751, 846]$. Therefore:

$$
F(846) - F(751) = 0.396
$$

Since $F(751) = 0.320$, this implies:

$$
F(846) = 0.716
$$

Again, the average paid price was exactly **846.00**, so we paid our second bid price on every second-leg fill. The per-unit profit should have been:

$$
920 - 846 = 74
$$

The naïve second-leg profit would therefore be:

$$
396 \cdot 74 = 29{,}304
$$

But the actual second-bid P&L was only:

$$
16{,}363.80
$$

The ratio was:

$$
\frac{16{,}363.80}{29{,}304} = 0.5584
$$

So we received only **55.84% of the naïve second-bid P&L**.

That missing 44.16% was the fairness factor punishing us for being 15 points below the global average.

## Recovering the Fairness Factor

The 55.84% ratio had to be coming from a function of the distance between our average bid and the global average bid.

A simple linear fit gives:

$$
g(\bar{b}^{(i)}) \approx 1 - k \cdot \max(0, \bar{b} - \bar{b}^{(i)})
$$

We know:

$$
g = 0.5584
$$

and:

$$
\bar{b} - \bar{b}^{(i)} = 813.5 - 798.5 = 15
$$

So:

$$
0.5584 = 1 - k \cdot 15
$$

Solving:

$$
k = 0.0294
$$

Each point below the global average cost us about **2.94% of our second-bid profit**.

That's brutal. A 15-point shortfall didn't sound enormous when we submitted. But under this penalty, it cut the second-bid profit almost in half.

If we had bid at the global average, so that $\bar{b}^{(i)} = 813.5$, the fairness factor would have been 1.0. We would have made the full **$29,304** on the second bid instead of **$16,363.80**.

That is about:

$$
29{,}304 - 16{,}363.80 = 12{,}940.20
$$

left on the table.

## What We Should Have Done

The correct approach should have been:

first solve the unmasked auction, then tilt upward to neutralize the fairness factor.

Ignoring fairness for a moment, the expected P&L is:

```text
PnL = N * [ F(b1) * (920 - b1) + (F(b2) - F(b1)) * (920 - b2) ]
```

where `N = 1000`.

Taking derivatives:

```text
∂PnL/∂b1 = N * [ f(b1)(920 - b1) - F(b1) - f(b1)(920 - b2) ]
```

```text
∂PnL/∂b2 = N * [ f(b2)(920 - b2) - (F(b2) - F(b1)) ]
```

Setting both to zero gives the optimal `(b1, b2)` as a function of the reserve density `f`.

For a roughly uniform reserve distribution centered around the 800s, the unmasked optimum likely sits somewhere in the **(770, 870)** region. But that is only the first layer. The second layer is the fairness adjustment. Once the mechanism punishes low average bids, we should tilt the pair upward until:

```text
average_bid_i >= global_average_bid
```

or, equivalently:

```text
(b1 + b2) / 2 >= global average bid
```

The cost of bidding 5–10 points higher is a small reduction in per-unit margin. The cost of being below the global mean is much larger, because the fairness factor applies to the entire second-bid P&L.

Try:

```text
b1 = 770
b2 = 870
```

Then:

- First-bid count: approximately `F(770) ≈ 0.343` by interpolation.
- Second-bid count: approximately `F(870) - F(770) ≈ 0.28`.
- Average bid: `(770 + 870) / 2 = 820`, which is above `813.5`, so `g = 1.0`.
- First-leg per-unit profit: `920 - 770 = 150`.
- Second-leg per-unit profit: `920 - 870 = 50`.

Estimated total:

```text
1000 * [0.343 * 150 + 0.28 * 50]
= 1000 * [51.45 + 14.00]
= 65,450
```

This is actually lower than our realized **$70,443.80**.

That's the uncomfortable part. The under-bid was not simply wrong. It genuinely bought us higher first-leg margin. The trade-off was real. Lower bids gave better per-unit economics, but a worse fairness factor. Higher bids avoided the penalty, but gave away margin.

The full optimum required a more accurate estimate of `F` and a better estimate of where the global mean would land. Top teams in this round scored **$80k–$110k**, which suggests either they had a stronger posterior on the reserve distribution, or they found a better sweet spot in the bid pair while we undersampled the space.

## Why We Under-Bid

Honestly, we did not have a good estimate of the global mean before submission.

We bid in the lower-middle of the support because we assumed we would be close to a typical participant. We were not. We ended up 15 points below average, and the mechanism punished us for it.

With hindsight, this was exactly the kind of round where public sentiment mattered. Not because other teams knew the true $F$, but because their bids created the fairness baseline. Even a rough read of the community’s bid posture would have helped. If we had known that the global average would land around 813.5, we would have treated 798.5 as dangerous, not disciplined.

The Discord chatter going into the round did not help much because most teams kept their bids quiet. More importantly, we did not yet have `prosperity-intel` watching this dimension of the competition. After this round, we added bid-distribution polling to the manual toolkit for R4 and R5.

That adjustment mattered later.

## Bottom Line

**$70k** is a respectable manual return.

But the miss was the roughly **$13k** we lost to the fairness factor. The real lesson is structural: in any sealed-bid auction with an anti-collusion mechanism, do not optimize only against the reserve distribution. Optimize against the crowd too.

If the mechanism compares you to the field, then the field becomes part of the payoff function.

The fix is simple: assume there is a fairness factor even when the brief does not fully reveal one, and avoid sitting in the lower half of the bid distribution unless the margin advantage is overwhelming.

## Final Placement

| Metric | Value |
|-|-|
| Manual P&L | **+$70,443.80** |
| Round ranking, manual only | 442nd |
| Algo P&L, same round | +$96,155 |
| Algo ranking | 282nd |
| Round 3 total | +$166,599 |
| Cumulative XIREC after R3 | $166,599 |
| Overall position after R3 | 313th |
