"""Ask the four study providers the fixed prompt.

A missing or blank API key skips that provider and writes a JSON record of
the skip. No key is stored. Raw response bodies are stored only after a call.
Temperature is left at each provider's default, and no browsing tool is
turned on: an API answer is a different instrument from the consumer chat app.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_crypto_signals.config import PROMPT, PROMPT_ID, PROVIDERS, Provider, data_paths, resolve_api_key, resolve_model
from ai_crypto_signals.http_util import Transport, request_json
from ai_crypto_signals.util import read_json, stamp, write_json

logger = logging.getLogger(__name__)

_ANTHROPIC_VERSION = "2023-06-01"
_MAX_OUTPUT_TOKENS = 2000


def _chat_text(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str) and part.strip():
                parts.append(part.strip())
            elif isinstance(part, dict) and str(part.get("text") or "").strip():
                parts.append(str(part["text"]).strip())
        joined = "\n".join(parts).strip()
        return joined or None
    return None


def _anthropic_text(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    blocks = body.get("content")
    if isinstance(blocks, str) and blocks.strip():
        return blocks.strip()
    if not isinstance(blocks, list):
        return None
    parts = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") not in (None, "text"):
            continue
        text = str(block.get("text") or "").strip()
        if text:
            parts.append(text)
    joined = "\n".join(parts).strip()
    return joined or None


def _gemini_text(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return None
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list):
        return None
    texts = [str(part.get("text") or "").strip() for part in parts if isinstance(part, dict)]
    joined = "\n".join(piece for piece in texts if piece).strip()
    return joined or None


def _error_message(body: Any, status: int) -> str:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str):
            return error
        if body.get("message"):
            return str(body["message"])
    return f"HTTP {status}"


def _request_for(provider: Provider, model: str, api_key: str) -> tuple[str, dict[str, str], dict[str, Any], Any]:
    """Return url, headers, extra request_json kwargs, and a text extractor."""
    if provider.id in {"openai", "xai"}:
        base = "https://api.openai.com" if provider.id == "openai" else "https://api.x.ai"
        return (
            f"{base}/v1/chat/completions",
            {"Authorization": f"Bearer {api_key}"},
            {
                "json_body": {
                    "model": model,
                    "messages": [{"role": "user", "content": PROMPT}],
                }
            },
            _chat_text,
        )
    if provider.id == "anthropic":
        return (
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
            },
            {
                "json_body": {
                    "model": model,
                    "max_tokens": _MAX_OUTPUT_TOKENS,
                    "messages": [{"role": "user", "content": PROMPT}],
                }
            },
            _anthropic_text,
        )
    if provider.id == "google":
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        return (
            url,
            {"x-goog-api-key": api_key},
            {
                "json_body": {
                    "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
                }
            },
            _gemini_text,
        )
    raise ValueError(f"No request builder for {provider.id}.")


def _ok_already_today(directory: Path, provider_id: str, day: str) -> bool:
    if not directory.exists():
        return False
    for path in directory.glob(f"*_{provider_id}.json"):
        try:
            payload = read_json(path)
        except (OSError, ValueError):
            continue
        if payload.get("status") == "ok" and str(payload.get("collected_at") or "").startswith(day):
            return True
    return False


def collect_llm(
    root: Path | None = None,
    *,
    transport: Transport | None = None,
    force: bool = False,
    collected_at: str | None = None,
) -> list[Path]:
    """Collect every configured provider. Missing keys are skipped, not fatal."""
    paths = data_paths(root)
    iso, compact = stamp()
    if collected_at:
        iso = collected_at
    day = iso[:10]
    written: list[Path] = []
    for provider in PROVIDERS:
        api_key, env_name = resolve_api_key(provider)
        model = resolve_model(provider)
        base = {
            "schema_version": 1,
            "source": "llm_api",
            "provider": provider.id,
            "provider_label": provider.label,
            "model": model,
            "prompt_id": PROMPT_ID,
            "prompt": PROMPT,
            "collected_at": iso,
            "env_var": env_name,
            "browsing": False,
        }
        if api_key is None:
            payload = {
                **base,
                "status": "skipped",
                "skip_reason": "missing_api_key",
                "http_status": None,
                "response_text": None,
                "raw_response": None,
                "error": None,
            }
            logger.info("Skipping %s: %s is not set.", provider.label, env_name)
        elif not force and _ok_already_today(paths["raw_llm"], provider.id, day):
            logger.info("Skipping %s: an ok response is already stored for %s.", provider.label, day)
            continue
        else:
            url, headers, extra, extract_text = _request_for(provider, model, api_key)
            status, body = request_json(
                "POST",
                url,
                headers=headers,
                timeout=90,
                retries=0,
                transport=transport,
                **extra,
            )
            text = extract_text(body) if status == 200 else None
            if status == 200 and text:
                record_status = "ok"
                error = None
            else:
                record_status = "error"
                error = None if status == 200 else _error_message(body, status)
                if status == 200 and not text:
                    error = "Response did not include text."
            payload = {
                **base,
                "status": record_status,
                "skip_reason": None,
                "http_status": status,
                "endpoint": url,
                "response_text": text,
                "raw_response": body,
                "error": error,
            }
            logger.info("%s collection status: %s", provider.label, record_status)

        # One second of uniqueness if several files share a stamp. The provider
        # id keeps filenames distinct; the stamp is the run time.
        path = paths["raw_llm"] / f"{compact}_{provider.id}.json"
        if collected_at:
            safe = datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")
            path = paths["raw_llm"] / f"{safe}_{provider.id}.json"
        write_json(path, payload)
        written.append(path)
    return written
