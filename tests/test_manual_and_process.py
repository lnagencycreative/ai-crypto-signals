import json
from pathlib import Path

import yaml

from ai_crypto_signals.config import project_root
from ai_crypto_signals.parsing.manual import iter_manual_paths, load_manual_responses
from ai_crypto_signals.processing.build import build_processed


def test_manual_files_parse_and_examples_are_ignored():
    root = project_root()
    paths = iter_manual_paths(root)
    names = {path.name for path in paths}
    assert names == {
        "2026-10-23_chatgpt.md",
        "2026-10-23_gemini.md",
        "2026-10-23_claude.md",
        "2026-10-23_grok.md",
        "2026-10-24_chatgpt.md",
        "2026-10-24_gemini.md",
        "2026-10-24_claude.md",
        "2026-10-24_grok.md",
        "2026-10-25_chatgpt.md",
        "2026-10-25_gemini.md",
        "2026-10-25_claude.md",
        "2026-10-25_grok.md",
        "2026-10-26_chatgpt.md",
        "2026-10-26_gemini.md",
        "2026-10-26_claude.md",
        "2026-10-26_grok.md",
        "2026-10-27_chatgpt.md",
        "2026-10-27_gemini.md",
        "2026-10-27_claude.md",
        "2026-10-27_grok.md",
        "2026-10-28_chatgpt.md",
        "2026-10-28_gemini.md",
        "2026-10-28_claude.md",
        "2026-10-28_grok.md",
        "2026-10-29_chatgpt.md",
        "2026-10-29_gemini.md",
        "2026-10-29_claude.md",
        "2026-10-29_grok.md",
    }
    responses = {item.path: item for item in load_manual_responses(root)}

    for name in (
        "2026-10-23_chatgpt.md",
        "2026-10-23_claude.md",
        "2026-10-23_grok.md",
        "2026-10-24_claude.md",
        "2026-10-24_grok.md",
        "2026-10-25_claude.md",
        "2026-10-25_grok.md",
        "2026-10-26_claude.md",
        "2026-10-27_claude.md",
        "2026-10-28_claude.md",
    ):
        skipped = responses[name]
        assert skipped.status == "skipped"
        assert skipped.skip_reason == "login required"
        assert skipped.transcript_fidelity == "not_collected"
        assert skipped.extraction.mentions == ()
        assert skipped.text == "No answer was collected."

    day1 = responses["2026-10-23_gemini.md"]
    assert day1.status == "ok"
    assert day1.model == "Gemini Auto"
    assert day1.transcript_fidelity == "verbatim"
    assert day1.collected_at == "2026-10-23T13:09:00Z"
    assert day1.text.startswith("Here are five prominent cryptocurrencies to keep an eye on this week")
    assert "4. Chainlink (LINK)" in day1.text
    assert "5. Ripple (XRP)" in day1.text
    assert day1.text.endswith("always conduct your own research before making investment decisions.")
    assert [(mention.list_type, mention.rank, mention.symbol) for mention in day1.extraction.mentions] == [
        ("watch", 1, "BTC"),
        ("watch", 2, "ETH"),
        ("watch", 3, "SOL"),
        ("watch", 4, "LINK"),
        ("watch", 5, "XRP"),
        ("watch", None, "ARB"),
        ("watch", None, "OP"),
    ]
    assert responses["2026-10-23_chatgpt.md"].collected_at == "2026-10-23T13:08:00Z"
    assert responses["2026-10-23_grok.md"].model == "Fast"

    chatgpt = responses["2026-10-24_chatgpt.md"]
    assert chatgpt.status == "ok"
    assert chatgpt.model == ""
    assert chatgpt.transcript_fidelity == "verbatim"
    assert chatgpt.collected_at == "2026-10-24T13:06:35Z"
    assert chatgpt.text.startswith("5 cryptocurrencies to watch this week")
    assert chatgpt.text.endswith("ChatGPT is AI and can make mistakes.")
    assert [(mention.rank, mention.symbol) for mention in chatgpt.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "LINK"),
        (5, "XRP"),
    ]

    gemini = responses["2026-10-24_gemini.md"]
    assert gemini.status == "ok"
    assert gemini.model == "Gemini Auto"
    assert gemini.transcript_fidelity == "verbatim"
    assert gemini.collected_at == "2026-10-24T13:06:00Z"
    assert gemini.text.startswith("The cryptocurrency market is navigating a critical consolidation phase")
    assert "5. Hyperliquid (HYPE)" in gemini.text
    assert gemini.text.endswith("Geco Capital")
    assert [(mention.rank, mention.symbol) for mention in gemini.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "LINK"),
        (5, "HYPE"),
    ]
    assert responses["2026-10-24_grok.md"].model == "Fast"
    assert responses["2026-10-24_grok.md"].collected_at == "2026-10-24T13:07:34Z"

    chatgpt_25 = responses["2026-10-25_chatgpt.md"]
    assert chatgpt_25.status == "ok"
    assert chatgpt_25.model == ""
    assert chatgpt_25.transcript_fidelity == "verbatim"
    assert chatgpt_25.collected_at == "2026-10-25T13:12:00Z"
    assert chatgpt_25.text.startswith("For the week of October 26–November 1, 2026")
    assert chatgpt_25.text.endswith("Fidelity Investments — Research Crypto ETFs Today (Ad)")
    assert [(mention.rank, mention.symbol) for mention in chatgpt_25.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "LINK"),
        (5, "XRP"),
    ]
    assert chatgpt_25.extraction.mentions[2].sentiment_label == "positive"

    gemini_25 = responses["2026-10-25_gemini.md"]
    assert gemini_25.status == "ok"
    assert gemini_25.model == "Gemini Auto"
    assert gemini_25.transcript_fidelity == "verbatim"
    assert gemini_25.collected_at == "2026-10-25T13:15:00Z"
    assert gemini_25.text.startswith("Evaluating and ranking cryptocurrencies involves subjective criteria")
    assert "5. NEAR Protocol (NEAR)" in gemini_25.text
    assert gemini_25.text.endswith("rather than financial advice.")
    assert [(mention.rank, mention.symbol) for mention in gemini_25.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "ZEC"),
        (5, "NEAR"),
    ]
    assert responses["2026-10-25_grok.md"].model == "Fast"
    assert responses["2026-10-25_grok.md"].collected_at == "2026-10-25T13:18:00Z"

    assert responses["2026-10-26_chatgpt.md"].skip_reason == "guest page reset with no answer"
    assert responses["2026-10-26_chatgpt.md"].collected_at == "2026-10-26T13:07:00Z"
    assert responses["2026-10-26_grok.md"].skip_reason == "sign-up wall"
    assert responses["2026-10-26_grok.md"].model == "Fast"
    assert responses["2026-10-26_grok.md"].collected_at == "2026-10-26T13:12:00Z"

    gemini_26 = responses["2026-10-26_gemini.md"]
    assert gemini_26.status == "ok"
    assert gemini_26.model == "Auto"
    assert gemini_26.transcript_fidelity == "verbatim"
    assert gemini_26.collected_at == "2026-10-26T13:05:00Z"
    assert gemini_26.text.startswith("5 top cryptocurrencies worth watching")
    assert "5. Hyperliquid (HYPE) / Zcash (ZEC)" in gemini_26.text
    assert gemini_26.text.endswith("not financial advice.")
    assert [(mention.rank, mention.symbol) for mention in gemini_26.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "LINK"),
        (5, "HYPE"),
        (None, "ZEC"),
    ]

    chatgpt_27 = responses["2026-10-27_chatgpt.md"]
    assert chatgpt_27.status == "ok"
    assert chatgpt_27.model == ""
    assert chatgpt_27.transcript_fidelity == "verbatim"
    assert chatgpt_27.collected_at == "2026-10-27T13:05:00Z"
    assert chatgpt_27.text.startswith("5 cryptocurrencies to watch this week, ranked")
    assert chatgpt_27.text.endswith("ChatGPT is AI and can make mistakes.")
    assert [(mention.rank, mention.symbol) for mention in chatgpt_27.extraction.mentions] == [
        (1, "BTC"),
        (2, "XRP"),
        (3, "ETH"),
        (4, "SOL"),
        (5, "ZEC"),
    ]

    gemini_27 = responses["2026-10-27_gemini.md"]
    assert gemini_27.status == "ok"
    assert gemini_27.model == "Gemini Auto"
    assert gemini_27.transcript_fidelity == "verbatim"
    assert gemini_27.collected_at == "2026-10-27T13:04:00Z"
    assert gemini_27.text.startswith("Top 5 Cryptocurrencies to Watch")
    assert "5 | Sui (SUI)" in gemini_27.text
    assert gemini_27.text.endswith("and real-time market data.")
    assert [(mention.rank, mention.symbol) for mention in gemini_27.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "LINK"),
        (5, "SUI"),
    ]
    assert gemini_27.extraction.mentions[4].rank_source == "table"

    assert responses["2026-10-27_grok.md"].skip_reason == "sign-up wall"
    assert responses["2026-10-27_grok.md"].model == "Fast"
    assert responses["2026-10-27_grok.md"].collected_at == "2026-10-27T13:06:00Z"

    assert responses["2026-10-28_chatgpt.md"].skip_reason == "guest page reset with no answer"
    assert responses["2026-10-28_chatgpt.md"].collected_at == "2026-10-28T13:05:00Z"
    assert responses["2026-10-28_grok.md"].skip_reason == "sign-up wall"
    assert responses["2026-10-28_grok.md"].model == "Fast"
    assert responses["2026-10-28_grok.md"].collected_at == "2026-10-28T13:06:00Z"

    gemini_28 = responses["2026-10-28_gemini.md"]
    assert gemini_28.status == "ok"
    assert gemini_28.model == ""
    assert gemini_28.transcript_fidelity == "verbatim"
    assert gemini_28.collected_at == "2026-10-28T13:06:00Z"
    assert gemini_28.text.startswith("Bitcoin (BTC)")
    assert "Zcash (ZEC)" in gemini_28.text
    assert gemini_28.text.endswith("whether recent momentum is persistent or short-lived.")
    assert [(mention.rank, mention.symbol) for mention in gemini_28.extraction.mentions] == [
        (None, "BTC"),
        (None, "ETH"),
        (None, "SOL"),
        (None, "XRP"),
        (None, "ZEC"),
    ]

    chatgpt_29 = responses["2026-10-29_chatgpt.md"]
    assert chatgpt_29.status == "ok"
    assert chatgpt_29.model == "Instant"
    assert chatgpt_29.prompt_id == "weekly_watch_v1"
    assert chatgpt_29.transcript_fidelity == "reformatted"
    assert chatgpt_29.collected_at == "2026-10-29T13:06:00Z"
    assert chatgpt_29.text.startswith("Top 5 cryptocurrencies to watch this week")
    assert chatgpt_29.text.endswith("maximizing upside rather than limiting downside.")
    assert [(mention.rank, mention.symbol) for mention in chatgpt_29.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "XRP"),
        (5, "LINK"),
    ]

    claude_29 = responses["2026-10-29_claude.md"]
    assert claude_29.status == "skipped"
    assert claude_29.skip_reason == "organization disabled"
    assert claude_29.prompt_id == "weekly_watch_v1"
    assert claude_29.transcript_fidelity == "not_collected"
    assert claude_29.collected_at == "2026-10-29T13:07:00Z"
    assert claude_29.extraction.mentions == ()
    assert claude_29.text == "No answer was collected."

    gemini_29 = responses["2026-10-29_gemini.md"]
    assert gemini_29.status == "ok"
    assert gemini_29.model == "Gemini Auto"
    assert gemini_29.prompt_id == "weekly_watch_v1"
    assert gemini_29.transcript_fidelity == "reformatted"
    assert gemini_29.collected_at == "2026-10-29T13:08:00Z"
    assert gemini_29.text.startswith("Here are the top 5 cryptocurrencies to watch this week")
    assert gemini_29.text.endswith("should not be taken as direct financial advice.")
    assert [(mention.rank, mention.symbol) for mention in gemini_29.extraction.mentions] == [
        (1, "BTC"),
        (2, "ZEC"),
        (3, "SOL"),
        (4, "ETH"),
        (5, "XRP"),
    ]

    grok_29 = responses["2026-10-29_grok.md"]
    assert grok_29.status == "ok"
    assert grok_29.model == "Fast"
    assert grok_29.prompt_id == "weekly_watch_v1"
    assert grok_29.transcript_fidelity == "reformatted"
    assert grok_29.collected_at == "2026-10-29T13:09:00Z"
    assert grok_29.text.startswith("Here are 5 cryptocurrencies worth watching this week")
    assert grok_29.text.endswith("than pure altcoin idiosyncrasies.")
    assert [(mention.rank, mention.symbol) for mention in grok_29.extraction.mentions] == [
        (1, "BTC"),
        (2, "HYPE"),
        (3, "ZEC"),
        (4, "XRP"),
        (5, "SOL"),
        (None, "ETH"),
    ]


def test_process_rebuilds_tables_from_raw(tmp_path: Path):
    manual = tmp_path / "data" / "raw" / "llm_manual"
    manual.mkdir(parents=True)
    (manual / "note.md").write_text(
        "---\n"
        "provider: chatgpt\n"
        'collected_at: "2026-10-23T04:16:43Z"\n'
        "transcript_fidelity: verbatim\n"
        "---\n\n"
        "1. Bitcoin (BTC) — benchmark\n",
        encoding="utf-8",
    )
    (manual / "examples").mkdir()
    (manual / "examples" / "template.md").write_text(
        "---\nprovider: chatgpt\ncollected_at: '2026-10-23T00:00:00Z'\n---\n\n1. Solana (SOL) — ignore\n",
        encoding="utf-8",
    )
    coingecko = tmp_path / "data" / "raw" / "coingecko"
    coingecko.mkdir(parents=True)
    (coingecko / "snap_markets.json").write_text(
        json.dumps(
            {
                "collected_at": "2026-10-23T04:30:00Z",
                "coins": [
                    {
                        "id": "bitcoin",
                        "symbol": "btc",
                        "name": "Bitcoin",
                        "current_price": 100.0,
                        "market_cap": 10,
                        "total_volume": 5,
                        "price_change_percentage_24h": -1.5,
                        "price_change_percentage_7d_in_currency": 0.2,
                        "market_cap_rank": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    polymarket = tmp_path / "data" / "raw" / "polymarket"
    polymarket.mkdir(parents=True)
    (polymarket / "snap_gamma.json").write_text(
        json.dumps(
            {
                "collected_at": "2026-10-23T04:30:00Z",
                "markets": [
                    {
                        "id": "1",
                        "question": "Will Bitcoin reach $85,000 in October?",
                        "slug": "will-bitcoin-reach-85000",
                        "endDate": "2026-11-01T04:00:00Z",
                        "closed": False,
                        "active": True,
                        "volumeNum": 1000,
                        "volume24hr": 50,
                        "liquidityNum": 10,
                        "outcomes": "[\"Yes\", \"No\"]",
                        "outcomePrices": "[\"0.45\", \"0.55\"]",
                        "bestBid": 0.44,
                        "bestAsk": 0.46,
                        "lastTradePrice": 0.45,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (polymarket / "snap_clob.json").write_text(
        json.dumps(
            {
                "collected_at": "2026-10-23T04:30:00Z",
                "tokens": [
                    {"market_id": "1", "outcome": "Yes", "token_id": "yes", "mid": "0.45"},
                    {"market_id": "1", "outcome": "No", "token_id": "no", "mid": "0.55"},
                ],
            }
        ),
        encoding="utf-8",
    )
    # A pyproject marker is not required: data_paths stays inside tmp_path
    # when no project file is found while walking parents. /tmp has none.
    frames = build_processed(tmp_path)
    assert list(frames["coin_mentions"]["symbol"]) == ["BTC"]
    assert frames["coin_mentions"].iloc[0]["rank"] == 1
    assert frames["coin_mentions"].iloc[0]["list_type"] == "watch"
    assert frames["prices"].iloc[0]["price_usd"] == 100.0
    assert frames["prices"].iloc[0]["in_watchlist"] == True  # noqa: E712
    odds = frames["polymarket_odds"].iloc[0]
    assert odds["yes_price"] == 0.45
    assert odds["clob_yes_mid"] == 0.45
    assert odds["linked_symbols"] == "BTC"
    assert odds["ended"] == False  # noqa: E712
    assert (tmp_path / "data" / "processed" / "llm_responses.csv").exists()
    # The example template must not become a Solana mention.
    assert "SOL" not in set(frames["coin_mentions"]["symbol"])
    # Front matter from the real Day 1 files still parses as YAML. This guards
    # the quoting of the prompt, which contains a colon.
    day1 = yaml.safe_load(
        (project_root() / "data/raw/llm_manual/2026-10-23_chatgpt.md")
        .read_text(encoding="utf-8")
        .split("---", 2)[1]
    )
    assert day1["prompt"].startswith("Which 5 cryptocurrencies")


def test_processed_mentions_split_the_7_day_return_list(tmp_path: Path):
    manual = tmp_path / "data" / "raw" / "llm_manual"
    manual.mkdir(parents=True)
    (manual / "note.md").write_text(
        "---\n"
        "provider: chatgpt\n"
        'collected_at: "2026-10-28T13:00:00Z"\n'
        "prompt_id: weekly_watch_return_v2\n"
        "transcript_fidelity: verbatim\n"
        "---\n\n"
        "Watch list\n"
        "1. Bitcoin (BTC) — benchmark\n"
        "2. Ethereum (ETH) — fees\n"
        "\n"
        "7-day return rank\n"
        "1. Solana (SOL) — highest expected return\n"
        "2. Bitcoin (BTC) — still positive, behind Solana\n",
        encoding="utf-8",
    )
    frames = build_processed(tmp_path)
    rows = frames["coin_mentions"]
    got = [
        (list_type, int(rank), symbol)
        for list_type, rank, symbol in zip(rows["list_type"], rows["rank"], rows["symbol"])
    ]
    assert got == [
        ("watch", 1, "BTC"),
        ("watch", 2, "ETH"),
        ("return_7d", 1, "SOL"),
        ("return_7d", 2, "BTC"),
    ]
    assert list(rows.columns).count("list_type") == 1
