"""Command-line interface."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Config
from .db import Inventory
from .scanner import scan as scan_cmd
from .hasher import hash_all
from .deduplicator import deduplicate
from .extractor import run_extraction
from .classifier import run_classification
from .organizer import plan_moves, export_plan, apply_moves


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_scan(args, cfg, inv):
    return scan_cmd(cfg, inv)


def cmd_hash(args, cfg, inv):
    return hash_all(cfg, inv)


def cmd_dedupe(args, cfg, inv):
    return deduplicate(inv)


def cmd_extract(args, cfg, inv):
    return run_extraction(cfg, inv)


def cmd_classify(args, cfg, inv):
    return run_classification(cfg, inv)


def cmd_plan(args, cfg, inv):
    stats = plan_moves(cfg, inv)
    if args.export:
        n = export_plan(inv, args.export)
        print(f"Exported {n} planned moves to {args.export}")
    return stats


def cmd_apply(args, cfg, inv):
    if args.force:
        cfg.dry_run = False
    return apply_moves(cfg, inv)


def cmd_stats(args, cfg, inv):
    s = inv.stats()
    for k, v in s.items():
        print(f"{k}: {v}")
    return s


def cmd_pipeline(args, cfg, inv):
    """Run scan → hash → dedupe → extract → classify → plan (stops before apply)."""
    scan_cmd(cfg, inv)
    hash_all(cfg, inv)
    deduplicate(inv)
    run_extraction(cfg, inv)
    run_classification(cfg, inv)
    plan_moves(cfg, inv)
    if args.export:
        n = export_plan(inv, args.export)
        print(f"\nExported {n} planned moves to {args.export}")
    print("\nReview the plan. Then run: mac-organizer apply --force")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mac-organizer",
        description="Scan, dedupe, classify (DeepInfra LLM), organize your Mac files.",
    )
    p.add_argument("-c", "--config", default="config.yaml", help="Path to config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="Walk filesystem and populate inventory.")
    sub.add_parser("hash", help="Compute SHA-256 for all scanned files.")
    sub.add_parser("dedupe", help="Group duplicates (mark non-canonical copies).")
    sub.add_parser("extract", help="Extract text and EXIF dates.")
    sub.add_parser("classify", help="Classify documents via DeepInfra LLM.")

    p_plan = sub.add_parser("plan", help="Build move plan (dry-run-able).")
    p_plan.add_argument("--export", help="Export plan to JSONL file.")

    p_apply = sub.add_parser("apply", help="Execute the move plan.")
    p_apply.add_argument("--force", action="store_true",
                         help="Actually move files (overrides dry_run in config).")

    sub.add_parser("stats", help="Show inventory stats.")

    p_full = sub.add_parser("pipeline", help="Run all phases except apply.")
    p_full.add_argument("--export", help="Export plan to JSONL file.")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    cfg = Config.load(args.config)
    inv = Inventory(cfg.db_path)

    handlers = {
        "scan": cmd_scan,
        "hash": cmd_hash,
        "dedupe": cmd_dedupe,
        "extract": cmd_extract,
        "classify": cmd_classify,
        "plan": cmd_plan,
        "apply": cmd_apply,
        "stats": cmd_stats,
        "pipeline": cmd_pipeline,
    }
    handler = handlers[args.command]
    try:
        handler(args, cfg, inv)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        logging.exception("Command failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
