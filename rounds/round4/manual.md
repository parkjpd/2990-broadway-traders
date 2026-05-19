# Round 4 — Manual: Aether Crystal options (+$63,019, rank 256)

R4 came down to a single trade — the chooser arb. The rest of the portfolio was a mix of solid hedges and one position I wish we hadn't taken (the KO put). The net is fine, but it could have been a lot cleaner.

Two questions worth asking on this round: what actually carried it, and what dragged it down? And why is the chooser arb in particular the strongest single trade we placed all competition?

## What you got

A spot underlying (Aether Crystal, "AC") at mid 50.00 with a 0.05 bid-ask, plus 11 options. Vanilla puts and calls at five strikes (35, 40, 45, 50, 60), two short-dated ATMs (T+14 versus the rest at T+21), and three exotics: a chooser at K=50, a binary put at K=40 paying 10 if $S_T < 40$, and a down-and-out put with K=45 and barrier 35. Each contract had a 3,000-share multiplier and a max volume per side.

You submitted a single one-shot order ticket. PnL was averaged across **100 GBM simulation paths** under a published spot dynamic. Submission was do-it-once-and-walk-away.

## Spot the arb first, then everything else

Three exotics in the chain, and one of them — the chooser — had a textbook static-replication identity. We went after it first because static arbitrage is the highest-EV trade in any options market, and you don't need to trust any pricing model to put it on.

### The chooser identity

A chooser at strike $K$, total expiry $T$, choose date $t < T$: at $t$, the holder declares it a put or a call (whichever they want), and from $t$ to $T$ it is that vanilla. At $r = 0$:

$$
\text{Chooser}(K, T, t) = \text{Call}(K, T) + \text{Put}(K, t)
$$

The proof sketch goes through put-call parity at the choose date. At time $t$ the holder gets $\max(C, P)$. Parity says $P = C + K e^{-r(T-t)} - S_t$, which at $r = 0$ collapses to $P = C + K - S_t$. So:

$$
\max(C, P) = C + \max(0, K - S_t) = C + (K - S_t)^+
$$

The first term is "what a call worth $T-t$ years to expiry pays at time $t$," which is exactly what a long-call(T) is worth at time $t$. The second term is "the payoff of a put expiring at $t$ with strike $K$." Therefore the chooser at $t = 0$ replicates as a long Call(K, T) plus a long Put(K, t).

In words: hold a long T+21 call AND a long T+14 put. At T+14, one of two things happens. If the chooser becomes a call (because $S_{T+14} \geq K$), our long call matches it and the put expires worthless. If it becomes a put (because $S_{T+14} < K$), the put we hold expires in-the-money and the cash pays for swapping our remaining call for a put via parity. Net: zero residual at risk-neutral expectation, and the simulator's 100-path averaging crushes whatever path noise is left.

### The mispricing

The IMC chain quoted these mids:

| Symbol | Type | Strike | TTE | Bid | Ask | Size |
|-|-|-|-|-|-|-|
| AC_50_CO | Chooser | 50 | T+14 / T+21 | **22.20** | **22.30** | 50 |
| AC_50_C | Call | 50 | T+21 | 12.00 | 12.05 | 50 |
| AC_50_P_2 | Put | 50 | T+14 | 9.70 | 9.75 | 50 |

The replicating portfolio bought at ask:

$$
12.05 + 9.75 = 21.80
$$

The chooser sold at bid was 22.20, which gives **40 cents of arbitrage per contract**. At 50 contracts with a 3,000 multiplier:

$$
0.40 \cdot 3{,}000 \cdot 50 = \$60{,}000
$$

Pure structural edge. Zero pricing model. We placed all three legs first.

### Why the mod let it through

The best guess is that the chooser was priced via a generic Monte Carlo on the spot dynamics, which gave the correct expected payoff but the bid-ask was set off the model price without accounting for the static-replication arb. The 40-cent gap was the spread between (model fair × 0.985) on the bid and (model fair × 1.015) on the ask, which happened to straddle the static rep on the wrong side.

Either way, free $60k.

## Binary put — also overpriced, plus a hedge

The binary put paid 10 if $S_T < 40$ else 0. Fair value under BSM is $10 \cdot \mathcal{N}(-d_2)$ at $K=40$. Plugging in $\sigma\sqrt{T}$:

$\sigma = 2.51$ annualized (from a leaked mod statement on Discord; see "Simulator parameters" below). $T = 15$ trading days = $15/252$ years. So $\sigma \sqrt{T} = 2.51 \cdot \sqrt{0.0595} = 0.6124$.

$$
d_2 = \frac{\ln(50/40) - \frac{1}{2}(0.6124)^2}{0.6124} = \frac{0.22314 - 0.18750}{0.6124} = 0.05819
$$

$\mathcal{N}(-0.05819) = 0.47681$, so **BP fair = $4.77$**.

Market bid was 5.00, giving a sell-edge of $+0.23$ per option.

We shorted 50 BP and hedged with a 35-45 put spread: long AC_45_P, short AC_35_P. The spread payoff:

- $S_T \geq 45$: 0
- $40 < S_T < 45$: $45 - S_T \in [0, 5]$
- $35 < S_T < 40$: $45 - S_T \in [5, 10]$
- $S_T < 35$: 10

Combined with the short BP, our net at expiry is bounded between **−$5 and +$5 per option**, which is much tighter than the naked BP's −$10 worst case in the $35 < S_T < 40$ zone.

Entry credit: $5.00 - 9.10 + 4.33 = +0.230$. Expected EV (BP fair = 4.77): $+0.217$ per option × 50 × 3000 ≈ $32k.

## KO put — fair on paper, lost in practice

This is the leg we'd skip if we got to replay R4.

The KO put (K=45, B=35, T+21) is path-dependent. Reiner-Rubinstein gives the continuous-monitoring fair value. However, the simulator monitors the barrier only at **discrete ticks** (4 per trading day, 60 total). Continuous monitoring undercounts: it credits more knockouts than the discrete grid actually allows. The Broadie-Glasserman-Kou correction lifts the effective barrier:

$$
B_\text{eff} = B \cdot e^{-\beta \sigma \sqrt{\Delta t}}, \quad \beta = 0.5826
$$

With $\Delta t = 1/4$ trading day and $\sigma = 2.51 / \sqrt{252} = 0.1582$/day, we get $\beta \sigma \sqrt{\Delta t} = 0.5826 \cdot 0.1582 \cdot 0.5 = 0.0461$. So $B_\text{eff} = 35 e^{-0.0461} = 33.43$.

Running R-R with $B_\text{eff} = 33.43$ at the K=45 smile vol gives a fair value of roughly $\$0.21$. The market mid was 0.1625, with bid 0.150 / ask 0.175. The buy-edge at the ask was 4–5 cents, which was tempting on 500 contracts (the chain's biggest size): $0.04 \cdot 500 \cdot 3000 = \$60{,}000$ if it held.

It did not hold. We lost $29k on this leg. The discrete-monitoring correction was an analytic, not a simulation; we should have MC'd the KO directly under the simulator's published path dynamics and compared to the model. We did not have time. Lesson logged.

## Simulator parameters (all from Discord, none from the brief)

The brief gave the option chain prices and the chooser conversion rule. It did not give the spot's SDE parameters, the discrete vs. continuous monitoring rule, or the path-averaging mechanic. We got those from the IMC Discord:

- **GBM with $r = q = 0$**, annualized $\sigma = 2.51$ (251%), confirmed by mod Tomas alongside a community-discovered wiki excerpt (`prosperity-intel` 04-27 01:20, aaron00720147 quoting the wiki).
- **4 ticks per trading day**, 252 trading days per year.
- "T+21" maps to **3 trading weeks = 15 trading days = 60 ticks** (not 21 trading days). Same for T+14 → 10 days = 40 ticks.
- KO barrier monitored only at the 60 discrete ticks (aaron00720147 same quote).
- Final PnL = mean across 100 independent paths, confirmed by mod Tomas (04-26 20:11).

The 100-sim averaging is what makes structural arb the right play. Path noise divides by $\sqrt{100} = 10$, so realized PnL converges to expected. That is why the chooser arb captures its full $60k EV reliably and not "$60k EV but with $1.5M of SD."

## The submission

| Order | Side | Symbol | Volume | Price | What it does |
|-|-|-|-|-|-|
| 1 | **SELL** | AC_50_CO | 50 | 22.20 | Chooser arb (sell expensive exotic) |
| 2 | **BUY** | AC_50_C | 50 | 12.05 | Chooser arb (long T+21 call) |
| 3 | **BUY** | AC_50_P_2 | 50 | 9.75 | Chooser arb (long T+14 put) |
| 4 | **BUY** | AC_50_C_2 | 50 | 9.75 | Vol diversifier (long T+14 call) |
| 5 | **SELL** | AC_40_BP | 50 | 5.00 | Binary put short |
| 6 | **BUY** | AC_45_P | 50 | 9.10 | BP hedge (long wing) |
| 7 | **SELL** | AC_35_P | 50 | 4.33 | BP hedge (short wing) |
| 8 | **SELL** | AC_60_C | 50 | 8.80 | OTM call short |
| 9 | **BUY** | AC_45_KO | 500 | 0.175 | KO long (lost, see above) |

Expected total per the model: $60k (chooser arb, locked) + $32k (BP hedged) + $46k (KO long, did not work out) + $5k (small misc), around $140k. Realized was $63k. The gap is almost entirely the KO leg.

## Realized P&L

| Symbol | Side | Vol | Price | **P&L** |
|-|-|-|-|-|
| AC_50_C | BUY | 50 | +628.31 | **+$31,415.57** |
| AC_35_P | SELL | 50 | −244.87 | **−$12,243.40** |
| AC_45_P | BUY | 50 | +405.61 | **+$20,280.48** |
| AC_60_C | SELL | 50 | +414.80 | **+$20,739.82** |
| AC_50_P_2 | BUY | 50 | −282.40 | **−$14,119.75** |
| AC_50_C_2 | BUY | 50 | −468.84 | **−$23,442.21** |
| AC_50_CO | SELL | 50 | +1,087.08 | **+$54,354.22** |
| AC_40_BP | SELL | 50 | +300.00 | **+$15,000.00** |
| AC_45_KO | BUY | 500 | −57.93 | **−$28,966.10** |
| | | | **TOTAL** | **+$63,018.63** |

### Per-leg audit

**Chooser arb (legs 1-3 combined): +$54,354 + $31,416 − $14,120 = +$71,650.**

That is $11.6k above the structural arb's $60k. The chooser-arb math says "lock in $60k of structural edge"; however, the path-noise residual term ($S_{T+21} - S_{T+14}$ when chooser converts to a put) had a positive realization on this particular average path. We would happily have taken $60k flat. The +$11.6k bonus was a free roll.

**BP hedged short (legs 5-7): +$15,000 − $12,243 + $20,280 = +$23,037.**

Model expected ~$32k. Realized $S_T$ landed in the (35, 40) range, which is where the hedge has its worst case; we keep the BP premium but the spread pays less than it would at $S_T \leq 35$. Still a clean $23k.

**OTM call short (leg 8): +$20,740.** $S_T$ ended below 60, so the short call expired worthless and we kept the premium. We had classified this as "too thin to act on" pre-trade (theoretical edge 0.008 per option); however, with the 100-sim averaging it locked in cleanly. Lesson: at the consensus mid for OTM strikes, even 1-cent edges are real.

**Vol diversifier (leg 4, long T+14 call): −$23,442.** This was the worst single leg. The thinking was that the long T+14 put we held (leg 3, part of the chooser arb) had asymmetric gamma exposure, so adding the matching call would hedge that. In practice the call landed slightly ITM but not enough to recover the $9.75 premium. Net loss $23k. In hindsight, this was an unnecessary trade; the chooser arb's hedge structure handles gamma intrinsically once the put expires at T+14.

**KO long (leg 9): −$28,966.** Discussed above. The discrete-monitoring correction underestimated barrier hits on the actual 60-tick paths. Of the 500 contracts, most knocked out and we lost the $0.175 premium; survivors paid roughly $0.117 net. We lost ~$0.058 per option on average × 500 × 3000 = −$28,966.

## Net P&L: +$63,018.63

Three legs we would repeat as-is (chooser arb, BP hedged short, OTM call short, roughly $115k combined). Two legs to drop or change (T+14 call diversifier, KO put long, roughly $52k loss combined). If we had shipped just the three winners and skipped the two losers, the total would have been roughly $115k, not $63k.

## What we would repeat

The chooser arb. It is the cleanest trade we placed in any round of the competition. Structural, model-independent, captured at expected value due to the 100-sim averaging. We arrived at the Rubinstein decomposition two ways at once: the hand-priced chain (Black-Scholes on each strike, then notice the chooser quote equals $C + P$ to the cent) and the parity derivation from the chooser conversion rule. Both pointed at the same trade, and the duplicate path gave us the confidence to size it at max volume.

The BP hedge structure. Even in the worst-zone realization, the hedge bounded the loss. A naked BP at $S_T \in (35, 40)$ would have lost the full $-10 \cdot 50 \cdot 3{,}000 = -\$1{,}500{,}000$. The 35-45 put spread saved that.

## What we would cut

The T+14 call diversifier (AC_50_C_2 long). Not necessary once the chooser arb is in place. The gamma profile is already handled by the chooser hedge. Should have been zero, was instead a $23k loss.

The KO put long. Tempting but mathematically unverifiable in the time we had. Continuous-monitoring analytics on a discrete-monitoring simulator are a model mismatch that compounds with path realizations. Should have been zero, was instead a $29k loss.

## Lessons that carried into R5

Four things from this round carried directly into R5, and the R5 outcome (rank 28, +$123k) is partly a function of how seriously we took them.

First, static replication is the highest-EV trade type when it exists. It beats every directional or model-based bet, because it is model-free.

Second, discrete-monitoring corrections are tricky. Even with a published analytic (Broadie-Glasserman-Kou) and the simulator's exact dynamics, the empirical knockout rate can diverge from the analytic. MC against the actual simulator before pricing path-dependent options, not against a continuous-time approximation.

Third, the 100-sim averaging changes optimal strategy. Variance divided by 10 means realized PnL is close to EV. This favors structural arb (Sharpe ratios that look terrible on a single path become great on the average) and disfavors directional bets (where the upside tail averages away).

Fourth, Discord intel is the alpha source. The simulator parameters that locked the math (σ=251%, 4 ticks/day, discrete barrier, 100-sim avg) came entirely from the IMC Discord scrape. The brief did not publish them.

(Tooling for the round was basically `scipy.stats.norm` plus a 200k-path custom MC for the KO; nothing more interesting than that.)

## Looking back

The gap between the chooser arb and the KO put is what I keep coming back to. They were the same shape of trade on paper (find an edge in a published price, size it up, capture the EV), but one of them was structural and the other one was a model. The structural one delivered $60k of EV at low variance, exactly as advertised. The model one delivered a $29k loss, because the model's assumptions did not match the simulator's discretization. And although we would not have left the KO put on the table again with the benefit of hindsight, the lesson it taught us is what allowed R5 to land at rank 28: trust structural identities, mistrust model approximations, and never assume the simulator behaves like the textbook.

Final manual P&L: +$63,019, ranking 256th. Algo same round: +$164,004 at 168th. Round 4 total: +$227,023, putting us at #154 overall after this round.
