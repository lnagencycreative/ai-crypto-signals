import json
from pathlib import Path

from ai_crypto_signals.collectors.coingecko import collect_coingecko
from ai_crypto_signals.collectors.llm import collect_llm
from ai_crypto_signals.collectors.polymarket import collect_polymarket
from ai_crypto_signals.config import PROMPT


def test_llm_skips_missing_keys_without_calling(tmp_path: Path, monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "XAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    def transport(*args, **kwargs):
        raise AssertionError("transport should not be called without keys")

    paths = collect_llm(tmp_path, transport=transport, collected_at="2026-10-23T05:00:00Z")
    assert len(paths) == 4
    statuses = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        statuses.append((payload["provider"], payload["status"], payload["skip_reason"]))
        assert payload["raw_response"] is None
        assert payload["prompt"] == PROMPT
        assert "api_key" not in payload
    assert statuses == [
        ("openai", "skipped", "missing_api_key"),
        ("anthropic", "skipped", "missing_api_key"),
        ("google", "skipped", "missing_api_key"),
        ("xai", "skipped", "missing_api_key"),
    ]


def test_llm_stores_raw_response_when_a_key_exists(tmp_path: Path, monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    calls = []

    def transport(method, url, headers=None, params=None, json_body=None, timeout=None):
        calls.append({"method": method, "url": url, "json_body": json_body, "headers": headers})
        return 200, {"choices": [{"message": {"content": "1. Bitcoin (BTC) — benchmark"}}]}

    paths = collect_llm(tmp_path, transport=transport, collected_at="2026-10-23T05:00:00Z")
    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.openai.com/v1/chat/completions"
    assert calls[0]["json_body"]["model"] == "gpt-test"
    assert calls[0]["json_body"]["messages"][0]["content"] == PROMPT
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    by_provider = {json.loads(path.read_text())["provider"]: json.loads(path.read_text()) for path in paths}
    assert by_provider["openai"]["status"] == "ok"
    assert by_provider["openai"]["response_text"].startswith("1. Bitcoin")
    assert by_provider["openai"]["raw_response"]["choices"][0]["message"]["content"].startswith("1. Bitcoin")
    # The key is used in the header and must not be copied into the JSON record.
    assert "test-key" not in path_text(paths)


def path_text(paths) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_blank_key_is_treated_as_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    paths = collect_llm(tmp_path, transport=lambda **kwargs: (_ for _ in ()).throw(AssertionError("called")), collected_at="2026-10-23T05:00:00Z")
    openai = json.loads(next(path.read_text() for path in paths if path.name.endswith("_openai.json")))
    assert openai["status"] == "skipped"


def test_coingecko_and_polymarket_writers(tmp_path: Path):
    def transport(method, url, headers=None, params=None, json_body=None, timeout=None):
        if "coingecko" in url:
            coin_id = params["ids"].split(",")[0]
            return 200, [
                {
                    "id": coin_id,
                    "symbol": "btc",
                    "name": "Bitcoin",
                    "current_price": 10,
                    "market_cap": 20,
                    "total_volume": 3,
                    "market_cap_rank": 1,
                }
            ]
        if url.endswith("/tags/slug/crypto"):
            return 200, {"id": "21", "slug": "crypto", "label": "Crypto"}
        if url.endswith("/markets"):
            if params.get("offset") in (0, "0"):
                return 200, [
                    {
                        "id": "m1",
                        "question": "Will Bitcoin reach $85,000?",
                        "outcomes": "[\"Yes\", \"No\"]",
                        "clobTokenIds": "[\"yes-token\", \"no-token\"]",
                        "volume24hr": 5,
                    }
                ]
            return 200, []
        if url.endswith("/midpoints"):
            assert method == "POST"
            assert json_body == [{"token_id": "yes-token"}, {"token_id": "no-token"}]
            return 200, {"yes-token": "0.46", "no-token": "0.54"}
        raise AssertionError(url)

    gecko = collect_coingecko(tmp_path, transport=transport, extra_ids=["bitcoin"])
    payload = json.loads(gecko.read_text())
    assert payload["coins"][0]["id"] == "bitcoin"
    assert "bitcoin" in payload["requested_ids"]
    written = collect_polymarket(tmp_path, transport=transport, max_markets=10)
    gamma = json.loads(written["gamma"].read_text())
    clob = json.loads(written["clob"].read_text())
    assert gamma["tag"]["id"] == "21"
    assert gamma["market_count"] == 1
    assert clob["returned"] == 2
    assert clob["tokens"][0]["mid"] == "0.46"


def test_up_down_markets_are_not_labeled_yes(tmp_path: Path):
    def transport(method, url, headers=None, params=None, json_body=None, timeout=None):
        if url.endswith("/tags/slug/crypto"):
            return 200, {"id": "21", "slug": "crypto", "label": "Crypto"}
        if url.endswith("/markets"):
            return 200, [
                {
                    "id": "up",
                    "question": "Bitcoin Up or Down on October 23?",
                    "outcomes": "[\"Up\", \"Down\"]",
                    "clobTokenIds": "[\"up-token\", \"down-token\"]",
                }
            ]
        if url.endswith("/midpoints"):
            raise AssertionError("Up/Down tokens must not be sent as Yes/No")
        raise AssertionError(url)

    written = collect_polymarket(tmp_path, transport=transport, max_markets=5)
    clob = json.loads(written["clob"].read_text())
    assert clob["requested"] == 0
    assert clob["tokens"] == []
