"""Turn raw JSON and manual logs into stable CSV tables.

Raw files stay the record of what was collected. These tables are derived
and can be deleted and rebuilt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ai_crypto_signals.config import coins_by_id, data_paths
from ai_crypto_signals.parsing.manual import load_manual_responses
from ai_crypto_signals.parsing.mentions import Extraction, Mention, extract_answer_mentions, extract_mentions
from ai_crypto_signals.util import parse_json_list, parse_time, read_json, to_float

PRICE_COLUMNS = [
    "collected_at",
    "coingecko_id",
    "symbol",
    "name",
    "price_usd",
    "market_cap",
    "total_volume",
    "price_change_percentage_24h",
    "price_change_percentage_7d",
    "market_cap_rank",
    "in_watchlist",
]

ODDS_COLUMNS = [
    "collected_at",
    "market_id",
    "question",
    "slug",
    "end_date",
    "ended",
    "closed",
    "active",
    "volume_num",
    "volume_24hr",
    "liquidity_num",
    "yes_price",
    "no_price",
    "best_bid",
    "best_ask",
    "last_trade_price",
    "clob_yes_mid",
    "clob_no_mid",
    "linked_coin_ids",
    "linked_symbols",
    "outcomes",
]

RESPONSE_COLUMNS = [
    "response_id",
    "collected_at",
    "time_precision",
    "provider",
    "provider_label",
    "model",
    "status",
    "skip_reason",
    "source",
    "prompt_id",
    "transcript_fidelity",
    "session_note",
    "unresolved_symbols",
    "text",
]

MENTION_COLUMNS = [
    "response_id",
    "collected_at",
    "provider",
    "provider_label",
    "source",
    "coingecko_id",
    "symbol",
    "name",
    "list_type",
    "rank",
    "rank_source",
    "in_ranked_list",
    "rationale",
    "sentiment_label",
    "positive_terms",
    "negative_terms",
    "match_forms",
    "in_watchlist",
]


def _write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _json_files(directory: Path, pattern: str) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob(pattern) if path.is_file())


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _outcome_price(market: dict[str, Any], label: str) -> float | None:
    outcomes = [str(item) for item in parse_json_list(market.get("outcomes"))]
    prices = parse_json_list(market.get("outcomePrices"))
    try:
        index = [item.lower() for item in outcomes].index(label.lower())
    except ValueError:
        return None
    if index >= len(prices):
        return None
    return to_float(prices[index])


def _price_rows(root: Path) -> list[dict[str, Any]]:
    registry = coins_by_id()
    rows: list[dict[str, Any]] = []
    for path in _json_files(data_paths(root)["raw_coingecko"], "*.json"):
        payload = read_json(path)
        collected_at = payload.get("collected_at")
        for coin in payload.get("coins") or []:
            if not isinstance(coin, dict):
                continue
            coin_id = str(coin.get("id") or "")
            known = registry.get(coin_id)
            change_7d = coin.get("price_change_percentage_7d_in_currency")
            if change_7d is None:
                change_7d = coin.get("price_change_percentage_7d")
            rows.append(
                {
                    "collected_at": collected_at,
                    "coingecko_id": coin_id,
                    "symbol": (known.symbol if known else str(coin.get("symbol") or "").upper()),
                    "name": known.name if known else coin.get("name"),
                    "price_usd": to_float(coin.get("current_price")),
                    "market_cap": to_float(coin.get("market_cap")),
                    "total_volume": to_float(coin.get("total_volume")),
                    "price_change_percentage_24h": to_float(coin.get("price_change_percentage_24h")),
                    "price_change_percentage_7d": to_float(change_7d),
                    "market_cap_rank": coin.get("market_cap_rank"),
                    "in_watchlist": bool(known and known.in_watchlist),
                }
            )
    return rows


def _clob_index(root: Path) -> dict[tuple[str, str, str], str | None]:
    index: dict[tuple[str, str, str], str | None] = {}
    for path in _json_files(data_paths(root)["raw_polymarket"], "*_clob.json"):
        payload = read_json(path)
        collected_at = str(payload.get("collected_at") or "")
        for token in payload.get("tokens") or []:
            if not isinstance(token, dict):
                continue
            key = (collected_at, str(token.get("market_id") or ""), str(token.get("outcome") or ""))
            index[key] = token.get("mid")
    return index


def _link(question: str, slug: str) -> tuple[str, str]:
    slug_words = slug.replace("-", " ")
    extraction = extract_mentions(f"{question}\n{slug_words}\n{slug_words.title()}")
    coin_ids = [mention.coingecko_id for mention in extraction.mentions]
    symbols = [mention.symbol for mention in extraction.mentions]
    return "|".join(coin_ids), "|".join(symbols)


def _odds_rows(root: Path) -> list[dict[str, Any]]:
    mids = _clob_index(root)
    rows: list[dict[str, Any]] = []
    for path in _json_files(data_paths(root)["raw_polymarket"], "*_gamma.json"):
        payload = read_json(path)
        collected_at = str(payload.get("collected_at") or "")
        observed = parse_time(collected_at)
        for market in payload.get("markets") or []:
            if not isinstance(market, dict):
                continue
            market_id = str(market.get("id") or "")
            end_date = _first(market, "endDate", "end_date")
            end_dt = parse_time(str(end_date) if end_date else None)
            ended = bool(observed and end_dt and end_dt <= observed)
            question = str(market.get("question") or "")
            slug = str(market.get("slug") or "")
            linked_ids, linked_symbols = _link(question, slug)
            outcome_names = [str(item) for item in parse_json_list(market.get("outcomes"))]
            rows.append(
                {
                    "collected_at": collected_at,
                    "market_id": market_id,
                    "question": question,
                    "slug": slug,
                    "end_date": end_date,
                    "ended": ended,
                    "closed": market.get("closed"),
                    "active": market.get("active"),
                    "volume_num": to_float(_first(market, "volumeNum", "volume_num", "volume")),
                    "volume_24hr": to_float(_first(market, "volume24hr", "volume24hrClob")),
                    "liquidity_num": to_float(_first(market, "liquidityNum", "liquidity_num", "liquidity")),
                    "yes_price": _outcome_price(market, "Yes"),
                    "no_price": _outcome_price(market, "No"),
                    "best_bid": to_float(market.get("bestBid")),
                    "best_ask": to_float(market.get("bestAsk")),
                    "last_trade_price": to_float(market.get("lastTradePrice")),
                    "clob_yes_mid": to_float(mids.get((collected_at, market_id, "Yes"))),
                    "clob_no_mid": to_float(mids.get((collected_at, market_id, "No"))),
                    "linked_coin_ids": linked_ids,
                    "linked_symbols": linked_symbols,
                    "outcomes": " | ".join(outcome_names),
                }
            )
    return rows


def _mention_rows(
    response_id: str,
    collected_at: str,
    provider: str,
    provider_label: str,
    source: str,
    extraction: Extraction,
) -> list[dict[str, Any]]:
    rows = []
    for mention in extraction.mentions:
        rows.append(_mention_dict(response_id, collected_at, provider, provider_label, source, mention))
    return rows


def _mention_dict(
    response_id: str,
    collected_at: str,
    provider: str,
    provider_label: str,
    source: str,
    mention: Mention,
) -> dict[str, Any]:
    return {
        "response_id": response_id,
        "collected_at": collected_at,
        "provider": provider,
        "provider_label": provider_label,
        "source": source,
        "coingecko_id": mention.coingecko_id,
        "symbol": mention.symbol,
        "name": mention.name,
        "list_type": mention.list_type,
        "rank": mention.rank,
        "rank_source": mention.rank_source,
        "in_ranked_list": mention.rank is not None,
        "rationale": mention.rationale,
        "sentiment_label": mention.sentiment_label,
        "positive_terms": "|".join(mention.positive_terms),
        "negative_terms": "|".join(mention.negative_terms),
        "match_forms": "|".join(mention.match_forms),
        "in_watchlist": mention.in_watchlist,
    }


def _response_rows(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    responses: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []
    for manual in load_manual_responses(root):
        responses.append(
            {
                "response_id": manual.response_id,
                "collected_at": manual.collected_at,
                "time_precision": manual.time_precision,
                "provider": manual.provider,
                "provider_label": manual.provider_label,
                "model": manual.model,
                "status": manual.status,
                "skip_reason": manual.skip_reason,
                "source": manual.source,
                "prompt_id": manual.prompt_id,
                "transcript_fidelity": manual.transcript_fidelity,
                "session_note": manual.session_note,
                "unresolved_symbols": "|".join(manual.extraction.unresolved_symbols),
                "text": manual.text,
            }
        )
        mentions.extend(
            _mention_rows(
                manual.response_id,
                manual.collected_at,
                manual.provider,
                manual.provider_label,
                manual.source,
                manual.extraction,
            )
        )

    for path in _json_files(data_paths(root)["raw_llm"], "*.json"):
        payload = read_json(path)
        response_id = "api:" + path.stem
        status = str(payload.get("status") or "")
        text = payload.get("response_text") or ""
        extraction = extract_answer_mentions(text) if status == "ok" and text else extract_answer_mentions("")
        responses.append(
            {
                "response_id": response_id,
                "collected_at": payload.get("collected_at"),
                "time_precision": "timestamp",
                "provider": payload.get("provider"),
                "provider_label": payload.get("provider_label"),
                "model": payload.get("model"),
                "status": status,
                "skip_reason": payload.get("skip_reason") or "",
                "source": "llm_api",
                "prompt_id": payload.get("prompt_id"),
                "transcript_fidelity": "api_response" if status == "ok" else "",
                "session_note": payload.get("error") or "",
                "unresolved_symbols": "|".join(extraction.unresolved_symbols),
                "text": text,
            }
        )
        mentions.extend(
            _mention_rows(
                response_id,
                str(payload.get("collected_at") or ""),
                str(payload.get("provider") or ""),
                str(payload.get("provider_label") or ""),
                "llm_api",
                extraction,
            )
        )
    return responses, mentions


def _frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    return frame.reindex(columns=columns)


def build_processed(root: Path | None = None) -> dict[str, pd.DataFrame]:
    base = data_paths(root)
    prices = _frame(_price_rows(base["root"]), PRICE_COLUMNS)
    if not prices.empty:
        prices = prices.sort_values(
            ["collected_at", "market_cap_rank", "symbol"],
            kind="mergesort",
        ).reset_index(drop=True)
    odds = _frame(_odds_rows(base["root"]), ODDS_COLUMNS)
    if not odds.empty:
        odds = odds.sort_values(
            ["collected_at", "volume_24hr", "market_id"],
            ascending=[True, False, True],
            kind="mergesort",
        ).reset_index(drop=True)
    response_rows, mention_rows = _response_rows(base["root"])
    responses = _frame(response_rows, RESPONSE_COLUMNS)
    if not responses.empty:
        responses = responses.sort_values(
            ["collected_at", "provider", "response_id"],
            kind="mergesort",
        ).reset_index(drop=True)
    mentions = _frame(mention_rows, MENTION_COLUMNS)
    if not mentions.empty:
        mentions["_list_sort"] = (
            mentions["list_type"].map({"watch": 0, "return_7d": 1}).fillna(9)
        )
        mentions["_rank_sort"] = mentions["rank"].fillna(99)
        mentions = mentions.sort_values(
            ["collected_at", "provider", "_list_sort", "_rank_sort", "symbol"],
            kind="mergesort",
        ).drop(columns=["_list_sort", "_rank_sort"]).reset_index(drop=True)

    processed = base["processed"]
    frames = {
        "prices": prices,
        "polymarket_odds": odds,
        "llm_responses": responses,
        "coin_mentions": mentions,
    }
    for name, frame in frames.items():
        _write(frame, processed / f"{name}.csv")
    return frames


def load_processed(root: Path | None = None) -> dict[str, pd.DataFrame]:
    processed = data_paths(root)["processed"]
    frames: dict[str, pd.DataFrame] = {}
    for name in ("prices", "polymarket_odds", "llm_responses", "coin_mentions"):
        path = processed / f"{name}.csv"
        frames[name] = pd.read_csv(path) if path.exists() else pd.DataFrame()
    return frames
