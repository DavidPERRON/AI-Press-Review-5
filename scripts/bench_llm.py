"""LLM-only bench: runs editorial generation against multiple models on the
same sources manifest, so output quality and performance can be compared
without TTS cost.

Collects sources once (or reuses the latest manifest on disk), then loops over
the provided models. For each model, writes a per-model script.txt, a compact
metrics record, and appends to the consolidated bench report.

Results land in `output/bench/<run_date>/`:
- `results.json`   — per-model metrics (machine-readable)
- `results.md`     — per-model summary (human-readable)
- `<model>.txt`    — generated script for manual inspection

Usage:
  python scripts/bench_llm.py --models "google/gemini-2.5-flash,openai/gpt-4o-mini" \
      --date 2026-04-14 --profile daily
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path

from ai_press_review.collect import collect_sources
from ai_press_review.editorial.generator import generate_episode_script
from ai_press_review.settings import DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger('bench_llm')

DEFAULT_SHORTLIST = [
    # OpenRouter-compatible model IDs. Ordered by the 3-agent audit's
    # quality/price consensus. Adjust at call site via --models.
    "google/gemini-2.5-flash",
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-haiku",
    "deepseek/deepseek-chat",
    "mistralai/mistral-medium-3",
]


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _paragraph_count(text: str) -> int:
    return len([p for p in (text or '').split('\n\n') if p.strip()])


def _safe_slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip('-')


def _run_one(manifest: dict, model: str, profile: str, out_dir: Path) -> dict:
    os.environ['LLM_EDITOR_MODEL'] = model
    slug = _safe_slug(model)
    record: dict = {
        'model': model,
        'status': 'pending',
        'elapsed_seconds': None,
        'word_count': None,
        'paragraph_count': None,
        'title': None,
        'highlights_label': None,
        'tomorrow_concept': None,
        'error': None,
    }
    start = time.monotonic()
    try:
        draft = generate_episode_script(manifest, profile=profile)
        elapsed = time.monotonic() - start
        wc = _word_count(draft.script)
        pc = _paragraph_count(draft.script)
        record.update({
            'status': 'ok',
            'elapsed_seconds': round(elapsed, 1),
            'word_count': wc,
            'paragraph_count': pc,
            'title': draft.episode_title,
            'highlights_label': draft.highlights_label,
            'tomorrow_concept': draft.tomorrow_concept,
        })
        (out_dir / f"{slug}.txt").write_text(draft.script, encoding='utf-8')
        (out_dir / f"{slug}.meta.json").write_text(
            json.dumps(
                {
                    'model': model,
                    'title': draft.episode_title,
                    'summary': draft.episode_summary,
                    'opening_news_title': draft.opening_news_title,
                    'highlights_label': draft.highlights_label,
                    'tomorrow_concept': draft.tomorrow_concept,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        logger.info("OK model=%s elapsed=%.1fs words=%d paragraphs=%d",
                    model, elapsed, wc, pc)
    except Exception as exc:
        elapsed = time.monotonic() - start
        record.update({
            'status': 'fail',
            'elapsed_seconds': round(elapsed, 1),
            'error': f"{type(exc).__name__}: {exc}",
        })
        logger.error("FAIL model=%s elapsed=%.1fs error=%s", model, elapsed, exc)
    return record


def _load_manifest(run_date: str, profile: str, reuse: bool) -> dict:
    """Load the latest on-disk manifest or collect fresh."""
    latest = DATA_DIR / 'sources' / 'latest.json'
    if reuse and latest.exists():
        logger.info("Reusing sources manifest from %s (on-disk %d bytes)",
                    latest, latest.stat().st_size)
        manifest = json.loads(latest.read_text(encoding='utf-8'))
        if not manifest.get('sources'):
            logger.warning("On-disk manifest has 0 sources, forcing fresh collect")
        else:
            return manifest
    logger.info("Collecting fresh sources manifest for bench")
    return collect_sources(run_date=run_date, profile=profile)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run editorial generation across multiple LLMs on the same manifest')
    parser.add_argument('--date', default=date.today().isoformat())
    parser.add_argument('--profile', default='daily', help='Editorial profile (daily, weekly_recap)')
    parser.add_argument(
        '--models',
        default=','.join(DEFAULT_SHORTLIST),
        help='Comma-separated list of model IDs to test',
    )
    parser.add_argument(
        '--reuse-manifest',
        action='store_true',
        default=True,
        help='Reuse on-disk latest sources manifest when present (default true)',
    )
    parser.add_argument(
        '--fresh-manifest',
        dest='reuse_manifest',
        action='store_false',
        help='Force a fresh collect instead of reusing latest.json',
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(',') if m.strip()]
    if not models:
        raise SystemExit("At least one model is required via --models")

    out_dir = Path('output') / 'bench' / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    original_editor = os.environ.get('LLM_EDITOR_MODEL')
    original_fallback = os.environ.get('LLM_FALLBACK_MODEL')
    # Disable fallback during bench so each run isolates a single model
    os.environ['LLM_FALLBACK_MODEL'] = ''

    try:
        manifest = _load_manifest(args.date, args.profile, args.reuse_manifest)
        source_count = manifest.get('source_count', len(manifest.get('sources', [])))
        logger.info("Manifest ready: %d sources, profile=%s, date=%s",
                    source_count, args.profile, args.date)

        results = []
        for model in models:
            logger.info("=" * 60)
            logger.info("Benching model: %s", model)
            logger.info("=" * 60)
            record = _run_one(manifest, model, args.profile, out_dir)
            results.append(record)

        summary = {
            'run_date': args.date,
            'profile': args.profile,
            'source_count': source_count,
            'models_tested': models,
            'results': results,
        }
        (out_dir / 'results.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        md_lines = [
            f"# LLM Bench — {args.date} ({args.profile})",
            '',
            f"Source count: {source_count}",
            '',
            '| Model | Status | Elapsed | Words | Paragraphs | Title |',
            '|---|---|---|---|---|---|',
        ]
        for r in results:
            md_lines.append(
                "| {model} | {status} | {elapsed}s | {words} | {paragraphs} | {title} |".format(
                    model=r['model'],
                    status=r['status'],
                    elapsed=r['elapsed_seconds'] if r['elapsed_seconds'] is not None else '-',
                    words=r['word_count'] if r['word_count'] is not None else '-',
                    paragraphs=r['paragraph_count'] if r['paragraph_count'] is not None else '-',
                    title=(r['title'] or r['error'] or '')[:60].replace('|', '/'),
                )
            )
        md_lines.append('')
        md_lines.append('## Per-model detail')
        md_lines.append('')
        for r in results:
            md_lines.append(f"### {r['model']}")
            md_lines.append('')
            if r['status'] == 'ok':
                md_lines.append(f"- Title: {r['title']}")
                md_lines.append(f"- Highlights label: {r['highlights_label']}")
                md_lines.append(f"- Tomorrow concept: {r['tomorrow_concept']}")
                md_lines.append(f"- Elapsed: {r['elapsed_seconds']}s, words: {r['word_count']}, paragraphs: {r['paragraph_count']}")
            else:
                md_lines.append(f"- Error: `{r['error']}`")
                md_lines.append(f"- Elapsed before failure: {r['elapsed_seconds']}s")
            md_lines.append('')
        (out_dir / 'results.md').write_text('\n'.join(md_lines), encoding='utf-8')

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        # Restore original env so subsequent pipeline steps aren't polluted
        if original_editor is not None:
            os.environ['LLM_EDITOR_MODEL'] = original_editor
        else:
            os.environ.pop('LLM_EDITOR_MODEL', None)
        if original_fallback is not None:
            os.environ['LLM_FALLBACK_MODEL'] = original_fallback
        else:
            os.environ.pop('LLM_FALLBACK_MODEL', None)


if __name__ == '__main__':
    main()
