# Lessons

Two big takeaways from IMC Prosperity 4. The first is about where alpha actually came from. The second is about how easily we lost it back.

## Math sets the ceiling, humans fill in the priors

The closed-form solutions we leaned on — the Rubinstein chooser identity, the portfolio optimum $\pi^* = (2p-1)\cdot R \cdot 50$ — are the easy part of these rounds. They fall out of one derivative or one parity argument. The hard part is the inputs: the $R$, the $p$, the confidence levels you feed the formula. Those don't come from another sheet of paper. They come from reading how other top players are talking about a product on Discord at 2 AM.

The Obsidian flip in R5 manual is the clearest example. The math itself was unambiguous: at any P(BUY correct) > 0.46, the flip from SELL to BUY is +EV. But P(BUY correct) is a *human* number, not a derived one. We didn't compute it from first principles. We counted: 9 named Discord players said BUY, 4 said SELL. We weighted each by how confident the post sounded (Suahs's *"its a supply shock, the factory broke down"* gets more weight than ChummyBigfoot86's two-word *"is a sell"*). Final tally was 9/13 = 0.69, well above the 0.46 threshold. We flipped. Realized direction came in correct (+$2,366 P&L).

Pyroflex was the same kind of catch. The article said "tax doubles tomorrow," which on first read sounds like a fresh shock. The reason we knew it wasn't came from re-reading the article as a person, not as an LLM extracting facts: "following its decision," "recent months of public criticism," "effective tomorrow." Three phrases that together mean "this is already in the price." No equation flagged that — a human noticed it. And we only knew to look that hard because Mosho's `BEFORE: ... -5%` → `AFTER: ... -9%` edit in the `deletions` table told us he had been wrestling with the same question.

The Discord scraper was not just a research tool. It was a way to pull priors out of the only source that could supply them, which was other humans who knew something we didn't and were communicating it in real time. Sometimes they even let it slip in the form of an edited post or a 30-second-old deletion.

If we had to compress the entire competition into one line: **math sets the ceiling, humans fill in the priors.**

## Overfitting beats clever modelling

Almost all of our self-inflicted losses across the competition came from the same mistake. We picked the version that scored highest on the 3-day backtest IMC released, instead of the version that traded the strongest signal. The same mistake showed up in three different rounds.

The R5 algo was the cleanest example. R5 algo finished at +$2,752 against an algo backtest north of $1.6M — a 600× gap. That is the signature of an overfit. We had around 50 candidate parameter configurations from sweeps, most of them clustered in the $800k–$1.1M backtest range, and we shipped one near the top of that distribution. Pair-trading 50 new products with only 3 days of data is a textbook overfitting setup, and we did the textbook thing. A smaller, dumber strategy — raw pair mean reversion on the 4–5 most stable spreads, ignoring the marginal pairs — would have shown lower backtest PnL and higher live PnL.

The R4 KO put long was the same mistake in different clothing. We bought 500 KO put contracts using a Broadie-Glasserman-Kou discrete-monitoring analytic. The model was clever, and that was part of the problem. It fit the simulator's continuous-time SDE, but we hadn't validated it against the simulator's *actual* realized paths. The analytic looked strong, the empirical knockout rate diverged, and the position lost $29k.

R3's options sub-strategy was the same shape. Several iterations (notably `v22–v28`) chased per-strike option-sizing tweaks that improved the backtest by $5k–$15k but added little structural edge. Most of those gains were noise; the final 10k champion, `v32`, ended up not depending on the most fragile versions of those tweaks. The issue was never that sweeping was bad. The issue was that we let the sweep start deciding what the strategy *was*.

The underlying confusion is between "scored well in the sweep" and "captures real edge." They are not the same thing. Sweeping is useful when you already know the signal and want to size it. It becomes dangerous the moment you use it to choose between strategies, because the strategy with the most fitting flexibility will win the sweep regardless of out-of-sample performance.

The rounds where we got it right (R4 chooser arb, R5 manual) had one thing in common: the signal was small enough to fit in one sentence. "Chooser equals call plus put under r=0." "If both directions are negative-EV under uncertainty, do nothing." The math behind each is two or three lines of derivation.

The lesson, on both algo and manual sides, is the same. **Trust the signal you can explain in one sentence. The math that requires three caveats is the math that overfits.**
