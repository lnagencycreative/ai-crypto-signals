"""Read answers that were copied out of a chat app.

Markdown files use YAML front matter. JSON files use the same field names
and put the answer in ``text``. Files in ``examples/``, ``README.md``, and
names that start with ``_`` are templates, not observations.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ai_crypto_signals.config import PROMPT_ID, data_paths, provider_by_alias
from ai_crypto_signals.parsing.mentions import Extraction, extract_answer_mentions

_FRONT_MATTER = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class ManualResponse:
    response_id: str
    path: str
    provider: str
    provider_label: str
    model: str
    status: str
    skip_reason: str
    collected_at: str
    time_precision: str
    time_note: str
    source: str
    prompt_id: str
    transcript_fidelity: str
    session_note: str
    text: str
    extraction: Extraction


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"collected_at is not an ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"collected_at needs a timezone: {value!r}")
    return parsed


def iter_manual_paths(root: Path | None = None) -> list[Path]:
    base = data_paths(root)["raw_manual"]
    if not base.exists():
        return []
    paths: list[Path] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(base)
        if "examples" in relative.parts:
            continue
        if path.name.lower() == "readme.md" or path.name.startswith("_"):
            continue
        if path.suffix.lower() not in {".md", ".markdown", ".json"}:
            continue
        paths.append(path)
    return paths


def _extraction_for(status: str, text: str) -> Extraction:
    if status != "ok":
        return extract_answer_mentions("")
    return extract_answer_mentions(text)


def parse_manual_text(text: str, *, response_id: str, path: str = "") -> ManualResponse:
    if text.lstrip().startswith("{"):
        meta = json.loads(text)
        if not isinstance(meta, dict):
            raise ValueError(f"{path or response_id} JSON must be an object.")
        body = _as_text(meta.get("text") or meta.get("body"))
    else:
        match = _FRONT_MATTER.match(text)
        if match is None:
            raise ValueError(
                f"{path or response_id} needs YAML front matter between --- lines, "
                "or a JSON object."
            )
        loaded = yaml.safe_load(match.group(1)) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{path or response_id} front matter must be a mapping.")
        meta = loaded
        body = match.group(2).strip()

    provider_raw = _as_text(meta.get("provider"))
    if not provider_raw:
        raise ValueError(f"{path or response_id} is missing provider.")
    provider = provider_by_alias(provider_raw)
    collected_at = _as_text(meta.get("collected_at"))
    if not collected_at:
        raise ValueError(f"{path or response_id} is missing collected_at.")
    parse_timestamp(collected_at)

    status = _as_text(meta.get("status")).lower() or "ok"
    if status not in {"ok", "skipped", "error"}:
        raise ValueError(f"{path or response_id} has unsupported status {status!r}.")
    skip_reason = _as_text(meta.get("skip_reason"))
    if status == "skipped" and not skip_reason:
        raise ValueError(f"{path or response_id} is skipped and needs skip_reason.")

    return ManualResponse(
        response_id=response_id,
        path=path,
        provider=provider.id,
        provider_label=_as_text(meta.get("provider_label")) or provider.label,
        model=_as_text(meta.get("model")),
        status=status,
        skip_reason=skip_reason,
        collected_at=collected_at,
        time_precision=_as_text(meta.get("time_precision")) or "timestamp",
        time_note=_as_text(meta.get("time_note")),
        source=_as_text(meta.get("source")) or "manual_chat",
        prompt_id=_as_text(meta.get("prompt_id")) or PROMPT_ID,
        transcript_fidelity=_as_text(meta.get("transcript_fidelity")) or "unspecified",
        session_note=_as_text(meta.get("session_note")),
        text=body,
        extraction=_extraction_for(status, body),
    )


def load_manual_responses(root: Path | None = None) -> list[ManualResponse]:
    base = data_paths(root)["raw_manual"]
    responses: list[ManualResponse] = []
    for path in iter_manual_paths(root):
        relative = path.relative_to(base)
        response_id = "manual:" + relative.with_suffix("").as_posix()
        responses.append(
            parse_manual_text(
                path.read_text(encoding="utf-8"),
                response_id=response_id,
                path=relative.as_posix(),
            )
        )
    return responses


def mentioned_coingecko_ids(root: Path | None = None) -> list[str]:
    """Ids named in manual logs. Used so the price snapshot covers them."""
    ids: list[str] = []
    for response in load_manual_responses(root):
        for mention in response.extraction.mentions:
            if mention.coingecko_id not in ids:
                ids.append(mention.coingecko_id)
    return ids
