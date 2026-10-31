"""Command line entry point for collection and table builds."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ai_crypto_signals.collectors.coingecko import collect_coingecko
from ai_crypto_signals.collectors.llm import collect_llm
from ai_crypto_signals.collectors.polymarket import collect_polymarket
from ai_crypto_signals.config import project_root
from ai_crypto_signals.http_util import HttpError
from ai_crypto_signals.parsing.manual import load_manual_responses
from ai_crypto_signals.processing.build import build_processed


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _root_from(args: argparse.Namespace) -> Path:
    if getattr(args, "root", None):
        return Path(args.root).resolve()
    return project_root()


def _collect_markets(root: Path) -> int:
    failures = 0
    try:
        path = collect_coingecko(root)
        print(f"CoinGecko snapshot: {path}")
    except (HttpError, OSError) as exc:
        logging.error("CoinGecko collection failed: %s", exc)
        failures += 1
    try:
        paths = collect_polymarket(root)
        print(f"Polymarket Gamma snapshot: {paths['gamma']}")
        print(f"Polymarket CLOB snapshot: {paths['clob']}")
    except (HttpError, OSError) as exc:
        logging.error("Polymarket collection failed: %s", exc)
        failures += 1
    return 1 if failures else 0


def _print_manual(root: Path) -> int:
    try:
        responses = load_manual_responses(root)
    except ValueError as exc:
        logging.error("%s", exc)
        return 1
    if not responses:
        print("No manual responses found in data/raw/llm_manual/.")
        return 0
    for response in responses:
        ranked = [
            (
                f"{mention.list_type}:{mention.rank}:{mention.symbol}"
                if mention.rank
                else f"{mention.list_type}:{mention.symbol}"
            )
            for mention in response.extraction.mentions
        ]
        print(
            f"{response.collected_at} {response.provider_label} "
            f"status={response.status} mentions={', '.join(ranked) or '-'}"
        )
        if response.extraction.unresolved_symbols:
            print(f"  unresolved: {', '.join(response.extraction.unresolved_symbols)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-crypto-signals",
        description="Collect and tabulate the AI crypto-signals pilot.",
    )
    parser.add_argument(
        "--root",
        help="Project root. Defaults to the directory that contains pyproject.toml.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="Fetch market data and, when keys exist, model answers.")
    collect_sub = collect.add_subparsers(dest="target", required=True)
    collect_sub.add_parser("markets", help="CoinGecko prices and Polymarket odds.")
    llm = collect_sub.add_parser("llm", help="The fixed prompt, for providers with API keys.")
    llm.add_argument(
        "--force",
        action="store_true",
        help="Call a provider again even if an ok answer for today is already stored.",
    )
    everything = collect_sub.add_parser("all", help="Markets, then LLM providers, then rebuild tables.")
    everything.add_argument("--force", action="store_true")

    sub.add_parser("process", help="Rebuild data/processed/*.csv from raw files.")
    sub.add_parser("parse-manual", help="Parse data/raw/llm_manual and print mentions.")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    root = _root_from(args)
    if args.command == "process":
        frames = build_processed(root)
        for name, frame in frames.items():
            print(f"{name}: {len(frame)} rows")
        return 0
    if args.command == "parse-manual":
        return _print_manual(root)
    if args.command == "collect" and args.target == "markets":
        return _collect_markets(root)
    if args.command == "collect" and args.target == "llm":
        paths = collect_llm(root, force=args.force)
        for path in paths:
            print(f"LLM record: {path}")
        if not paths:
            print("No new LLM records. Existing ok answers were kept.")
        return 0
    if args.command == "collect" and args.target == "all":
        status = _collect_markets(root)
        paths = collect_llm(root, force=args.force)
        for path in paths:
            print(f"LLM record: {path}")
        frames = build_processed(root)
        for name, frame in frames.items():
            print(f"{name}: {len(frame)} rows")
        return status
    parser.error(f"Unhandled command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
