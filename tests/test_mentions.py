from ai_crypto_signals.config import COINS, watchlist_ids
from ai_crypto_signals.parsing.mentions import extract_mentions

DAY1 = (
    "Ranked: 1 BTC, 2 ETH, 3 SOL, 4 XRP, 5 LINK\n"
    "Reasons: BTC = market benchmark, ETF flows, Fed Oct 28; "
    "ETH = Glamsterdam Hoodi testnet Oct 26; "
    "SOL = Alpenglow upgrade live Oct 21; "
    "XRP = fixCleanup3_4_0 amendment ~Oct 23; "
    "LINK = oracle/RWA infrastructure, +20% since early Sept."
)


def _by_symbol(text: str) -> dict:
    extraction = extract_mentions(text)
    return {mention.symbol: mention for mention in extraction.mentions}, extraction


def test_watchlist_is_the_frozen_twenty():
    assert len(watchlist_ids()) == 20
    assert len(watchlist_ids()) == len(set(watchlist_ids()))
    assert len({coin.coingecko_id for coin in COINS}) == len(COINS)


def test_day1_rank_line():
    mentions, extraction = _by_symbol(DAY1)
    assert extraction.unresolved_symbols == ()
    assert [mentions[symbol].rank for symbol in ("BTC", "ETH", "SOL", "XRP", "LINK")] == [1, 2, 3, 4, 5]
    assert mentions["BTC"].rationale.startswith("market benchmark")
    assert mentions["LINK"].rationale.startswith("oracle/RWA")
    assert {mention.sentiment_label for mention in mentions.values()} == {"unspecified"}
    assert "ETF" not in mentions
    assert "RWA" not in mentions


def test_numbered_prose_and_an_unranked_aside():
    text = (
        "1. Bitcoin (BTC) — Institutional flows remain the cleanest read.\n"
        "2. Ethereum (ETH) — Settlement layer.\n"
        "I would not put Dogecoin (DOGE) in the five.\n"
    )
    mentions, _ = _by_symbol(text)
    assert mentions["BTC"].rank == 1
    assert mentions["ETH"].rank == 2
    assert mentions["DOGE"].rank is None
    assert "flows" in mentions["BTC"].rationale
    assert set(mentions) == {"BTC", "ETH", "DOGE"}


def test_bitcoin_cash_does_not_consume_bitcoin():
    mentions, _ = _by_symbol("Watch Bitcoin Cash (BCH) and Bitcoin (BTC).")
    assert set(mentions) == {"BCH", "BTC"}


def test_ordinary_words_are_not_tickers():
    mentions, extraction = _by_symbol(
        "The upgrade is near completion. There is optimism about Bitcoin. "
        "A solid link to the docs. The rain fell."
    )
    assert set(mentions) == {"BTC"}
    assert extraction.unresolved_symbols == ()


def test_contextual_ticker_needs_a_rank_slot_or_marker():
    bare, _ = _by_symbol("NEAR is interesting beside UNI today.")
    assert bare == {}
    marked, _ = _by_symbol("Ranked: 1 NEAR, 2 UNI\nI also hold $DOT and (APT).")
    assert marked["NEAR"].rank == 1
    assert marked["UNI"].rank == 2
    assert marked["DOT"].rank is None
    assert marked["APT"].rank is None


def test_unresolved_rank_slot_is_kept():
    _, extraction = _by_symbol("Ranked: 1 BTC, 2 XYZ")
    assert extraction.unresolved_symbols == ("XYZ",)
    assert [mention.symbol for mention in extraction.mentions] == ["BTC"]


def test_sentiment_lexicon_reads_the_rationale_only():
    text = "1. Dogecoin (DOGE) — bearish after the dump, despite broader momentum elsewhere."
    mentions, _ = _by_symbol(text)
    # "momentum" is in the same rationale, so the clause is mixed.
    assert mentions["DOGE"].sentiment_label == "mixed"
    plain, _ = _by_symbol("1. Dogecoin (DOGE) — bearish after the dump.")
    assert plain["DOGE"].sentiment_label == "negative"
