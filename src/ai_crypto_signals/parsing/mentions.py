"""Find coin mentions, ranks, and a small sentiment tag in one answer.

The extractor is a set of rules, not a model. It is built for this study's
prompt: a short ranked list, usually with tickers. Name matching uses the
registry in ``config.py``. Sentiment is a keyword check on the clause that
justifies a coin, and most clauses in this pilot come back ``unspecified``.

v2 answers contain two numbered lists. ``extract_answer_mentions`` splits on
the "7-day return rank" label so those ranks stay in separate rows
(``list_type`` ``watch`` or ``return_7d``). ``extract_mentions`` parses one
section and does not split.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from ai_crypto_signals.config import COINS, Coin

# Ranks the prompt asks for five names. Slots past 10 are ignored so dates
# and prices are less likely to look like a ranking.
_RANK_TOKEN = re.compile(
    r"(?:^|[\s,;:])#?(?P<rank>10|[1-9])\s*[.)\-:]?\s+\$?(?P<token>[A-Za-z][A-Za-z0-9]{1,24})\b"
)
_NUMBERED_LINE = re.compile(
    r"(?m)^\s*#?\s*(?P<rank>10|[1-9])\s*[.)\-:]\s+(?P<body>.+?)\s*$"
)
# Comparison tables in the chat apps sometimes state the rank as
# `1 | Bitcoin (BTC) | ...`. A markdown row that already starts with a pipe
# (`| 1 | Bitcoin price |`) is a notes table, not this rank list.
_RANK_PIPE_LINE = re.compile(
    r"(?m)^\s*(?P<rank>10|[1-9])\s*\|\s+(?P<body>.+?)\s*$"
)
_REASON_CLAUSE = re.compile(
    r"(?:^|[;\n:]|\s)\s*(?P<ticker>[A-Z][A-Z0-9]{1,9})\s*=\s*(?P<reason>[^;\n]+)"
)
_BARE_TICKER = re.compile(r"\b(?P<ticker>[A-Z][A-Z0-9]{1,9})\b")
_CONTEXT_TICKER = re.compile(
    r"(?:\$(?P<dollar>[A-Z][A-Z0-9]{1,9})\b|\((?P<paren>[A-Z][A-Z0-9]{1,9})\))"
)

# v2 labels the second list "7-day return rank". A line that only repeats the
# instruction ("Label the two lists ...") is not the start of that list.
_RETURN_RANK_HEADING = re.compile(
    r"(?im)^[ \t>*#_]*"
    r"(?:(?:part\s+)?\d{1,2}\s*[.)]\s*)?"
    r"(?:\*\*|__)?\s*"
    r"7\s*[-–—]?\s*day\s+return\s+rank\b"
)
_RETURN_RANK_LOOSE = re.compile(
    r"7\s*[-–—]?\s*day\s+return\s+rank",
    re.IGNORECASE,
)
_LABEL_INSTRUCTION = re.compile(r"label the two lists", re.IGNORECASE)

_POSITIVE = (
    "bullish",
    "upside",
    "outperform",
    "breakout",
    "accumulate",
    "rally",
    "surge",
    "momentum",
)
_NEGATIVE = (
    "bearish",
    "avoid",
    "downside",
    "underperform",
    "sell-off",
    "selloff",
    "dump",
    "crash",
)


@dataclass(frozen=True)
class Mention:
    coingecko_id: str
    symbol: str
    name: str
    rank: int | None
    rank_source: str
    rationale: str
    sentiment_label: str
    positive_terms: tuple[str, ...]
    negative_terms: tuple[str, ...]
    match_forms: tuple[str, ...]
    in_watchlist: bool
    # ``watch`` is the week's watch list. ``return_7d`` is the 7-day
    # expected-return rank. v1 answers are entirely ``watch``.
    list_type: str = "watch"


@dataclass(frozen=True)
class Extraction:
    mentions: tuple[Mention, ...]
    unresolved_symbols: tuple[str, ...]


@dataclass
class _Span:
    coin: Coin
    start: int
    end: int
    form: str


def _ticker_index(coins: tuple[Coin, ...]) -> dict[str, Coin]:
    index: dict[str, Coin] = {}
    for coin in coins:
        for ticker in coin.tickers():
            index.setdefault(ticker, coin)
    return index


def _term_hits(text: str, vocabulary: tuple[str, ...]) -> tuple[str, ...]:
    lowered = text.lower()
    found = []
    for term in vocabulary:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            found.append(term)
    return tuple(found)


def sentiment(text: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    positive = _term_hits(text, _POSITIVE)
    negative = _term_hits(text, _NEGATIVE)
    if positive and negative:
        label = "mixed"
    elif positive:
        label = "positive"
    elif negative:
        label = "negative"
    else:
        label = "unspecified"
    return label, positive, negative


def _name_spans(text: str, coins: tuple[Coin, ...]) -> list[_Span]:
    spans: list[_Span] = []
    for coin in coins:
        for form in coin.name_forms():
            flags = re.IGNORECASE if coin.form_ignorecase(form) else 0
            pattern = re.compile(rf"\b{re.escape(form)}\b", flags)
            for match in pattern.finditer(text):
                spans.append(_Span(coin, match.start(), match.end(), "name"))
    spans.sort(key=lambda span: (span.start, -(span.end - span.start)))
    kept: list[_Span] = []
    for span in spans:
        if any(span.start >= prior.start and span.end <= prior.end for prior in kept):
            continue
        kept.append(span)
    return kept


def _resolve_token(token: str, ticker_index: dict[str, Coin], coins: tuple[Coin, ...]) -> Coin | None:
    upper = token.upper()
    if upper == token and upper in ticker_index:
        return ticker_index[upper]
    for coin in coins:
        for form in coin.name_forms():
            if coin.form_ignorecase(form) and form.casefold() == token.casefold():
                return coin
            if not coin.form_ignorecase(form) and form == token:
                return coin
    return None


def _clean_reason(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .;")


def _instruction_mention(text: str, start: int) -> bool:
    window = text[max(0, start - 80) : start]
    return _LABEL_INSTRUCTION.search(window) is not None


def _return_rank_start(text: str) -> int | None:
    """Index where the 7-day return list begins, if the answer has one.

    A heading wins over a mid-sentence mention. The sentence in the prompt
    that tells the model to label the lists is not a heading, and it is
    skipped when it is the only match.
    """
    heading = _RETURN_RANK_HEADING.search(text)
    if heading is not None:
        return heading.start()
    for match in _RETURN_RANK_LOOSE.finditer(text):
        if not _instruction_mention(text, match.start()):
            return match.start()
    return None


def split_answer_lists(text: str) -> tuple[tuple[str, str], ...]:
    """Split one answer into ``watch`` and, when labeled, ``return_7d``.

    The v2 prompt puts the watch list first and the label "7-day return rank"
    on the second list. Text before that label is ``watch``. The label and
    the text after it are ``return_7d``. An answer with no label, including
    every v1 log, is a single ``watch`` section.
    """
    start = _return_rank_start(text)
    if start is None:
        return (("watch", text),)
    return (("watch", text[:start]), ("return_7d", text[start:]))


def extract_answer_mentions(text: str, coins: tuple[Coin, ...] | None = None) -> Extraction:
    """Extract mentions from one answer, one row per coin per list.

    The two numbered lists are parsed separately so a coin can be rank 1 on
    the watch list and a different rank on the 7-day return list. Those rows
    do not collapse into a rank conflict.
    """
    mentions: list[Mention] = []
    unresolved: list[str] = []
    for list_type, section in split_answer_lists(text):
        extraction = extract_mentions(section, coins)
        for mention in extraction.mentions:
            mentions.append(replace(mention, list_type=list_type))
        for symbol in extraction.unresolved_symbols:
            if symbol not in unresolved:
                unresolved.append(symbol)
    mentions.sort(
        key=lambda item: (
            0 if item.list_type == "watch" else 1,
            item.rank is None,
            item.rank or 0,
            item.symbol,
        )
    )
    return Extraction(mentions=tuple(mentions), unresolved_symbols=tuple(unresolved))


def extract_mentions(text: str, coins: tuple[Coin, ...] | None = None) -> Extraction:
    """Return one row per recognized coin, plus tickers we could not map."""
    catalog = coins if coins is not None else COINS
    ticker_index = _ticker_index(catalog)
    contextual = {
        ticker
        for coin in catalog
        for ticker in coin.contextual_tickers
    }

    spans = _name_spans(text, catalog)
    covered = [(span.start, span.end) for span in spans]

    def _inside_name(start: int, end: int) -> bool:
        return any(start >= left and end <= right for left, right in covered)

    forms: dict[str, set[str]] = {}
    present: dict[str, Coin] = {}

    def _add(coin: Coin, form: str) -> None:
        present[coin.coingecko_id] = coin
        forms.setdefault(coin.coingecko_id, set()).add(form)

    for span in spans:
        _add(span.coin, span.form)

    for match in _BARE_TICKER.finditer(text):
        ticker = match.group("ticker")
        if ticker in contextual or ticker not in ticker_index:
            continue
        if _inside_name(match.start(), match.end()):
            _add(ticker_index[ticker], "ticker")
            continue
        _add(ticker_index[ticker], "ticker")

    for match in _CONTEXT_TICKER.finditer(text):
        ticker = match.group("dollar") or match.group("paren")
        coin = ticker_index.get(ticker)
        if coin is None:
            continue
        _add(coin, "ticker")

    ranks: dict[str, tuple[int, str]] = {}
    unresolved: list[str] = []

    def _assign_rank(coin: Coin, rank: int, source: str) -> None:
        _add(coin, "rank")
        current = ranks.get(coin.coingecko_id)
        if current is None:
            ranks[coin.coingecko_id] = (rank, source)
            return
        if current[0] != rank:
            ranks[coin.coingecko_id] = (0, "conflict")

    for match in _RANK_TOKEN.finditer(text):
        rank = int(match.group("rank"))
        token = match.group("token")
        coin = _resolve_token(token, ticker_index, catalog)
        if coin is None:
            if token.isupper() and 2 <= len(token) <= 6 and token not in unresolved:
                unresolved.append(token)
            continue
        _assign_rank(coin, rank, "inline")

    def _first_coin_on_line(match) -> Coin | None:
        body = match.group("body")
        line_start = match.start("body")
        # First coin mentioned on the line takes the line rank. Later coins
        # on the same line stay mentions without inheriting that rank.
        candidates = []
        for inner in _RANK_TOKEN.finditer(body):
            coin = _resolve_token(inner.group("token"), ticker_index, catalog)
            if coin is not None:
                candidates.append((inner.start(), coin))
        for span in spans:
            if line_start <= span.start < match.end():
                candidates.append((span.start - line_start, span.coin))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    for match in _NUMBERED_LINE.finditer(text):
        coin = _first_coin_on_line(match)
        if coin is not None:
            _assign_rank(coin, int(match.group("rank")), "numbered_line")

    for match in _RANK_PIPE_LINE.finditer(text):
        coin = _first_coin_on_line(match)
        if coin is not None:
            _assign_rank(coin, int(match.group("rank")), "table")

    rationales: dict[str, str] = {}
    for match in _REASON_CLAUSE.finditer(text):
        coin = ticker_index.get(match.group("ticker"))
        if coin is None:
            continue
        _add(coin, "ticker")
        rationales.setdefault(coin.coingecko_id, _clean_reason(match.group("reason")))

    for match in _NUMBERED_LINE.finditer(text):
        body = match.group("body")
        split = re.split(r"\s+[—–]\s+|\s+-\s+", body, maxsplit=1)
        if len(split) != 2:
            continue
        line_start = match.start("body")
        candidates = [span for span in spans if line_start <= span.start < match.end()]
        if not candidates:
            # Fall back to the coin that received this line's rank.
            rank = int(match.group("rank"))
            owners = [cid for cid, (value, source) in ranks.items() if value == rank]
            if len(owners) == 1:
                rationales.setdefault(owners[0], _clean_reason(split[1]))
            continue
        first = min(candidates, key=lambda span: span.start)
        rationales.setdefault(first.coin.coingecko_id, _clean_reason(split[1]))

    mentions: list[Mention] = []
    for coin_id, coin in present.items():
        rank_info = ranks.get(coin_id)
        if rank_info is None:
            rank: int | None = None
            rank_source = ""
        elif rank_info[1] == "conflict":
            rank = None
            rank_source = "conflict"
        else:
            rank = rank_info[0]
            rank_source = rank_info[1]
        rationale = rationales.get(coin_id, "")
        label, positive, negative = sentiment(rationale)
        mentions.append(
            Mention(
                coingecko_id=coin.coingecko_id,
                symbol=coin.symbol,
                name=coin.name,
                rank=rank,
                rank_source=rank_source,
                rationale=rationale,
                sentiment_label=label,
                positive_terms=positive,
                negative_terms=negative,
                match_forms=tuple(sorted(forms[coin_id])),
                in_watchlist=coin.in_watchlist,
            )
        )

    mentions.sort(key=lambda item: (item.rank is None, item.rank or 0, item.symbol))
    return Extraction(mentions=tuple(mentions), unresolved_symbols=tuple(unresolved))
