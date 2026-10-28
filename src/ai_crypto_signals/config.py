"""Study constants: the fixed prompt, the coin registry, and provider settings.

The watchlist is frozen on purpose. Changing it later would make the price
panel incomparable across days, so new coins belong in the extended registry
(matched and priced when a model actually names them) unless the study design
itself is revised.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# v2 (2026-10-28): keeps the v1 watch-list ask and adds a 7-day expected-return
# rank, scored later against CoinGecko returns and a BTC buy-and-hold baseline.
PROMPT_ID = "weekly_watch_return_v2"
PROMPT = (
    "Please answer both parts.\n\n"
    "1) Which 5 cryptocurrencies would you recommend watching this week? "
    "Rank them 1-5 with a brief reason for each.\n\n"
    "2) Of the coins you would consider, which 5 would make the most money "
    "over the next 7 days (from now until the same time 7 days from now) if "
    "you had to pick? Rank them 1-5, where 1 = highest expected return over "
    "that fixed 7-day window. Give a brief reason for each.\n\n"
    "Label the two lists \"Watch list\" and \"7-day return rank\"."
)

# Pinned on 2026-10-23. Override with the *_MODEL variables. grok-4.7 was the
# chat model named on docs.x.ai that day. The other three are stable API ids;
# a provider that rejects one is logged as an error and the rest still run.
DEFAULT_MODELS = {
    "openai": "gpt-4.1",
    "anthropic": "claude-sonnet-5",
    "google": "gemini-2.5-flash",
    "xai": "grok-4.7",
}

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
POLYMARKET_TAG_SLUG = "crypto"
POLYMARKET_MAX_MARKETS = 200
POLYMARKET_PAGE_SIZE = 100

USER_AGENT = "ai-crypto-signals/0.1 (research pilot; local collection)"


@dataclass(frozen=True)
class Coin:
    """One asset the extractor knows how to recognize.

    ``contextual_tickers`` are uppercase symbols that are also ordinary words
    or very short codes. Those match only as ``$TICKER``, ``(TICKER)``, or in
    a rank slot such as ``1 NEAR``. Bare "near term" does not count.

    ``name_ignorecase`` is off for names that are ordinary English words, so
    "optimism about bitcoin" does not become a mention of Optimism.
    """

    coingecko_id: str
    symbol: str
    name: str
    aliases: tuple[str, ...] = ()
    extra_tickers: tuple[str, ...] = ()
    contextual_tickers: tuple[str, ...] = ()
    in_watchlist: bool = False
    name_ignorecase: bool = True
    match_name: bool = True
    # Forms matched with case intact. Used when the official name is also
    # an English word ("Cosmos", "Canton", "Gram") but a longer alias is safe.
    sensitive_forms: tuple[str, ...] = ()

    def tickers(self) -> tuple[str, ...]:
        seen: list[str] = []
        for ticker in (self.symbol, *self.extra_tickers):
            upper = ticker.upper()
            if upper not in seen:
                seen.append(upper)
        return tuple(seen)

    def name_forms(self) -> tuple[str, ...]:
        if not self.match_name:
            forms = list(self.aliases)
        else:
            forms = [self.name, *self.aliases]
        seen: list[str] = []
        for form in forms:
            if form and form not in seen:
                seen.append(form)
        return tuple(seen)

    def form_ignorecase(self, form: str) -> bool:
        if form in self.sensitive_forms:
            return False
        return self.name_ignorecase


def _c(
    coingecko_id: str,
    symbol: str,
    name: str,
    *,
    aliases: tuple[str, ...] = (),
    extra_tickers: tuple[str, ...] = (),
    contextual_tickers: tuple[str, ...] = (),
    in_watchlist: bool = False,
    name_ignorecase: bool = True,
    match_name: bool = True,
    sensitive_forms: tuple[str, ...] = (),
) -> Coin:
    return Coin(
        coingecko_id=coingecko_id,
        symbol=symbol,
        name=name,
        aliases=aliases,
        extra_tickers=extra_tickers,
        contextual_tickers=tuple(t.upper() for t in contextual_tickers),
        in_watchlist=in_watchlist,
        name_ignorecase=name_ignorecase,
        match_name=match_name,
        sensitive_forms=sensitive_forms,
    )


# Frozen 2026-10-23 from CoinGecko's market-cap ranking. Walk the ranking and
# skip stablecoins and tokenized cash/gold (USDT, USDC, USDS, USDe, DAI, USD1,
# USDG, PYUSD, XAUT), tokenized private credit (Figure Heloc), and centralized
# exchange tokens (WhiteBIT Coin, LEO Token). Keep the first 20 assets that
# remain. Rain and Canton stay in because that rule includes them.
COINS: tuple[Coin, ...] = (
    _c("bitcoin", "BTC", "Bitcoin", in_watchlist=True),
    _c("ethereum", "ETH", "Ethereum", aliases=("Ether",), in_watchlist=True),
    _c("binancecoin", "BNB", "BNB", aliases=("Binance Coin",), in_watchlist=True),
    _c("ripple", "XRP", "XRP", aliases=("Ripple",), in_watchlist=True),
    _c("solana", "SOL", "Solana", in_watchlist=True),
    _c("tron", "TRX", "TRON", aliases=("Tron",), in_watchlist=True),
    _c("zcash", "ZEC", "Zcash", in_watchlist=True),
    _c("hyperliquid", "HYPE", "Hyperliquid", in_watchlist=True),
    _c("dogecoin", "DOGE", "Dogecoin", in_watchlist=True),
    _c("monero", "XMR", "Monero", in_watchlist=True),
    _c("chainlink", "LINK", "Chainlink", in_watchlist=True),
    _c("cardano", "ADA", "Cardano", in_watchlist=True),
    _c(
        "near",
        "NEAR",
        "NEAR Protocol",
        contextual_tickers=("NEAR",),
        in_watchlist=True,
    ),
    _c("stellar", "XLM", "Stellar", aliases=("Stellar Lumens",), in_watchlist=True),
    _c(
        "rain",
        "RAIN",
        "Rain",
        contextual_tickers=("RAIN",),
        match_name=False,
        in_watchlist=True,
    ),
    _c(
        "bitcoin-cash",
        "BCH",
        "Bitcoin Cash",
        in_watchlist=True,
    ),
    _c("litecoin", "LTC", "Litecoin", in_watchlist=True),
    _c(
        "uniswap",
        "UNI",
        "Uniswap",
        contextual_tickers=("UNI",),
        in_watchlist=True,
    ),
    _c(
        "canton-network",
        "CC",
        "Canton",
        aliases=("Canton Network", "Canton Coin"),
        contextual_tickers=("CC",),
        sensitive_forms=("Canton",),
        in_watchlist=True,
    ),
    _c("avalanche-2", "AVAX", "Avalanche", in_watchlist=True),
    # Extended registry: recognized when an answer names them, and priced on
    # the days they are named. They are not part of the frozen daily panel.
    _c("sui", "SUI", "Sui", contextual_tickers=("SUI",)),
    _c("hedera-hashgraph", "HBAR", "Hedera", aliases=("Hedera Hashgraph",)),
    _c(
        "the-open-network",
        "GRAM",
        "Gram",
        aliases=("Toncoin", "The Open Network"),
        extra_tickers=("TON",),
        contextual_tickers=("GRAM", "TON"),
        sensitive_forms=("Gram",),
    ),
    _c("shiba-inu", "SHIB", "Shiba Inu", aliases=("Shiba",)),
    _c("pepe", "PEPE", "Pepe"),
    _c("polkadot", "DOT", "Polkadot", contextual_tickers=("DOT",)),
    _c("aptos", "APT", "Aptos", contextual_tickers=("APT",)),
    _c("bittensor", "TAO", "Bittensor", contextual_tickers=("TAO",)),
    _c(
        "polygon-ecosystem-token",
        "POL",
        "Polygon",
        aliases=("Polygon Ecosystem Token",),
        extra_tickers=("MATIC",),
        contextual_tickers=("POL",),
    ),
    _c("aave", "AAVE", "Aave"),
    _c("arbitrum", "ARB", "Arbitrum"),
    _c(
        "optimism",
        "OP",
        "Optimism",
        contextual_tickers=("OP",),
        name_ignorecase=False,
    ),
    _c("filecoin", "FIL", "Filecoin"),
    _c(
        "cosmos",
        "ATOM",
        "Cosmos Hub",
        aliases=("Cosmos",),
        contextual_tickers=("ATOM",),
        sensitive_forms=("Cosmos",),
    ),
    _c("internet-computer", "ICP", "Internet Computer"),
    _c("injective-protocol", "INJ", "Injective"),
    _c("sei-network", "SEI", "Sei"),
    _c(
        "render-token",
        "RENDER",
        "Render",
        aliases=("Render Network",),
        contextual_tickers=("RENDER",),
        match_name=False,
    ),
    _c("blockstack", "STX", "Stacks", name_ignorecase=False),
)


def coins_by_id() -> dict[str, Coin]:
    return {coin.coingecko_id: coin for coin in COINS}


def watchlist_ids() -> list[str]:
    return [coin.coingecko_id for coin in COINS if coin.in_watchlist]


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    api_key_envs: tuple[str, ...]
    model_env: str
    default_model: str
    aliases: tuple[str, ...]


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        id="openai",
        label="ChatGPT",
        api_key_envs=("OPENAI_API_KEY",),
        model_env="OPENAI_MODEL",
        default_model=DEFAULT_MODELS["openai"],
        aliases=("openai", "chatgpt", "gpt"),
    ),
    Provider(
        id="anthropic",
        label="Claude",
        api_key_envs=("ANTHROPIC_API_KEY",),
        model_env="ANTHROPIC_MODEL",
        default_model=DEFAULT_MODELS["anthropic"],
        aliases=("anthropic", "claude"),
    ),
    Provider(
        id="google",
        label="Gemini",
        api_key_envs=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        model_env="GEMINI_MODEL",
        default_model=DEFAULT_MODELS["google"],
        aliases=("google", "gemini"),
    ),
    Provider(
        id="xai",
        label="Grok",
        api_key_envs=("XAI_API_KEY",),
        model_env="XAI_MODEL",
        default_model=DEFAULT_MODELS["xai"],
        aliases=("xai", "grok"),
    ),
)


def provider_by_alias(value: str) -> Provider:
    key = value.strip().lower()
    for provider in PROVIDERS:
        if key in provider.aliases:
            return provider
    known = ", ".join(sorted(alias for provider in PROVIDERS for alias in provider.aliases))
    raise ValueError(f"Unknown provider {value!r}. Expected one of: {known}.")


def resolve_api_key(provider: Provider) -> tuple[str | None, str]:
    """Return ``(key, env_var)``. A blank variable counts as missing."""
    for env_name in provider.api_key_envs:
        raw = os.environ.get(env_name)
        if raw and raw.strip():
            return raw.strip(), env_name
    return None, provider.api_key_envs[0]


def resolve_model(provider: Provider) -> str:
    raw = os.environ.get(provider.model_env, "")
    if raw and raw.strip():
        return raw.strip()
    return provider.default_model


def project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src").exists():
            return candidate
    return current


def data_paths(root: Path | None = None) -> dict[str, Path]:
    base = project_root(root)
    return {
        "root": base,
        "raw_coingecko": base / "data" / "raw" / "coingecko",
        "raw_polymarket": base / "data" / "raw" / "polymarket",
        "raw_llm": base / "data" / "raw" / "llm",
        "raw_manual": base / "data" / "raw" / "llm_manual",
        "processed": base / "data" / "processed",
    }
