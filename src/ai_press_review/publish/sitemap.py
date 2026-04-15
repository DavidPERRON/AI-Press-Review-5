from __future__ import annotations

"""Site-wide sitemap.xml generator.

Called from `publish_episode` after feed + index + episode brief are written,
so newly-published episodes appear in the sitemap on the same CI run.

The sitemap is SITE-WIDE (both locales) and lives at `docs/sitemap.xml` —
not under `docs/<locale>/`. Even when publish runs under APR_LOCALE=fr, the
writer targets the EN root so there's only one sitemap for all of
podcast.aequitus.net, which is what robots.txt advertises.

URLs are derived from the filesystem rather than episode history so the
sitemap self-heals if history JSON drifts, and older episodes visible in
`docs/episodes/` stay indexable even past retention.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from ..settings import DOCS_DIR, load_settings

logger = logging.getLogger(__name__)

_ISO_DATE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})\.html$')

# Static site pages keyed by locale prefix. Google largely ignores
# priority/changefreq but Bing and Yandex still use them for crawl
# budgeting, so keeping them accurate is cheap.
_STATIC_PAGES: tuple[tuple[str, str, str], ...] = (
    ('',                  '1.0', 'daily'),    # index (trailing-slash URL)
    ('how-it-works.html', '0.7', 'monthly'),
    ('about.html',        '0.5', 'yearly'),
)


def _iso_today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _file_lastmod(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')
    except OSError:
        return _iso_today()


def _url_entry(loc: str, lastmod: str, changefreq: str, priority: str) -> str:
    # All our URLs are ASCII / percent-safe — no XML escaping needed.
    return (
        '<url>'
        f'<loc>{loc}</loc>'
        f'<lastmod>{lastmod}</lastmod>'
        f'<changefreq>{changefreq}</changefreq>'
        f'<priority>{priority}</priority>'
        '</url>'
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

    # Static pages
    for rel_path, priority, changefreq in _STATIC_PAGES:
        page_path = loc_dir / rel_path if rel_path else loc_dir / 'index.html'
        if not page_path.exists():
            continue
        url = f'{site_base}/' if not rel_path else f'{site_base}/{rel_path}'
        entries.append(_url_entry(url, _file_lastmod(page_path), changefreq, priority))

    # RSS feed — aggressive recrawl hint.
    feed_path = loc_dir / 'podcast-feed.xml'
    if feed_path.exists():
        entries.append(_url_entry(
            f'{site_base}/podcast-feed.xml',
            _file_lastmod(feed_path), 'daily', '0.9',
        ))

    # Episode briefs — use date-from-filename as lastmod (publication date is
    # what crawlers should record, not file mtime which resets on every
    # redeploy).
    episodes_dir = loc_dir / 'episodes'
    if episodes_dir.is_dir():
        for ep_file in sorted(episodes_dir.glob('*.html')):
            m = _ISO_DATE_RE.match(ep_file.name)
            if not m:
                continue  # skip latest.html aliases and non-dated files
            entries.append(_url_entry(
                f'{site_base}/episodes/{ep_file.name}',
                m.group(1), 'monthly', '0.8',
            ))

    # Per-episode source manifests — lower priority, they're reference pages.
    # Skip `latest.html` to avoid duplicate-content signals with the dated
    # copy it mirrors.
    sources_dir = loc_dir / 'sources'
    if sources_dir.is_dir():
        for src_file in sorted(sources_dir.glob('*.html')):
            m = _ISO_DATE_RE.match(src_file.name)
            if not m:
                continue
            entries.append(_url_entry(
                f'{site_base}/sources/{src_file.name}',
                m.group(1), 'monthly', '0.5',
            ))

    return entries


def write_sitemap(docs_root: Path | None = None) -> Path:
    """Generate and write <docs_root>/sitemap.xml covering all locales.

    Safe to call multiple times in a single run (idempotent — always
    overwrites). Returns the output path.
    """
    docs_root = docs_root or DOCS_DIR
    settings = load_settings()

    # Derive the EN root URL from settings — strip /fr if we happen to be
    # running under APR_LOCALE=fr. The sitemap always lives at the EN root.
    en_base = settings.site_base_url.rstrip('/')
    if en_base.endswith('/fr'):
        en_base = en_base[:-3]
    fr_base = f'{en_base}/fr'

    urls = (
        _collect_locale_urls(docs_root, '', en_base)
        + _collect_locale_urls(docs_root, 'fr', fr_base)
    )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(urls)}"
        '</urlset>'
    )
    out_path = docs_root / 'sitemap.xml'
    out_path.write_text(body, encoding='utf-8')
    logger.info("Sitemap written: %s (%d URLs)", out_path, len(urls))
    return out_path
