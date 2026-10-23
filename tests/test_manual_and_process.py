import json
from pathlib import Path

import yaml

from ai_crypto_signals.config import project_root
from ai_crypto_signals.parsing.manual import iter_manual_paths, load_manual_responses
from ai_crypto_signals.processing.build import build_processed


def test_day1_files_parse_and_examples_are_ignored():
    root = project_root()
    paths = iter_manual_paths(root)
    names = {path.name for path in paths}
    assert names == {
        "2026-10-23_chatgpt.md",
        "2026-10-23_gemini.md",
        "2026-10-23_claude.md",
        "2026-10-23_grok.md",
    }
    responses = {item.provider: item for item in load_manual_responses(root)}
    assert responses["openai"].status == "ok"
    assert responses["google"].status == "ok"
    assert responses["anthropic"].status == "skipped"
    assert responses["xai"].status == "skipped"
    assert responses["anthropic"].extraction.mentions == ()
    assert responses["xai"].skip_reason == "logged-out session returned no answer"
    for provider in ("openai", "google"):
        ranked = [(mention.rank, mention.symbol) for mention in responses[provider].extraction.mentions]
        assert ranked == [(1, "BTC"), (2, "ETH"), (3, "SOL"), (4, "XRP"), (5, "LINK")]
        assert responses[provider].transcript_fidelity == "abbreviated_session_notes"


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
