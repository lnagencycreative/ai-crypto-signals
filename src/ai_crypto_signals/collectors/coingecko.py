"""CoinGecko market snapshot. The public API does not need a key."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_crypto_signals.config import (
    COINGECKO_MARKETS_URL,
    data_paths,
    watchlist_ids,
)
from ai_crypto_signals.http_util import HttpError, Transport, request_json
from ai_crypto_signals.parsing.manual import mentioned_coingecko_ids
from ai_crypto_signals.util import stamp, write_json


def price_ids(root: Path | None = None, extra_ids: list[str] | None = None) -> list[str]:
    """Watchlist first, then coins named in the manual log, then caller extras."""
    ordered: list[str] = []
    for coin_id in [*watchlist_ids(), *mentioned_coingecko_ids(root), *(extra_ids or [])]:
        if coin_id not in ordered:
            ordered.append(coin_id)
    return ordered


def collect_coingecko(
    root: Path | None = None,
    *,
    transport: Transport | None = None,
    collected_at: str | None = None,
    extra_ids: list[str] | None = None,
) -> Path:
    paths = data_paths(root)
    iso, compact = stamp()
    if collected_at:
        iso = collected_at
        compact = collected_at.replace("-", "").replace(":", "")
    requested = price_ids(paths["root"], extra_ids)
    coins: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    for start in range(0, len(requested), 50):
        chunk = requested[start : start + 50]
        params = {
            "vs_currency": "usd",
            "ids": ",".join(chunk),
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d",
        }
        status, body = request_json(
            "GET",
            COINGECKO_MARKETS_URL,
            params=params,
            timeout=40,
            retries=2,
            transport=transport,
        )
        calls.append({"status": status, "ids": chunk})
        if status != 200 or not isinstance(body, list):
            raise HttpError(
                f"CoinGecko /coins/markets returned HTTP {status}.",
                status=status,
                body=body,
            )
        coins.extend(item for item in body if isinstance(item, dict))

    returned = [item.get("id") for item in coins if item.get("id")]
    missing = [coin_id for coin_id in requested if coin_id not in returned]
    payload = {
        "schema_version": 1,
        "source": "coingecko",
        "endpoint": COINGECKO_MARKETS_URL,
        "collected_at": iso,
        "requested_ids": requested,
        "returned_ids": returned,
        "missing_ids": missing,
        "calls": calls,
        "coins": coins,
    }
    path = paths["raw_coingecko"] / f"{compact}_markets.json"
    write_json(path, payload)
    return path
