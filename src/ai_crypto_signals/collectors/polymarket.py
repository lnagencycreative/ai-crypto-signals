"""Polymarket snapshot: Gamma for market listings, CLOB for midpoint odds.

Both APIs are public. Gamma's outcome prices are kept either way. A CLOB
failure is stored next to the Gamma file and does not discard the listing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_crypto_signals.config import (
    POLYMARKET_CLOB_URL,
    POLYMARKET_GAMMA_URL,
    POLYMARKET_MAX_MARKETS,
    POLYMARKET_PAGE_SIZE,
    POLYMARKET_TAG_SLUG,
    data_paths,
)
from ai_crypto_signals.http_util import HttpError, Transport, request_json
from ai_crypto_signals.util import parse_json_list, stamp, write_json


def _lookup_tag(transport: Transport | None) -> dict[str, Any]:
    status, body = request_json(
        "GET",
        f"{POLYMARKET_GAMMA_URL}/tags/slug/{POLYMARKET_TAG_SLUG}",
        timeout=30,
        retries=2,
        transport=transport,
    )
    if status == 200 and isinstance(body, dict) and body.get("id"):
        return {
            "id": str(body.get("id")),
            "slug": body.get("slug") or POLYMARKET_TAG_SLUG,
            "label": body.get("label"),
            "lookup": "api",
        }
    return {
        "id": "21",
        "slug": POLYMARKET_TAG_SLUG,
        "label": "Crypto",
        "lookup": "fallback",
        "lookup_status": status,
    }


def _yes_no_tokens(market: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return CLOB token ids only when the outcomes are literally Yes and No.

    Up/Down and other binaries are left unlabeled. Treating the first token
    as Yes would put an Up price in the Yes column.
    """
    outcomes = [str(item) for item in parse_json_list(market.get("outcomes"))]
    tokens = [str(item) for item in parse_json_list(market.get("clobTokenIds"))]
    lowered = [item.lower() for item in outcomes]
    if "yes" not in lowered or "no" not in lowered:
        return None, None
    yes_index = lowered.index("yes")
    no_index = lowered.index("no")
    yes = tokens[yes_index] if yes_index < len(tokens) else None
    no = tokens[no_index] if no_index < len(tokens) else None
    return yes, no


def collect_polymarket(
    root: Path | None = None,
    *,
    transport: Transport | None = None,
    collected_at: str | None = None,
    max_markets: int = POLYMARKET_MAX_MARKETS,
) -> dict[str, Path]:
    paths = data_paths(root)
    iso, compact = stamp()
    if collected_at:
        iso = collected_at
        compact = collected_at.replace("-", "").replace(":", "").replace("T", "T")
    tag = _lookup_tag(transport)
    markets: list[dict[str, Any]] = []
    seen: set[str] = set()
    offset = 0
    pages = 0
    while len(markets) < max_markets and pages < 10:
        status, body = request_json(
            "GET",
            f"{POLYMARKET_GAMMA_URL}/markets",
            params={
                "tag_id": tag["id"],
                "closed": "false",
                "limit": min(POLYMARKET_PAGE_SIZE, max_markets - len(markets)),
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            },
            timeout=40,
            retries=2,
            transport=transport,
        )
        pages += 1
        if status != 200 or not isinstance(body, list):
            raise HttpError(
                f"Polymarket Gamma /markets returned HTTP {status}.",
                status=status,
                body=body,
            )
        if not body:
            break
        for market in body:
            if not isinstance(market, dict):
                continue
            market_id = str(market.get("id") or "")
            if market_id and market_id in seen:
                continue
            if market_id:
                seen.add(market_id)
            markets.append(market)
        if len(body) < POLYMARKET_PAGE_SIZE:
            break
        offset += len(body)

    gamma_payload = {
        "schema_version": 1,
        "source": "polymarket_gamma",
        "endpoint": f"{POLYMARKET_GAMMA_URL}/markets",
        "collected_at": iso,
        "tag": tag,
        "order": "volume24hr",
        "max_markets": max_markets,
        "market_count": len(markets),
        "markets": markets,
    }
    gamma_path = paths["raw_polymarket"] / f"{compact}_gamma.json"

    token_rows: list[dict[str, str]] = []
    for market in markets:
        yes_token, no_token = _yes_no_tokens(market)
        market_id = str(market.get("id") or "")
        if yes_token:
            token_rows.append({"market_id": market_id, "outcome": "Yes", "token_id": yes_token})
        if no_token:
            token_rows.append({"market_id": market_id, "outcome": "No", "token_id": no_token})

    mids: dict[str, str] = {}
    clob_error: str | None = None
    clob_status: int | None = None
    # The batch endpoint accepts 500 tokens. Stay under that.
    for start in range(0, len(token_rows), 400):
        chunk = token_rows[start : start + 400]
        status, body = request_json(
            "POST",
            f"{POLYMARKET_CLOB_URL}/midpoints",
            json_body=[{"token_id": row["token_id"]} for row in chunk],
            timeout=40,
            retries=1,
            transport=transport,
        )
        clob_status = status
        if status != 200 or not isinstance(body, dict):
            message = body.get("error") if isinstance(body, dict) else None
            clob_error = message or f"HTTP {status}"
            continue
        for token_id, mid in body.items():
            if mid is not None and "error" not in str(token_id).lower():
                mids[str(token_id)] = str(mid)

    clob_payload = {
        "schema_version": 1,
        "source": "polymarket_clob",
        "endpoint": f"{POLYMARKET_CLOB_URL}/midpoints",
        "collected_at": iso,
        "http_status": clob_status,
        "error": clob_error,
        "requested": len(token_rows),
        "returned": len(mids),
        "tokens": [
            {**row, "mid": mids.get(row["token_id"])}
            for row in token_rows
        ],
    }
    clob_path = paths["raw_polymarket"] / f"{compact}_clob.json"
    write_json(gamma_path, gamma_payload)
    write_json(clob_path, clob_payload)
    return {"gamma": gamma_path, "clob": clob_path}
