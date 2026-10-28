# Manual chat logs

Use this folder when an answer comes from a chat app instead of the API.
One file per answer. The parser reads Markdown with YAML front matter, and
JSON objects with the same fields.

Files in `examples/`, `README.md`, and names starting with `_` are ignored.

## Markdown

```markdown
---
provider: chatgpt
provider_label: ChatGPT
model: ""
status: ok
collected_at: "2026-10-23T04:16:43Z"
time_precision: timestamp
source: manual_chat
prompt_id: weekly_watch_return_v2
transcript_fidelity: abbreviated_session_notes
session_note: "Logged out. The app used web citations."
---

Watch list
Ranked: 1 BTC, 2 ETH, 3 SOL, 4 XRP, 5 LINK
Reasons: BTC = market benchmark; ETH = testnet this week

7-day return rank
Ranked: 1 SOL, 2 BTC, 3 ETH, 4 LINK, 5 XRP
Reasons: SOL = highest expected return over the next 7 days
```

`provider` accepts `chatgpt`, `openai`, `claude`, `anthropic`, `gemini`,
`google`, `grok`, or `xai`. `collected_at` is ISO-8601 and needs a timezone.
`status` is `ok`, `skipped`, or `error`. A skipped file needs `skip_reason`
and produces no coin mentions.

`prompt_id` is `weekly_watch_v1` for answers collected 2026-10-23 through
2026-10-27, and `weekly_watch_return_v2` from 2026-10-28. Files already in
this folder for 2026-10-28 were asked the v1 prompt and keep that id. A
missing `prompt_id` falls back to the current id in `config.py`. For a v2
answer, label the two lists `Watch list` and `7-day return rank` so the
mention table can keep their ranks apart (`list_type` `watch` or
`return_7d`).

`transcript_fidelity` records what the body actually is. `verbatim` is the
full answer text. `abbreviated_session_notes` is ranks and reasons written
down, not a full transcript. `not_collected` is a skip with no answer.

## JSON

```json
{
  "provider": "gemini",
  "collected_at": "2026-10-23T04:17:24Z",
  "status": "ok",
  "text": "1. Bitcoin (BTC) — benchmark\n2. Ethereum (ETH) — fees"
}
```

Check a file with:

```bash
python -m ai_crypto_signals parse-manual
```
