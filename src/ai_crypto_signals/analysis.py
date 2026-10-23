"""Descriptive comparisons. None of these functions estimate a causal effect.

Lead-lag output stays empty until the price panel has successive snapshots
and enough coin-snapshot pairs. A correlation, once it exists, is still only
a description of this sample.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def jaccard(left: set[str], right: set[str]) -> float | None:
    union = left | right
    if not union:
        return None
    return len(left & right) / len(union)


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(values):
        end = position
        while end + 1 < len(values) and values[order[end + 1]] == values[order[position]]:
            end += 1
        # Ranks are 1-based. Ties share the average of the occupied ranks.
        average = (position + 1 + end + 1) / 2
        for index in order[position : end + 1]:
            ranks[index] = average
        position = end + 1
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    left_scale = math.sqrt(sum((x - mean_left) ** 2 for x in left))
    right_scale = math.sqrt(sum((y - mean_right) ** 2 for y in right))
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    return pearson(_average_ranks(left), _average_ranks(right))


def _utc_date(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value)
    if len(text) < 10:
        return None
    return text[:10]


def agreement_table(mentions: pd.DataFrame) -> pd.DataFrame:
    """Pairwise overlap of coins named by two providers on the same UTC date.

    Skipped providers never appear here, because they have no mention rows.
    """
    columns = [
        "date",
        "provider_a",
        "provider_b",
        "n_a",
        "n_b",
        "n_overlap",
        "jaccard",
        "n_ranked_overlap",
        "spearman_rank",
    ]
    if mentions.empty:
        return pd.DataFrame(columns=columns)
    frame = mentions.copy()
    frame["date"] = frame["collected_at"].map(_utc_date)
    rows: list[dict[str, Any]] = []
    for day, day_frame in frame.groupby("date", dropna=True):
        providers = sorted(day_frame["provider"].dropna().unique())
        grouped = {provider: day_frame[day_frame["provider"] == provider] for provider in providers}
        for index, provider_a in enumerate(providers):
            for provider_b in providers[index + 1 :]:
                left = grouped[provider_a]
                right = grouped[provider_b]
                set_a = set(left["coingecko_id"])
                set_b = set(right["coingecko_id"])
                overlap = set_a & set_b
                ranked_left = {
                    row.coingecko_id: float(row.rank)
                    for row in left.itertuples(index=False)
                    if pd.notna(row.rank) and row.coingecko_id in overlap
                }
                ranked_right = {
                    row.coingecko_id: float(row.rank)
                    for row in right.itertuples(index=False)
                    if pd.notna(row.rank) and row.coingecko_id in overlap
                }
                shared_ranked = sorted(set(ranked_left) & set(ranked_right))
                coefficient = None
                if len(shared_ranked) >= 2:
                    coefficient = spearman(
                        [ranked_left[coin_id] for coin_id in shared_ranked],
                        [ranked_right[coin_id] for coin_id in shared_ranked],
                    )
                rows.append(
                    {
                        "date": day,
                        "provider_a": provider_a,
                        "provider_b": provider_b,
                        "n_a": len(set_a),
                        "n_b": len(set_b),
                        "n_overlap": len(overlap),
                        "jaccard": jaccard(set_a, set_b),
                        "n_ranked_overlap": len(shared_ranked),
                        "spearman_rank": coefficient,
                    }
                )
    return pd.DataFrame(rows, columns=columns)


def lead_lag_screen(
    prices: pd.DataFrame,
    mentions: pd.DataFrame,
    *,
    min_pairs: int = 8,
) -> dict[str, Any]:
    """Screen whether a same-day mention lines up with the next price snapshot.

    The return is from one snapshot to the next snapshot of that coin, which
    is only a one-day return when collection actually ran once per day.
    """
    method = (
        "Pearson correlation between a same-UTC-date mention indicator and "
        "the price change to the next snapshot of that coin. Descriptive only."
    )
    result: dict[str, Any] = {
        "estimable": False,
        "reason": "",
        "n_price_dates": 0,
        "n_pairs": 0,
        "min_pairs": min_pairs,
        "correlation": None,
        "method": method,
    }
    if prices.empty or "price_usd" not in prices.columns:
        result["reason"] = "No CoinGecko price snapshots are in the processed tables yet."
        return result

    panel = prices.copy()
    panel["date"] = panel["collected_at"].map(_utc_date)
    panel = panel.dropna(subset=["date", "coingecko_id", "price_usd"])
    panel = panel[panel["price_usd"] > 0]
    if panel.empty:
        result["reason"] = "Price rows do not include a positive USD price."
        return result
    # Several snapshots on one UTC date collapse to the last one.
    panel = (
        panel.sort_values(["coingecko_id", "date", "collected_at"], kind="mergesort")
        .groupby(["coingecko_id", "date"], as_index=False)
        .tail(1)
    )
    dates = sorted(panel["date"].unique())
    result["n_price_dates"] = len(dates)
    if len(dates) < 2:
        result["reason"] = (
            "Lead-lag needs price snapshots on at least two UTC dates. "
            f"The panel currently has {len(dates)}."
        )
        return result

    mention_keys: set[tuple[str, str]] = set()
    if not mentions.empty and {"collected_at", "coingecko_id"}.issubset(mentions.columns):
        for row in mentions.itertuples(index=False):
            day = _utc_date(row.collected_at)
            if day:
                mention_keys.add((day, str(row.coingecko_id)))

    indicators: list[float] = []
    returns: list[float] = []
    for coin_id, coin_frame in panel.groupby("coingecko_id"):
        ordered = coin_frame.sort_values("date")
        rows = list(ordered.itertuples(index=False))
        for earlier, later in zip(rows, rows[1:]):
            indicators.append(1.0 if (earlier.date, str(coin_id)) in mention_keys else 0.0)
            returns.append((later.price_usd / earlier.price_usd) - 1.0)
    result["n_pairs"] = len(indicators)
    if len(indicators) < min_pairs:
        result["reason"] = (
            f"Only {len(indicators)} coin-snapshot pairs are available. "
            f"The screen waits for {min_pairs} before reporting a correlation."
        )
        return result
    coefficient = pearson(indicators, returns)
    if coefficient is None:
        result["reason"] = (
            "The pairs do not vary enough to compute a correlation. "
            "That usually means every coin was mentioned, or none were."
        )
        return result
    result["estimable"] = True
    result["correlation"] = coefficient
    result["reason"] = (
        "A descriptive correlation is available. It is not evidence that "
        "mentions lead prices, or the reverse."
    )
    return result
