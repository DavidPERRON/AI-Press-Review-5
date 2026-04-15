#!/usr/bin/env python3
"""One-shot migration: patch the JSON-LD block in already-deployed episode
HTML files so they match the new enriched schema used by the updated
episode-brief-template.html.

Why a migration is needed:
  The template change only affects FUTURE publications. The episode HTML
  files currently live on podcast.aequitus.net were generated with the old
  schema (invalid "PT17:45" duration, no url/image/episodeNumber, no
  BreadcrumbList). Crawlers won't re-parse them until they're refetched AND
  the content changes — so we rewrite them in place now.

What this script does:
  For each docs/episodes/*.html and docs/fr/episodes/*.html, it:
  1. Parses the current <title>, <meta description>, canonical URL,
     existing JSON-LD, and duration.
  2. Converts the duration string (e.g. "PT17:45") to valid ISO 8601
     ("PT17M45S").
  3. Replaces the old single <script type="application/ld+json"> block with
     two new blocks (enriched PodcastEpisode + BreadcrumbList).
  4. Writes the file back. Idempotent — running twice leaves the file
     unchanged (checks for BreadcrumbList presence before patching).

Run once:
  python seo/tools/migrate_episode_schema.py
  # or dry-run to preview:
  python seo/tools/migrate_episode_schema.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger("seo.migrate")

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
SITE_BASE_EN = "https://podcast.aequitus.net"
SITE_BASE_FR = "https://podcast.aequitus.net/fr"
COVER_IMAGE = f"{SITE_BASE_EN}/assets/podcast-cover.png"
FEED_URL = f"{SITE_BASE_EN}/podcast-feed.xml"

# Matches the existing JSON-LD block (from "<!-- JSON-LD: PodcastEpisode -->"
# through the closing </script>). DOTALL so . crosses newlines.
_OLD_JSONLD_RE = re.compile(
    r'<!-- JSON-LD: PodcastEpisode[^-]*-->\s*<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
    re.DOTALL,
)

# Fallback when the comment is missing — match any ld+json block that
# references "PodcastEpisode" (to avoid clobbering BreadcrumbList if this
# script runs twice).
_ANY_EPISODE_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">\s*(\{[^{}]*"@type"\s*:\s*"PodcastEpisode"[\s\S]*?\})\s*</script>',
    re.DOTALL,
)

_DATE_IN_FILENAME = re.compile(r'(\d{4}-\d{2}-\d{2})\.html$')
_DURATION_RE = re.compile(r'"(?:duration|timeRequired)"\s*:\s*"([^"]+)"')
_AUTHOR_NAME_RE = re.compile(r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"')


def _duration_to_iso8601(raw: str) -> str:
    """Convert existing duration strings to valid ISO 8601.

    Accepts: "PT17:45", "PT1:02:30", "PT0M45S" (already valid), "17:45",
    bare seconds as string. Returns "PT0S" on anything unparseable rather
    than raising, since an invalid duration is worse than a 0 duration.
    """
    if not raw:
        return "PT0S"
    s = raw.strip()
    # Already valid ISO 8601?
    if re.match(r'^PT(\d+H)?(\d+M)?(\d+S)?$', s):
        return s
    # Strip leading "PT" if present, we'll re-add after parsing.
    if s.startswith("PT"):
        s = s[2:]
    parts = s.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        logger.warning("Unparseable duration %r — defaulting to PT0S", raw)
        return "PT0S"
    if len(nums) == 3:
        h, m, sec = nums
    elif len(nums) == 2:
        h, m, sec = 0, nums[0], nums[1]
    elif len(nums) == 1:
        h, m, sec = 0, 0, nums[0]
    else:
        return "PT0S"
    out = "PT"
    if h:
        out += f"{h}H"
    out += f"{m}M{sec:02d}S"
    return out


def _extract(pattern: str, haystack: str, group: int = 1) -> str | None:
    m = re.search(pattern, haystack, re.DOTALL)
    return m.group(group) if m else None


def _is_fr(path: Path) -> bool:
    """Detect locale from path: anything under docs/fr/ is French."""
    return "/fr/" in str(path.as_posix())


def _build_new_jsonld(
    *,
    title: str,
    date_iso: str,
    summary: str,
    audio_url: str,
    duration_iso: str,
    episode_number: int,
    author: str,
    locale: str,
) -> str:
    """Build the replacement JSON-LD block (PodcastEpisode + BreadcrumbList)."""
    site_base = SITE_BASE_FR if locale == "fr" else SITE_BASE_EN
    episode_url = f"{site_base}/episodes/{date_iso}.html"

    podcast_episode = {
        "@context": "https://schema.org",
        "@type": "PodcastEpisode",
        "url": episode_url,
        "name": title,
        "episodeNumber": str(episode_number),
        "datePublished": date_iso,
        "description": summary,
        "duration": duration_iso,
        "inLanguage": locale if locale else "en",
        "image": COVER_IMAGE,
        "associatedMedia": {
            "@type": "MediaObject",
            "contentUrl": audio_url,
            "encodingFormat": "audio/mpeg",
        },
        "partOfSeries": {
            "@type": "PodcastSeries",
            "name": "AI Press Review",
            "url": SITE_BASE_EN,
            "webFeed": FEED_URL,
        },
        "author": {"@type": "Person", "name": author or "David Perron"},
    }

    # Localized breadcrumb labels — FR reader sees "Accueil > Épisodes".
    if locale == "fr":
        home_label, episodes_label = "Accueil", "Épisodes"
        home_item = f"{SITE_BASE_FR}/"
    else:
        home_label, episodes_label = "Home", "Episodes"
        home_item = f"{SITE_BASE_EN}/"

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": home_label, "item": home_item},
            {"@type": "ListItem", "position": 2, "name": episodes_label, "item": home_item},
            {"@type": "ListItem", "position": 3, "name": title, "item": episode_url},
        ],
    }

    # 2-space indent matches the surrounding template style.
    ep_json = json.dumps(podcast_episode, indent=2, ensure_ascii=False)
    bc_json = json.dumps(breadcrumb, indent=2, ensure_ascii=False)

    return (
        '<!-- JSON-LD: PodcastEpisode (enriched — url, episodeNumber, image, '
        'inLanguage, valid ISO 8601 duration). -->\n'
        f'  <script type="application/ld+json">\n  {ep_json}\n  </script>\n'
        '\n'
        '  <!-- JSON-LD: BreadcrumbList — renders "Home > Episodes > …" in SERPs. -->\n'
        f'  <script type="application/ld+json">\n  {bc_json}\n  </script>'
    )


def _extract_episode_fields(html: str, path: Path) -> dict[str, str] | None:
    """Pull the fields we need to rebuild JSON-LD from an already-rendered
    episode HTML. Returns None if something critical is missing."""
    # Existing JSON-LD (required — we can't rebuild without the original
    # audio URL and duration).
    m = _OLD_JSONLD_RE.search(html) or _ANY_EPISODE_JSONLD_RE.search(html)
    if not m:
        logger.error("%s: no PodcastEpisode JSON-LD found", path)
        return None
    old_jsonld = m.group(1)

    # Title — prefer <meta property="og:title"> (no site suffix).
    title = (
        _extract(r'<meta property="og:title" content="([^"]+)"', html)
        or _extract(r'<meta name="twitter:title" content="([^"]+)"', html)
        or _extract(r'"name"\s*:\s*"([^"]+)"', old_jsonld)
    )
    summary = (
        _extract(r'<meta name="description" content="([^"]+)"', html)
        or _extract(r'"description"\s*:\s*"([^"]+)"', old_jsonld)
    )
    # Date from filename is the authoritative source (matches URL structure).
    date_m = _DATE_IN_FILENAME.search(path.name)
    date_iso = date_m.group(1) if date_m else _extract(
        r'"datePublished"\s*:\s*"([^"]+)"', old_jsonld
    )
    audio_url = _extract(r'"contentUrl"\s*:\s*"([^"]+)"', old_jsonld)
    duration_raw = _extract(r'"(?:duration|timeRequired)"\s*:\s*"([^"]+)"', old_jsonld) or ""
    author = _extract(r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', old_jsonld) or "David Perron"

    if not all([title, summary, date_iso, audio_url]):
        logger.error("%s: missing required fields (title=%s, date=%s, audio=%s)",
                     path, bool(title), bool(date_iso), bool(audio_url))
        return None

    return {
        "title": title,
        "summary": summary,
        "date_iso": date_iso,
        "audio_url": audio_url,
        "duration_iso": _duration_to_iso8601(duration_raw),
        "author": author,
    }


def _already_patched(html: str) -> bool:
    """Return True if the file already has a BreadcrumbList — idempotency guard."""
    return '"@type": "BreadcrumbList"' in html or '"@type":"BreadcrumbList"' in html


def _discover_episode_files(docs: Path) -> list[Path]:
    """All dated /episodes/YYYY-MM-DD.html files across EN + FR."""
    result: list[Path] = []
    for base in (docs / "episodes", docs / "fr" / "episodes"):
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.html")):
            if _DATE_IN_FILENAME.search(f.name):
                result.append(f)
    return result


def _assign_episode_numbers(paths: list[Path]) -> dict[Path, int]:
    """Per-locale chronological numbering. Oldest dated episode = 1."""
    by_locale: dict[str, list[Path]] = {"en": [], "fr": []}
    for p in paths:
        by_locale["fr" if _is_fr(p) else "en"].append(p)
    numbers: dict[Path, int] = {}
    for paths_loc in by_locale.values():
        for i, p in enumerate(sorted(paths_loc, key=lambda x: x.name), start=1):
            numbers[p] = i
    return numbers


def migrate_file(path: Path, episode_number: int, dry_run: bool) -> bool:
    """Return True if the file was modified (or would be, under --dry-run)."""
    html = path.read_text(encoding="utf-8")
    if _already_patched(html):
        logger.info("%s: already patched — skipping", path.relative_to(REPO_ROOT))
        return False

    fields = _extract_episode_fields(html, path)
    if not fields:
        return False

    locale = "fr" if _is_fr(path) else "en"
    new_block = _build_new_jsonld(
        title=fields["title"],
        date_iso=fields["date_iso"],
        summary=fields["summary"],
        audio_url=fields["audio_url"],
        duration_iso=fields["duration_iso"],
        episode_number=episode_number,
        author=fields["author"],
        locale=locale,
    )

    # Perform the substitution — prefer the commented pattern, fall back
    # to the generic one.
    if _OLD_JSONLD_RE.search(html):
        new_html = _OLD_JSONLD_RE.sub(lambda m: new_block, html, count=1)
    else:
        # Generic fallback: wrap the replacement so it still includes the
        # outer <script> tags (since _ANY_EPISODE_JSONLD_RE matched within
        # those tags, we need to replace the whole <script>…</script>).
        def _wrap(m: re.Match) -> str:
            return new_block
        new_html = re.sub(
            r'<script type="application/ld\+json">\s*\{[^{}]*"@type"\s*:\s*"PodcastEpisode"[\s\S]*?\}\s*</script>',
            _wrap, html, count=1,
        )

    if new_html == html:
        logger.warning("%s: substitution produced no change", path.relative_to(REPO_ROOT))
        return False

    logger.info("%s: patched (ep#%d, locale=%s, duration=%s)",
                path.relative_to(REPO_ROOT), episode_number, locale, fields["duration_iso"])
    if not dry_run:
        path.write_text(new_html, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", type=Path, default=DOCS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    files = _discover_episode_files(args.docs)
    if not files:
        logger.warning("No episode HTML files found under %s", args.docs)
        return 0

    numbers = _assign_episode_numbers(files)
    modified = 0
    for path in files:
        if migrate_file(path, numbers[path], args.dry_run):
            modified += 1

    logger.info("Done — %d file(s) %s (of %d scanned)",
                modified, "would change" if args.dry_run else "modified", len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
