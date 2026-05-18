# prosperity-intel — Discord scrape + LLM extraction pipeline

[`parkjpd/prosperity-intel`](https://github.com/parkjpd/prosperity-intel) is a 24/7 Discord selfbot that scraped the official IMC Prosperity Discord into a SQLite DB on a VPS, an hourly LLM extractor that turned prose into structured insights, and a digest pipeline that fed those insights back into the strategy team every morning.

By the end of R5 the database had **131,201 messages**, **4,937 LLM-extracted insights**, **5,829 deletion events**, plus per-message attachments, replies, threads, and edit history. So the question worth asking up front: was a 24/7 selfbot worth the operational headache of running it for three weeks? Moreover, why should the deletion table be considered the highest-signal piece of the whole pipeline?

## Why we built it

Manual rounds in IMC are anchored on **other teams' consensus** far more than they are anchored on first-principles fundamentals. We learned this the hard way in R3, where we under-bid the global mean and lost roughly $13k to the fairness factor; and we learned it again in R4, where the chooser arb math only worked because we knew the simulator's σ, which had only been confirmed in a single mod response buried in `#announcements`. By the time R5 rolled around, the need was obvious: if the alpha lives in the Discord, we should be reading the Discord at scale.

The `prosperity-intel` pipeline was designed to give us live access to that consensus. What were high-sophistication users converging on? What was being deleted (often the highest-signal alpha, because people delete the things they regret sharing)? What were mods saying off-the-record that contradicted the official brief?

And the single biggest payoff was the R5 manual. Three independent top-tier players converged on the P3R5 → P4R5 product mapping the night before submission, and `prosperity-intel` surfaced the convergence in time for us to flip our Obsidian Cutlery position from SELL to BUY. That flip alone made +$2,366 and saved us roughly $4k on the swing from the original SELL position. See [`../rounds/round5/manual.md`](../rounds/round5/manual.md) for the trade-by-trade narrative.

## What's in it

```
prosperity-intel/
├── bot.py                ← Discord selfbot (scrapes channels, mirrors deletions)
├── db.py                 ← SQLite schema + write helpers
├── search.py             ← full-text search across messages + insights
├── llm_extractor.py      ← per-message LLM call → structured insight rows
├── llm_runner.py         ← hourly extraction pass orchestrator
├── llm_client.py         ← anthropic SDK wrapper with retry/backoff
├── pipeline.py           ← end-to-end runner (scrape → extract → digest)
├── digest.py             ← daily summary email/Slack notification
├── autoposter.py         ← cross-channel forwarding (high-importance → priority)
├── notifications.py      ← push/desktop alerts on threshold crossings
├── attachments.py        ← screenshot + image attachment downloader
├── forwarder.py          ← /priority and /alerts channels (deduped)
├── backfill.py           ← historical message backfill
├── intelligence/
│   ├── antisignal.py     ← detect "this is wrong" / suspicious phrases
│   ├── deletion_tracker.py  ← surface deleted-within-5-min messages
│   ├── brief.py          ← LLM-driven action-brief synthesis
│   ├── consensus.py      ← detect cross-author convergence on a topic
│   ├── modbehavior.py    ← mod silence / burst / hint detection
│   ├── profiler.py       ← per-author sophistication scoring
│   ├── questions.py      ← cluster unanswered questions (alpha proxies)
│   ├── round_analysis.py ← round-vs-round structural comparison
│   ├── sentiment.py      ← keyword-based positive/negative tone
│   ├── smartmoney.py     ← high-conviction author tracking
│   ├── strategy_extractor.py  ← extract instruments + params from text
│   └── timing.py         ← event detection (round_start, mod_burst, deadline)
├── priors/
│   └── prosperity_history.md  ← P1-P3 patterns loaded into LLM prompts
├── dashboard.py          ← live monitoring dashboard (~87KB)
├── CLAUDE.md             ← system instructions for any LLM querying the DB
└── FOR_GRAPHIMC.md       ← integration guide for the graphIMC team (27KB)
```

## The data model — 8 tables

There are eight tables in total, but four of them carried almost all the load for the strategy team.

### `messages` — the raw firehose (131K+ rows)

```sql
CREATE TABLE messages (
  message_id        TEXT UNIQUE,        -- Discord snowflake
  author            TEXT,
  author_id         TEXT,               -- stable; use this for joins
  channel           TEXT,               -- algo-trading, manual-trading, general,
                                        -- announcements, bugs, find-teammates,
                                        -- open-source, programming
  channel_id        TEXT,
  content           TEXT,
  timestamp         TEXT,               -- UTC ISO8601 +00:00
  is_mod            BOOLEAN,            -- official IMC mod
  is_bot            BOOLEAN,
  has_attachment    BOOLEAN,
  attachment_urls   TEXT,
  reply_to_id       TEXT,
  thread_id         TEXT,
  importance_score  INTEGER,
  is_deleted        BOOLEAN,            -- mirrored to deletions
  original_content  TEXT                -- pre-edit version
);
```

### `llm_insights` — structured extractions (4,937 rows)

Each row is the output of an LLM pass over a single message, with six fields that enabled the highest-value queries:

```sql
(insight_type, topic, instruments, parameters, confidence, sophistication_weight)
```

These six fields are what made cross-author consensus detection possible. For example:

```sql
-- "What params are top-50 sophistication users using on VEV?"
SELECT * FROM llm_insights
WHERE 'VEV_5000' = ANY(instruments)
  AND sophistication_weight >= 0.8
ORDER BY confidence DESC;

-- "Where are the deletions clustered?"
SELECT topic, COUNT(*) as n
FROM llm_insights
WHERE message_id IN (SELECT message_id FROM deletions)
GROUP BY topic ORDER BY n DESC;
```

### `deletions` — what got deleted (5,829 rows)

This is the single highest-signal table in the whole database. People delete what they regret sharing, and what they regret sharing is almost always alpha. The selfbot mirrored every deletion event with the original content preserved, so even when a user deleted a post three seconds after sending it, we still had the original in our table.

The sweet spot was deletions within the first 5 minutes of posting; that is the "I shouldn't have said that" window. Deletions after one or more hours were mostly typo cleanups and noise. We learned to filter aggressively on the timestamp delta.

Mosho's R5 portfolio iteration is the textbook example of why this table mattered. He posted a portfolio draft, then edited it five times in the next ten minutes, and each edit's "before" version was preserved in the deletions table. We could watch him work through the P3R5 mapping in real time, and the final version of his portfolio (before he deleted it altogether) was essentially the same as ours.

### `mod_messages` — ground truth, mostly (rows in `messages` with `is_mod=1`)

Mods do not answer questions about optimal parameters, but they do answer infrastructure questions and they do so with a precision that nobody else does. Filtering `messages` for `is_mod=1` and `channel='announcements'` gave us, among other things:

- The "1k vs 10k horizon" confirmation (Jasper, R3).
- The "options are fair-value-liquidated, not exercised" clarification (Tomas, R3).
- The "no counterparties this round" confirmation (R5).

Each of those answers shaped major strategy decisions, and each of them was buried in a thread where it would have been impossible to find without an indexed search.

## The LLM extraction pass

`llm_runner.py` runs hourly. For every new message it does three things in sequence:

1. Calls the LLM (DeepSeek-V3.2, switched from Claude for cost reasons after the first week) with a prompt template instructing it to extract structured insights from prose.
2. Parses the JSON response into `(insight_type, topic, instruments, parameters, confidence, sophistication_weight)` rows.
3. Stores them in `llm_insights`.

The sophistication_weight field comes from `intelligence/profiler.py`, which scores authors based on use of precise quantitative language ("Sharpe 1.7" outranks "good Sharpe"), reference to specific bot trader IDs or market microstructure detail, density of code snippets or formulas, and historical hit rate on prior insights (forward-validated against actual round outcomes).

## The digest

`digest.py` produces a daily email and Slack post summarizing five categories:

- Top-10 highest-importance messages of the last 24h.
- Cross-author consensus clusters, where three or more high-sophistication authors agreed on a claim.
- Notable deletions: deleted within 5 minutes by an author with sophistication_weight ≥ 0.7.
- Mod activity bursts.
- Open questions with no mod response and three or more askers.

This was the **default morning brief** for the strategy team during the competition, and we leaned on it more days than I want to admit.

## How graphIMC consumed it

Three patterns ended up dominating.

**(a) One-shot SQL** for quick lookups during a strategy iteration:

```bash
ssh root@VPS \
  "sqlite3 /root/prosperity-intel/prosperity.db \
     'SELECT content FROM messages WHERE content LIKE \"%VEV_5100%\" LIMIT 10'"
```

**(b) Pull a CSV slice** when joining against backtest data:

```bash
ssh root@VPS "sqlite3 -csv prosperity.db \
   'SELECT * FROM llm_insights WHERE topic = \"market_making\"'" > /tmp/mm.csv
```

**(c) SSHFS mount** for overnight loops where graphIMC re-queried continuously:

```bash
sshfs root@VPS:/root/prosperity-intel /tmp/intel
sqlite3 "file:/tmp/intel/prosperity.db?mode=ro" "..."
```

The full integration guide is in [`prosperity-intel/FOR_GRAPHIMC.md`](https://github.com/parkjpd/prosperity-intel/blob/main/FOR_GRAPHIMC.md), which is 27KB of how-to and is by far the longest doc in the repo.

## What we would do differently

Looking back on the operational side of this, four things stand out.

First, we should have started scraping earlier. We started the selfbot on Apr 12, which was 2 days before R1 opened. Earlier would have given us tutorial-round intel and built a stronger author-sophistication baseline; even one extra week of historical data would have meaningfully changed how we weighted certain authors going into R3.

Second, multi-account redundancy. A single Discord account scraping for three or more weeks risks rate limits and bans (we hit neither, but the risk was real). Two or three accounts with overlapping coverage would have been safer.

Third, live deletion alerts. The deletion tracker was useful in retrospect, but we didn't have real-time alerts firing. A Slack push the moment a `soph_weight ≥ 0.8` author deleted within 5 minutes of posting would have caught some intel we surfaced too late to use. The infrastructure was there; we just never wired it up.

Fourth, cross-edition memory. The `priors/prosperity_history.md` file was hand-curated by me, which means it was incomplete; auto-loading prior P3 winners' writeups as RAG context would have made the LLM extractor sharper from day one. This is the single thing I would change first if running this again.

If we had to keep one tool from the entire competition for next year, this is it. The visualizer is a close second, but the visualizer multiplies the iteration speed of an idea we already have; the Discord scraper is what gives us the ideas in the first place. Build it on day one. Do not wait.
