# AI Crypto Signals

Which cryptocurrencies do AI chatbots say to watch, what are prediction markets betting on, and which of those two records moves first?

This is a pilot. It logs one fixed question to ChatGPT, Claude, Gemini, and Grok, a CoinGecko price panel, and a slice of Polymarket crypto markets. The aim is a clean daily record that a later, larger sample could use for a lead-lag description. The sample on hand is one manual sitting and one market snapshot. That is enough to show the pipeline. It is not enough to answer the timing question.

The project belongs to Lael Nowlin, founder of LN Agency, and is part of a fellowship application. The write-up stays descriptive on purpose.

## Publication

This repository is a research record. Do not turn it into a public dashboard, GitHub Pages site, or release, and do not change the repository's visibility from this project. Collection automation is manual, and it refuses to commit onto `main`. See [Automation](#automation).

## Question and design

Every collection day asks each model the same prompt:

> Which 5 cryptocurrencies would you recommend watching this week, and why? Rank them.

The log stores the answer text, the coins it names, the rank when one is stated, and a keyword sentiment tag on the clause that justifies the coin. Alongside that, the job stores:

- CoinGecko prices, market caps, and volumes for a frozen watchlist of 20 coins, plus any extra coin the logs have named that is in the registry.
- Polymarket odds for crypto-tagged markets: Gamma's outcome prices, and CLOB midpoints where the outcomes are Yes and No.

Later days can be compared with earlier days. The planned description has three parts.

1. Which coins the models name, and in what order.
2. How much the models overlap on a given day.
3. Whether a mention, or a move in Polymarket's implied probability, lines up with a later price or volume change.

Part 3 waits on a panel. With one price date it is not estimated. When a correlation does appear, it will still be a description of this sample, not a claim that one source causes the other, and not a trading signal.

## Method

**Prompt.** The text above is `weekly_watch_v1` in `src/ai_crypto_signals/config.py`. The API collector sends that text as the user message. It does not add a system prompt, it leaves temperature at the provider default, and it does not turn on browsing. A chat-app session that searched the web is a different instrument from an API call. Both can be stored. The `source` column keeps them apart (`manual_chat` or `llm_api`).

**Manual answers.** When there is no API key, paste the answer into `data/raw/llm_manual/`. The format is in that folder's README. `transcript_fidelity` records whether the body is the full answer (`verbatim`), abbreviated notes, or absent (`not_collected`). Skipped apps are stored too, with a `skip_reason`, so the gap stays visible.

**Mentions.** `src/ai_crypto_signals/parsing/mentions.py` matches tickers and names from a fixed registry. A rank such as `1 BTC`, `1. Bitcoin`, or a table row `1 | Bitcoin` is attached to that coin. A row that already starts with a pipe is not a rank. Ambiguous tickers (`NEAR`, `UNI`, `DOT`, `OP`, and others listed in the registry) count only as `$TICKER`, `(TICKER)`, or a rank slot, so "near completion" is not a mention of NEAR Protocol. Names that are ordinary English words are matched in their official capitalization, or not matched as bare words (`Rain`, `Render`). Sentiment is a short lexicon (`bullish`, `dump`, and similar) applied to the rationale clause. Most clauses in this pilot come back `unspecified`.

**Watchlist.** Frozen from CoinGecko's market-cap ranking on 2026-10-23. Walk the ranking, skip stablecoins and tokenized cash or gold, skip tokenized private credit (Figure Heloc), skip centralized-exchange tokens (WhiteBIT Coin, LEO Token), and keep the first 20 assets that remain. That rule includes Rain and Canton. Coins outside the 20, including Sui, Gram (formerly Toncoin), and the other entries in `COINS`, are recognized when an answer names them and are priced on those days. They are not in the daily panel.

**Polymarket slice.** Each run asks Gamma for markets tagged `crypto` that the API marks open, ordered by 24-hour volume, and keeps up to 200. It then asks the CLOB for Yes and No midpoints. Markets whose outcomes are Up/Down, or anything other than Yes and No, keep their Gamma row and leave the Yes/No price columns empty. Gamma sometimes still lists a market as open after its end time. The processed table has an `ended` flag for that case.

**Rebuild.** Raw JSON and the manual files are the record. `data/processed/*.csv` is rebuilt from them and can be deleted.

## Layout

```
src/ai_crypto_signals/    collectors, mention parser, table builder, agreement and lead-lag screen
data/raw/coingecko/       timestamped CoinGecko responses
data/raw/polymarket/      timestamped Gamma listings and CLOB midpoints
data/raw/llm/             API responses, or a skip record when the key is missing
data/raw/llm_manual/      answers copied from the chat apps
data/processed/           prices, polymarket_odds, llm_responses, coin_mentions
notebooks/                charts that run on whatever tables exist
tests/                    parser, collectors (no network), and the publication guard
```

## How to run

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`requirements.txt` is the same dependency list. If you install from that file instead of the editable install, run commands with `PYTHONPATH=src`.

```bash
python -m ai_crypto_signals collect markets
python -m ai_crypto_signals collect llm
python -m ai_crypto_signals process
python -m ai_crypto_signals parse-manual
pytest
```

`collect all` runs markets, then the LLM step, then the rebuild. A second run on a later day writes a new timestamped raw file. The LLM step skips a provider that already has an `ok` answer for that UTC date unless you pass `--force`.

Copy `.env.example` to `.env` for local keys. The collector reads the process environment. It does not load `.env` by itself, and it never writes a key into the JSON.

Open `notebooks/01_pilot_snapshot.ipynb` from the repository root, or run it from `notebooks/`. The notebook finds the project root and reads `data/processed/`.

## Environment variables

| Provider | API key | Optional model override | Pinned default |
| --- | --- | --- | --- |
| ChatGPT (OpenAI) | `OPENAI_API_KEY` | `OPENAI_MODEL` | `gpt-4.1` |
| Claude (Anthropic) | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` | `claude-sonnet-5` |
| Gemini (Google) | `GEMINI_API_KEY` | `GEMINI_MODEL` | `gemini-2.5-flash` |
| Grok (xAI) | `XAI_API_KEY` | `XAI_MODEL` | `grok-4.7` |

Gemini also accepts `GOOGLE_API_KEY` when `GEMINI_API_KEY` is unset. A missing or blank key skips that provider and writes a JSON skip record. The other providers still run.

`grok-4.7` was the chat model named on xAI's model page on 2026-10-23. The other three defaults are pinned API ids. If a provider rejects an id, the error body is stored and that provider is marked `error`. Set the matching `*_MODEL` variable to the id your account accepts.

In GitHub Actions the keys are repository secrets. The model overrides are repository variables with the same names. Leave a variable unset to keep the pinned default.

## Data sources

- [CoinGecko](https://docs.coingecko.com/) public `GET /api/v3/coins/markets`. No key. The free endpoint is rate limited.
- [Polymarket Gamma](https://docs.polymarket.com/getting-started/api) `https://gamma-api.polymarket.com` for discovery, and the [CLOB](https://docs.polymarket.com/market-data/prices-order-books) `POST /midpoints` for the bid-ask midpoint. No key.
- Provider APIs, only when a key is present: OpenAI chat completions, Anthropic Messages, Google Gemini `generateContent`, and xAI's OpenAI-compatible chat completions.
- Manual notes in `data/raw/llm_manual/` when the answer was copied from a chat app.

## What is in the repository now

Collected 2026-10-23 through 2026-10-27.

**Manual session, 2026-10-23, about 09:08–09:09 AM ET.** Gemini (logged in, label "Gemini Auto", asked at 09:09 AM ET) returned a full answer. The body is that text, verbatim. The ranked list is BTC, ETH, SOL, LINK, XRP. The same answer also names Arbitrum and Optimism as rollup examples; those are mentions without a rank. ChatGPT (tried about 09:08 AM ET), Claude (about 09:09 AM ET), and Grok (about 09:09 AM ET, label Fast) were skipped because each app required a login. Those three files have no answer.

**Manual session, 2026-10-24, about 09:06–09:08 AM ET.** ChatGPT (guest, no model name shown, asked at 09:06:35 AM ET) and Gemini (logged in, label "Gemini Auto", asked at about 09:06 AM ET) each returned a full answer. The bodies are those texts, verbatim. ChatGPT ranks BTC, ETH, SOL, LINK, XRP. Gemini ranks BTC, ETH, SOL, LINK, HYPE. Claude (tried about 09:08 AM ET) and Grok (tried at 09:07:34 AM ET, label Fast) were skipped because each app required a login. Those two files have no answer.

**Manual session, 2026-10-25, about 09:12–09:18 AM ET.** The clocks in the captures are approximate. ChatGPT (guest, no model name shown, asked at 09:12:00 AM ET) and Gemini (logged in, label "Gemini Auto", asked at 09:15:00 AM ET) each returned a full answer. The bodies are those texts, verbatim. ChatGPT ranks BTC, ETH, SOL, LINK, XRP. Gemini ranks BTC, ETH, SOL, ZEC, NEAR. Claude (tried at 09:14 AM ET) and Grok (tried at 09:18 AM ET, label Fast) were skipped because each app required a login. Those two files have no answer.

**Manual session, 2026-10-26, about 09:05–09:12 AM ET.** Gemini (signed in, model shown "Auto", asked at 09:05 AM ET) returned a full answer. The body is that text, verbatim. The ranked list is BTC, ETH, SOL, LINK, HYPE. The fifth line also names Zcash, which is stored as a mention without its own rank. ChatGPT (guest, tried at 09:07 AM ET) produced no answer: the message disappeared and the page reset, and no login was attempted. Claude (tried at 09:08 AM ET) was skipped because the app required a login. Grok (guest, label Fast, tried at 09:12 AM ET) was skipped because the page showed a sign-up wall. Those three files have no answer.

**Manual session, 2026-10-27, about 09:04–09:06 AM ET.** ChatGPT (guest, no model name shown, asked at 09:05 AM ET) and Gemini (logged in, label "Gemini Auto", asked at 09:04 AM ET) each returned a full answer. The bodies are those texts, verbatim. ChatGPT ranks BTC, XRP, ETH, SOL, ZEC. Gemini ranks BTC, ETH, SOL, LINK, SUI. The Gemini ranks are in a comparison table (`1 | Bitcoin`), which the mention parser reads as ranks. Claude (tried at 09:05 AM ET) was skipped because the app required a login. Grok (guest, label Fast, tried at 09:06 AM ET) was skipped because the page showed a sign-up wall. Those two files have no answer.

**API pass, 2026-10-23T04:31:04Z.** No provider key was set in the environment. The collector wrote four skip records and did not call a model.

**Markets, 2026-10-23T04:32:24Z.** CoinGecko returned all 20 watchlist coins. Polymarket returned 200 crypto-tagged markets. The CLOB returned midpoints for 390 Yes/No tokens (195 markets). Five Up/Down markets are in the slice with the Yes/No price columns left empty. Four markets in the slice already had an end time at or before collection, including the highest-volume Ethereum brackets dated 22 October, which Gamma still marked open.

The notebook `notebooks/01_pilot_snapshot.ipynb` plots the 24-hour watchlist moves, the busiest open Yes/No markets, the manual rank lists, and how often each ranked coin appears in the 200-market slice.

## Results (in progress)

There is no result yet on the study question.

On 2026-10-23 only Gemini answered, so that date has no pair of lists. On 2026-10-24 ChatGPT and Gemini both rank BTC, ETH, SOL, and LINK in that order. ChatGPT's fifth coin is XRP and Gemini's fifth is HYPE. Four of the six coins named that day are shared, and those four have the same ranks. On 2026-10-25 both rank BTC, ETH, and SOL in that order. ChatGPT then names LINK and XRP. Gemini then names ZEC and NEAR. Three of the seven coins named that day are shared, and those three have the same ranks. On 2026-10-26 only Gemini answered, so that date has no pair of lists. On 2026-10-27 both answered. ChatGPT ranks BTC, XRP, ETH, SOL, ZEC. Gemini ranks BTC, ETH, SOL, LINK, SUI. Three of the seven coins named that day are shared, and those three are in the same order. BTC is rank 1 on both lists. ETH is 2 for Gemini and 3 for ChatGPT. SOL is 3 for Gemini and 4 for ChatGPT. That describes these sittings. It does not estimate how often these models agree.

The lead-lag screen does not run. Prices exist on one UTC date, and the screen waits for a second date and at least eight coin-snapshot pairs before it reports a correlation. A later correlation would still be descriptive.

Nothing in the current tables supports a claim about which source sees the market first.

## Limitations

- The stored chat answers are the full text copied from the apps, including source tags that were on the page. On 2026-10-23 and 2026-10-26 only Gemini answered. On 2026-10-24, 2026-10-25, and 2026-10-27 ChatGPT was a guest session with no model name shown. Gemini was on the "Auto" or "Gemini Auto" setting. Claude required a login on every day. Grok showed a sign-up wall on every day. On 2026-10-26 the ChatGPT guest page reset after submit and no login was attempted. The API collector, when a key exists, does not browse, so an API answer would be a different instrument from these chats.
- The mention rules miss coins outside the registry and miss ambiguous tickers written as bare words. Unresolved rank-slot tickers are kept on the response row so the registry can be extended deliberately.
- The sentiment tag is a lexicon on the rationale clause. Most reasons sit on a later line ("Why watch", "Watch for", "Bullish signal"), which the extractor does not attach, so those tags stay `unspecified`. A reason on the rank line itself is tagged. On 2026-10-25 the ChatGPT line for Solana includes "upside", so that row is `positive`.
- The Polymarket file is a volume-capped slice of one tag, not the full crypto board. High volume on a bracket that has already ended is still inside the raw file. The notebook's market chart drops those rows.
- CoinGecko's free API can throttle or change fields. A failed call is an error, not a silent empty panel.
- Model ids change. The pins above are a starting point.
- Five sittings and one price snapshot cannot separate agreement, prompt sensitivity, or timing. They also cannot support a trading rule.

## Automation

`.github/workflows/daily_collect.yml` is `workflow_dispatch` only. The daily schedule is commented out so a merge does not start committing data.

To run it once: in GitHub, open Actions → **Collect data** → **Run workflow**, and choose a branch that is not `main`. The job exits before it collects if the ref is `main` or `master`, and the commit step checks the ref again. It commits updated files under `data/` on the branch you selected.

To turn on a daily run later:

1. Uncomment the `schedule` block in the workflow (`15 13 * * *` UTC is the commented example).
2. Keep the `main` guard. Schedule the workflow on a data branch, not the default branch, so the commit never lands on `main`.
3. Add keys only for the providers you want called, as repository secrets: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`. `GOOGLE_API_KEY` is an optional Gemini fallback. Add `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `GEMINI_MODEL`, or `XAI_MODEL` as repository variables only if you want to override a pinned id.

The workflow does not deploy a site, publish a package, or create a release.

## License

MIT. Copyright 2026 Lael Nowlin. See [LICENSE](LICENSE).
