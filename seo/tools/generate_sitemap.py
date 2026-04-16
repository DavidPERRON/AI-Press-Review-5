#!/usr/bin/env python3
"""Standalone sitemap.xml generator for podcast.aequitus.net.

DESIGN CHOICE — why this lives outside src/ai_press_review/:
  The user asked to keep all SEO changes isolated from the existing publish
  pipeline so a bug here can't break the daily cron. This script has ZERO
  dependencies on the ai_press_review package — it just reads files from
  docs/ and writes to seo/output/sitemap.xml. Once validated you can
  either (a) symlink/copy seo/output/sitemap.xml → docs/sitemap.xml in CI,
  or (b) port this logic into src/ai_press_review/publish/sitemap.py. See
  seo/README.md for the integration options.

Usage:
  python seo/tools/generate_sitemap.py                     # writes to seo/output/
  python seo/tools/generate_sitemap.py --write-to-docs     # writes to docs/sitemap.xml
  python seo/tools/generate_sitemap.py --base-url https://podcast.aequitus.net

Output: a sitemap covering every indexable page across both locales (EN + FR):
  index, how-it-works, about, RSS feed, every /episodes/YYYY-MM-DD.html,
  and every /sources/YYYY-MM-DD.html. `latest.html` aliases are excluded
  to avoid duplicate-content signals.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("seo.sitemap")

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_OUTPUT = REPO_ROOT / "seo" / "output" / "sitemap.xml"
DEFAULT_BASE_URL = "https://podcast.aequitus.net"

# Filename pattern for dated episode/source pages (2026-04-15.html).
_ISO_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")

# Static site pages — (relative_path, priority, changefreq).
# Google largely ignores priority/changefreq but Bing and Yandex still use
# them to plan crawl budgets, so keeping them accurate is cheap and useful.
_STATIC_PAGES: tuple[tuple[str, str, str], ...] = (
    ("",                   "1.0", "daily"),    # index (trailing slash URL)
    ("how-it-works.html",  "0.7", "monthly"),
    # NOTE: about.html removed 2026-04-16 — replaced by how-it-works.html
    # which serves the same purpose with cleaner copy.
)


def _iso_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _file_lastmod(path: Path) -> str:
    """Return ISO date (YYYY-MM-DD) for a file's last modification in UTC."""
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return _iso_today()


def _url_entry(loc: str, lastmod: str, changefreq: str, priority: str) -> str:
    # URLs are ASCII and already percent-safe, so no XML escaping is needed.
    return (
        "<url>"
        f"<loc>{loc}</loc>"
        f"<lastmod>{lastmod}</lastmod>"
        f"<changefreq>{changefreq}</changefreq>"
        f"<priority>{priority}</priority>"
        "</url>"
    )


def _collect_locale_urls(
    docs_root: Path,
    locale_subdir: str,
    site_base: str,
) -> list[str]:
    """Build sitemap URL entries for one locale (EN at root, FR under /fr/)."""
    entries: list[str] = []
    loc_dir = docs_root / locale_subdir if locale_subdir else docs_root
    if not loc_dir.is_dir():
        logger.warning("Locale dir missing, skipping: %s", loc_dir)
        return entries

    # 1) Static pages
    for rel_path, priority, changefreq in _STATIC_PAGES:
        page_path = loc_dir / rel_path if rel_path else loc_dir / "index.html"
        if not page_path.exists():
            continue
        url = f"{site_base}/" if not rel_path else f"{site_base}/{rel_path}"
        entries.append(_url_entry(url, _file_lastmod(page_path), changefreq, priority))

    # 2) RSS feed (high-priority, frequent recrawl)
    feed_path = loc_dir / "podcast-feed.xml"
    if feed_path.exists():
        entries.append(_url_entry(
            f"{site_base}/podcast-feed.xml",
            _file_lastmod(feed_path),
            "daily",
            "0.9",
        ))

    # 3) Episode brief pages — use the filename date as lastmod (publication
    #    date is what crawlers care about, not file mtime).
    episodes_dir = loc_dir / "episodes"
    if episodes_dir.is_dir():
        for ep_file in sorted(episodes_dir.glob("*.html")):
            m = _ISO_DATE_RE.match(ep_file.name)
            if not m:
                continue  # skip latest.html aliases and any non-dated files
            entries.append(_url_entry(
                f"{site_base}/episodes/{ep_file.name}",
                m.group(1),
                "monthly",
                "0.8",
            ))

    # 4) Per-episode source manifests — reference material, lower priority.
    sources_dir = loc_dir / "sources"
    if sources_dir.is_dir():
        for src_file in sorted(sources_dir.glob("*.html")):
            m = _ISO_DATE_RE.match(src_file.name)
            if not m:
                continue
            entries.append(_url_entry(
                f"{site_base}/sources/{src_file.name}",
                m.group(1),
                "monthly",
                "0.5",
            ))

    return entries


def build_sitemap(docs_root: Path, base_url: str) -> str:
    """Return the full sitemap.xml body as a string."""
    en_base = base_url.rstrip("/")
    # Defensive: if the caller passed a base URL that already has /fr on it
    # (e.g. because they loaded settings under APR_LOCALE=fr), strip it.
    if en_base.endswith("/fr"):
        en_base = en_base[:-3]
    fr_base = f"{en_base}/fr"

    urls = (
        _collect_locale_urls(docs_root, "", en_base)
        + _collect_locale_urls(docs_root, "fr", fr_base)
    )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(urls)}"
        "</urlset>"
    )
    logger.info("Built sitemap with %d URLs", len(urls))
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Site base URL without trailing slash (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=DOCS_DIR,
        help="Path to the docs/ directory to scan",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write sitemap.xml (default: seo/output/sitemap.xml)",
    )
    parser.add_argument(
        "--write-to-docs",
        action="store_true",
        help="Shortcut: write directly to <docs>/sitemap.xml instead of the seo output",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not args.docs.is_dir():
        logger.error("docs directory not found: %s", args.docs)
        return 1

    body = build_sitemap(args.docs, args.base_url)

    out_path = args.docs / "sitemap.xml" if args.write_to_docs else args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    logger.info("Wrote %s (%d bytes)", out_path, len(body))
    return 0


if __name__ == "__main__":
    sys.exit(main())
