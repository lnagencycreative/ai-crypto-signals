import pandas as pd
import pytest

from ai_crypto_signals.analysis import agreement_table, jaccard, lead_lag_screen, spearman


def test_jaccard_and_spearman():
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert spearman([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == pytest.approx(1)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1)


def test_agreement_on_a_shared_ranking():
    mentions = pd.DataFrame(
        [
            {"collected_at": "2026-10-23T04:16:43Z", "provider": "openai", "coingecko_id": "bitcoin", "rank": 1},
            {"collected_at": "2026-10-23T04:16:43Z", "provider": "openai", "coingecko_id": "ethereum", "rank": 2},
            {"collected_at": "2026-10-23T04:17:24Z", "provider": "google", "coingecko_id": "bitcoin", "rank": 1},
            {"collected_at": "2026-10-23T04:17:24Z", "provider": "google", "coingecko_id": "ethereum", "rank": 2},
        ]
    )
    table = agreement_table(mentions)
    assert len(table) == 1
    row = table.iloc[0]
    assert row["jaccard"] == 1
    assert row["spearman_rank"] == pytest.approx(1)
    assert row["n_overlap"] == 2


def test_agreement_keeps_the_7_day_rank_out_of_the_watch_overlap():
    mentions = pd.DataFrame(
        [
            {
                "collected_at": "2026-10-28T13:00:00Z",
                "provider": "openai",
                "coingecko_id": "bitcoin",
                "rank": 1,
                "list_type": "watch",
            },
            {
                "collected_at": "2026-10-28T13:00:00Z",
                "provider": "openai",
                "coingecko_id": "ethereum",
                "rank": 2,
                "list_type": "watch",
            },
            {
                "collected_at": "2026-10-28T13:00:00Z",
                "provider": "openai",
                "coingecko_id": "bitcoin",
                "rank": 5,
                "list_type": "return_7d",
            },
            {
                "collected_at": "2026-10-28T13:00:00Z",
                "provider": "google",
                "coingecko_id": "bitcoin",
                "rank": 1,
                "list_type": "watch",
            },
            {
                "collected_at": "2026-10-28T13:00:00Z",
                "provider": "google",
                "coingecko_id": "ethereum",
                "rank": 2,
                "list_type": "watch",
            },
            {
                "collected_at": "2026-10-28T13:00:00Z",
                "provider": "google",
                "coingecko_id": "solana",
                "rank": 1,
                "list_type": "return_7d",
            },
        ]
    )
    table = agreement_table(mentions)
    assert len(table) == 1
    row = table.iloc[0]
    assert row["n_a"] == 2
    assert row["n_b"] == 2
    assert row["n_overlap"] == 2
    assert row["spearman_rank"] == pytest.approx(1)


def test_lead_lag_waits_for_a_second_date():
    prices = pd.DataFrame(
        [
            {
                "collected_at": "2026-10-23T04:30:00Z",
                "coingecko_id": "bitcoin",
                "price_usd": 100.0,
            }
        ]
    )
    screen = lead_lag_screen(prices, pd.DataFrame())
    assert screen["estimable"] is False
    assert screen["n_price_dates"] == 1
    assert screen["correlation"] is None


def test_lead_lag_correlation_is_descriptive_once_pairs_exist():
    rows = []
    for coin_id, path in (
        ("bitcoin", [100, 110, 110, 110]),
        ("ethereum", [100, 90, 90, 90]),
        ("solana", [100, 90, 90, 90]),
    ):
        for day, price in enumerate(path, start=1):
            rows.append(
                {
                    "collected_at": f"2026-10-0{day}T00:00:00Z",
                    "coingecko_id": coin_id,
                    "price_usd": price,
                }
            )
    mentions = pd.DataFrame(
        [{"collected_at": "2026-10-01T00:00:00Z", "coingecko_id": "bitcoin", "provider": "openai"}]
    )
    screen = lead_lag_screen(pd.DataFrame(rows), mentions, min_pairs=8)
    assert screen["n_pairs"] == 9
    assert screen["estimable"] is True
    assert screen["correlation"] > 0
