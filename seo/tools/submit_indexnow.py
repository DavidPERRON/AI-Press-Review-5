#!/usr/bin/env python3
"""Ping IndexNow (Bing, Yandex, Seznam, Naver) with freshly-published URLs.

IndexNow is a free push-based indexing protocol — you notify the engine the
moment a URL changes, instead of waiting for the crawler to come around. A
single ping to api.indexnow.org fans out to all participating engines.

Google is NOT an IndexNow participant — it still relies on sitemap discovery
and its own crawler. For Google, use the sitemap + Search Console (see
seo/SETUP.md). IndexNow covers roughly Bing (plus the engines that federate
from Bing: DuckDuckGo, Ecosia, Brave, Yahoo) and Yandex.

Prerequisites:
  1. The IndexNow key file (seo/static/<KEY>.txt) must be copied to
     docs/<KEY>.txt BEFORE the first submission. IndexNow validates ownership
     by fetching https://podcast.aequitus.net/<KEY>.txt and checking it
     contains the same KEY.
  2. The URLs you submit must resolve (200 OK) — IndexNow ignores 404s.

Usage:
  # Submit all episode + index URLs from the live docs/ tree:
  python seo/tools/submit_indexnow.py --all

  # Submit a specific list:
  python seo/tools/submit_indexnow.py https://podcast.aequitus.net/episodes/2026-04-15.html

  # Dry run (print what would be submitted, don't actually POST):
  python seo/tools/submit_indexnow.py --all --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.request
from pathlib import Path

logger = logging.getLogger("seo.indexnow")

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
KEY_FILE = REPO_ROOT / "seo" / "static" / "ecc8dffbb048713bbab441ddaee8958e.txt"
HOST = "podcast.aequitus.net"
BASE_URL = f"https://{HOST}"
# api.indexnow.org is the neutral endpoint that fans out to all participating
# engines — simpler than calling bing.com/indexnow and yandex.com/indexnow
# separately (and both are accepted by the protocol spec).
ENDPOINT = "https://api.indexnow.org/indexnow"
# IndexNow's per-request limit is 10,000 URLs; we set a conservative chunk
# size so a single request stays well under their rate-limit thresholds.
CHUNK_SIZE = 500

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.html$")


def _read_key() -> str:
    if not KEY_FILE.exists():
        raise FileNotFoundError(
            f"IndexNow key file not found at {KEY_FILE}. "
            "Regenerate one with: python -c 'import secrets; print(secrets.token_hex(16))'"
        )
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    # Filename must equal the key (IndexNow verifies by fetching
    # https://<host>/<KEY>.txt and matching contents).
    if KEY_FILE.stem != key:
        raise ValueError(
            f"IndexNow key mismatch: filename is '{KEY_FILE.stem}' but file "
            f"contents are '{key}'. They must be identical."
        )
    return key


def discover_urls(docs_root: Path) -> list[str]:
    """Walk docs/ and return every URL worth notifying IndexNow about."""
    urls: list[str] = [f"{BASE_URL}/", f"{BASE_URL}/fr/"]

    for locale_prefix, loc_dir in (
        ("", docs_root),
        ("/fr", docs_root / "fr"),
    ):
        if not loc_dir.is_dir():
            continue
        # Episode briefs
        ep_dir = loc_dir / "episodes"
        if ep_dir.is_dir():
            for f in sorted(ep_dir.glob("*.html")):
                if _ISO_DATE_RE.match(f.name):
                    urls.append(f"{BASE_URL}{locale_prefix}/episodes/{f.name}")
        # how-it-works + about
        for page in ("how-it-works.html", "about.html"):
            if (loc_dir / page).exists():
                urls.append(f"{BASE_URL}{locale_prefix}/{page}")

    return urls


def submit(urls: list[str], key: str, dry_run: bool = False) -> int:
    """POST the URL list to IndexNow. Returns HTTP status (or 0 on dry run)."""
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"{BASE_URL}/{key}.txt",
        "urlList": urls,
    }
    body = json.dumps(payload).encode("utf-8")

    logger.info("Submitting %d URLs to %s", len(urls), ENDPOINT)
    if dry_run:
        logger.info("DRY RUN — payload:\n%s", json.dumps(payload, indent=2))
        return 0

    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "ai-press-review-indexnow/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            logger.info("IndexNow responded: %d %s", status, resp.reason)
            return status
    except urllib.error.HTTPError as exc:
        # IndexNow returns 422 for "key not verified" — the most common
        # first-time failure (KEY.txt not yet deployed to docs/ root).
        logger.error("IndexNow HTTP %d: %s", exc.code, exc.read().decode("utf-8", "replace"))
        return exc.code


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "urls",
        nargs="*",
        help="Specific URLs to submit. If omitted, use --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Discover URLs from docs/ and submit all of them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload instead of POSTing.",
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=DOCS_DIR,
        help="docs/ path for --all discovery",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not args.all and not args.urls:
        parser.error("Provide URLs explicitly, or use --all to discover them.")
    if args.all and args.urls:
        parser.error("Choose either --all OR explicit URLs, not both.")

    try:
        key = _read_key()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2

    urls = discover_urls(args.docs) if args.all else list(args.urls)
    if not urls:
        logger.warning("No URLs to submit.")
        return 0

    # IndexNow's docs say ≤10,000 URLs per request and suggest keeping
    # requests small to avoid rate limits, so we chunk defensively.
    failed = 0
    for batch in _chunk(urls, CHUNK_SIZE):
        status = submit(batch, key, dry_run=args.dry_run)
        # 200 OK and 202 Accepted both mean "received"; anything else is an error.
        if not args.dry_run and status not in (200, 202):
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
