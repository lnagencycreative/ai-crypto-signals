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
    }
    responses = {item.path: item for item in load_manual_responses(root)}

    for name in (
        "2026-10-23_chatgpt.md",
        "2026-10-23_claude.md",
        "2026-10-23_grok.md",
        "2026-10-24_claude.md",
        "2026-10-24_grok.md",
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
    assert [(mention.rank, mention.symbol) for mention in day1.extraction.mentions] == [
        (1, "BTC"),
        (2, "ETH"),
        (3, "SOL"),
        (4, "LINK"),
        (5, "XRP"),
        (None, "ARB"),
        (None, "OP"),
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
