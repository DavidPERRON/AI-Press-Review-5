from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import logging

from ..models import PublishedEpisode
from ..settings import DATA_DIR, DOCS_DIR, load_settings
from ..state import load_episode_history, save_episode_history
from ..storage.r2 import delete_key
from ..utils import read_json, utcnow
from .episode_brief import generate_episode_brief
from .sitemap import write_sitemap

logger = logging.getLogger(__name__)

# Month names for French date formatting ("15 avril 2026" style).
# strftime('%B') would honor LC_TIME but the runner locale isn't guaranteed,
# so we inline the table rather than depend on system locale data.
_MONTHS_FR = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def _build_brief_data(episode: PublishedEpisode, source_titles: list[str], episode_number: int) -> dict:
    """Build the data dict expected by generate_episode_brief."""
    pub_dt = datetime.fromisoformat(episode.published_at)
    dur = episode.duration_seconds or 0
    dur_str = f"{dur // 60}:{dur % 60:02d}"
    # ISO 8601 duration for schema.org PodcastEpisode.duration. The previous
    # schema used "PT{dur_str}" which emits "PT17:45" — not valid ISO 8601
    # and rejected by Google's Rich Results validator.
    dur_iso = f"PT{dur // 60}M{dur % 60:02d}S" if dur else "PT0S"

    # Build a simplified source manifest from source titles
    domain_counts: dict[str, int] = {}
    for title in source_titles:
        # Use a generic label since we don't have domains here
        domain_counts[title[:40]] = domain_counts.get(title[:40], 0) + 1

    settings = load_settings()
    return {
        'title': episode.title,
        'date_iso': episode.date,
        'date_human': pub_dt.strftime('%B %d, %Y'),
        'number': episode_number,
        'duration': dur_str,
        'duration_iso': dur_iso,
        'audio_url': episode.audio_url,
        'spotify_url': '',
        'apple_url': '',
        'summary': episode.summary,
        'prev_url': '',
        'prev_title': '',
        'next_url': '',
        'next_title': '',
        'key_claims': [],
    }


def publish_episode(episode: PublishedEpisode, source_fingerprints: list[str], source_titles: list[str]) -> None:
    history = load_episode_history()
    episodes = history.get('episodes', [])
    payload = episode.to_dict()
    payload['source_fingerprints'] = source_fingerprints
    payload['source_titles'] = source_titles

    # Generate episode brief HTML page
    episode_number = len(episodes) + 1
    brief_data = _build_brief_data(episode, source_titles, episode_number)
    try:
        brief_rel_path = generate_episode_brief(brief_data)
        settings = load_settings()
        payload['brief_url'] = f"{settings.site_base_url}/{brief_rel_path}"
        logger.info("Episode brief generated: %s", brief_rel_path)
    except Exception as exc:
        logger.warning("Failed to generate episode brief: %s", exc)
        payload['brief_url'] = ''

    episodes.insert(0, payload)

    settings = load_settings()
    cutoff = utcnow() - timedelta(days=settings.retention_days)

    kept = []
    for item in episodes:
        published_at = datetime.fromisoformat(item['published_at'])
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if published_at >= cutoff:
            kept.append(item)
        else:
            try:
                key = item['audio_url'].replace(settings.public_audio_base_url.rstrip('/') + '/', '')
                delete_key(key)
            except Exception:
                pass

    history['episodes'] = kept
    save_episode_history(history)
    _write_feed(kept)
    _write_index(kept)
    # Sitemap is site-wide (EN + FR) and scans the filesystem, so it runs
    # AFTER _write_feed/_write_index so the freshly-published episode is
    # visible. Failures here must not block publishing — sitemap staleness
    # only delays crawler discovery by a day.
    try:
        write_sitemap()
    except Exception as exc:
        logger.warning("Failed to write sitemap: %s", exc)


def _secondary_category_xml(settings) -> str:
    if not settings.category_secondary:
        return ''
    if settings.category_secondary.strip().lower() == 'artificial intelligence':
        return '<itunes:category text="Technology"><itunes:category text="Artificial Intelligence" /></itunes:category>'
    return f'<itunes:category text="{escape(settings.category_secondary)}" />'


def _write_feed(episodes: list[dict]) -> None:
    settings = load_settings()
    items = []
    latest_pub_dt: datetime | None = None
    for ep in episodes:
        ep_dt = datetime.fromisoformat(ep['published_at'])
        if ep_dt.tzinfo is None:
            ep_dt = ep_dt.replace(tzinfo=timezone.utc)
        if latest_pub_dt is None or ep_dt > latest_pub_dt:
            latest_pub_dt = ep_dt
        pub_date = format_datetime(ep_dt)
        duration_secs = ep.get('duration_seconds', 0)
        duration_str = f"{duration_secs // 3600}:{(duration_secs % 3600) // 60:02d}:{duration_secs % 60:02d}"
        # Fallback chain for <link>: brief page -> site homepage. Never emit an
        # empty <link></link> — some podcast aggregators (Apple, Spotify)
        # silently drop items with a missing canonical URL.
        item_link = ep.get('brief_url') or settings.site_base_url
        content_encoded = f"<p>{escape(ep['summary'])}</p>"
        items.append(
            f"<item><title>{escape(ep['title'])}</title>"
            f"<description>{escape(ep['summary'])}</description>"
            f"<content:encoded><![CDATA[{content_encoded}]]></content:encoded>"
            f"<guid isPermaLink=\"false\">{escape(ep.get('date', '') + '-' + ep.get('slug', ''))}</guid>"
            f"<pubDate>{pub_date}</pubDate>"
            f'<enclosure url="{escape(ep["audio_url"])}" length="{ep["audio_bytes"]}" type="audio/mpeg" />'
            f"<itunes:summary>{escape(ep['summary'])}</itunes:summary>"
            f"<itunes:duration>{escape(duration_str)}</itunes:duration>"
            f"<link>{escape(item_link)}</link></item>"
        )

    # Freshness signals required by Apple Podcasts / YouTube Music to detect NEW episodes
    # after initial feed import. Without these tags, aggregators fall back on HTTP cache
    # headers and the default refresh interval (often 24h), so newly published items
    # may not appear for hours or days.
    # - lastBuildDate: when the FEED was last rebuilt (now)
    # - channel pubDate: publication time of the MOST RECENT item
    # - ttl: client-side refresh hint in minutes (60 = 1h)
    # - itunes:type: episodic (standard for serial podcasts — dated releases)
    now_dt = utcnow()
    last_build_date = format_datetime(now_dt)
    channel_pub_date = format_datetime(latest_pub_dt) if latest_pub_dt else last_build_date

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<?xml-stylesheet type="text/xsl" href="/feed.xsl"?>\n'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">'
        '<channel>'
        f"<title>{escape(settings.podcast_title)}</title>"
        f"<link>{escape(settings.site_base_url)}</link>"
        f'<atom:link href="{escape(settings.rss_feed_url)}" rel="self" type="application/rss+xml" />'
        f"<language>{escape(settings.podcast_language)}</language>"
        f"<lastBuildDate>{last_build_date}</lastBuildDate>"
        f"<pubDate>{channel_pub_date}</pubDate>"
        "<ttl>60</ttl>"
        "<itunes:type>episodic</itunes:type>"
        f"<itunes:author>{escape(settings.podcast_author)}</itunes:author>"
        f"<itunes:subtitle>{escape(settings.podcast_subtitle)}</itunes:subtitle>"
        f"<itunes:summary>{escape(settings.podcast_description_short)}</itunes:summary>"
        f"<description>{escape(settings.podcast_description_long or settings.podcast_description_short)}</description>"
        f"<itunes:explicit>{'true' if settings.explicit else 'false'}</itunes:explicit>"
        '<itunes:owner>'
        f"<itunes:name>{escape(settings.podcast_author)}</itunes:name>"
        f"<itunes:email>{escape(settings.podcast_email)}</itunes:email>"
        '</itunes:owner>'
        f'<itunes:image href="{escape(settings.site_base_url)}/{escape(settings.cover_image_path)}" />'
        f'<itunes:category text="{escape(settings.category_primary)}" />'
        f'{_secondary_category_xml(settings)}'
        f"{''.join(items)}"
        '</channel></rss>'
    )
    # Write to locale-specific docs dir (docs/ for EN, docs/fr/ for FR).
    out_dir = settings.docs_output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'podcast-feed.xml').write_text(xml, encoding='utf-8')


_TEMPLATES_DIR = Path(__file__).parent / 'templates'
# Legacy constant kept so callers/tests that imported it still resolve (it points
# at the EN template, which is the default when APR_LOCALE is unset).
_INDEX_TEMPLATE_PATH = _TEMPLATES_DIR / 'index-template.html'


def _index_template_path() -> Path:
    """Pick index template per locale: EN default, `index-template-<loc>.html` else."""
    locale = os.getenv('APR_LOCALE', '').strip().lower()
    if locale:
        return _TEMPLATES_DIR / f'index-template-{locale}.html'
    return _INDEX_TEMPLATE_PATH


def _format_card_date(pub_dt: datetime, locale: str) -> str:
    """Human-readable date for an episode card. FR uses French months; EN uses %B %d, %Y."""
    if locale == 'fr':
        return f"{pub_dt.day} {_MONTHS_FR[pub_dt.month - 1]} {pub_dt.year}"
    return pub_dt.strftime('%B %d, %Y')


def _write_index(episodes: list[dict]) -> None:
    settings = load_settings()
    template_path = _index_template_path()
    # Fall back to EN template if the locale-specific one is missing — protects
    # against partial deploys where only one template was shipped.
    if not template_path.exists():
        logger.warning("Index template %s missing — falling back to EN", template_path.name)
        template_path = _INDEX_TEMPLATE_PATH
    template = template_path.read_text(encoding='utf-8')

    locale = os.getenv('APR_LOCALE', '').strip().lower()
    listen_label = 'Écouter' if locale == 'fr' else 'Listen'
    brief_label = 'Lire le brief' if locale == 'fr' else 'Read brief'
    sources_label = 'Sources' if locale == 'fr' else 'Sources'
    # Locale-aware sources directory: /sources/ for EN, /fr/sources/ for FR.
    sources_base = '/fr/sources/' if locale == 'fr' else '/sources/'

    cards = []
    for ep in episodes:
        pub_dt = datetime.fromisoformat(ep['published_at'])
        date_str = _format_card_date(pub_dt, locale)
        dur = ep.get('duration_seconds') or 0
        dur_str = f'{dur // 60} min' if dur else ''
        meta = f"{date_str} · {dur_str}" if dur_str else date_str

        # Fallback chain for title link: brief page -> site homepage.
        # Never link the title to the .mp3 directly (that triggers a download
        # and looks like a blank page in the browser).
        title_link = escape(ep.get('brief_url') or settings.site_base_url or '/')
        audio_url = escape(ep.get('audio_url') or '')
        brief_url_raw = ep.get('brief_url') or ''
        brief_url = escape(brief_url_raw)
        # Per-episode sources manifest page. Opens in new tab so the listener
        # doesn't lose their place on the home index.
        sources_url = escape(f"{sources_base}{pub_dt.strftime('%Y-%m-%d')}.html")

        # Links row: always show Listen. Append "Read brief" when a brief page
        # exists, then "Sources" pointing to the per-episode manifest.
        links_parts = [f'<a href="{audio_url}">{listen_label}</a>']
        if brief_url_raw:
            links_parts.append('<span class="dot">·</span>')
            links_parts.append(f'<a href="{brief_url}">{brief_label}</a>')
        links_parts.append('<span class="dot">·</span>')
        links_parts.append(
            f'<a href="{sources_url}" target="_blank" rel="noopener">{sources_label}</a>'
        )
        links_html = ''.join(links_parts)

        cards.append(
            f'<div class="card">'
            f'<p class="card-meta">{escape(meta)}</p>'
            f'<h3><a href="{title_link}">{escape(ep["title"])}</a></h3>'
            f'<p class="card-summary">{escape(ep["summary"])}</p>'
            f'<p class="card-links">{links_html}</p>'
            f'</div>'
        )

    if cards:
        # Wrap cards in a CSS grid so the layout auto-fits up to ~4 columns
        # on wide screens and collapses to 1 column on mobile.
        episodes_html = '<div class="cards-grid">' + '\n'.join(cards) + '</div>'
    elif locale == 'fr':
        episodes_html = (
            "<div class='card empty'>"
            "<p class='card-meta'>Bientôt</p>"
            "<h3>Premier épisode publié dans les jours qui viennent.</h3>"
            "<p class='card-summary'>Abonnez-vous via Apple, Spotify, YouTube ou RSS pour être notifié.</p>"
            "</div>"
        )
    else:
        episodes_html = (
            "<div class='card empty'>"
            "<p class='card-meta'>Coming soon</p>"
            "<h3>First episode publishing within days.</h3>"
            "<p class='card-summary'>Subscribe via Apple, Spotify, YouTube, or RSS to be notified.</p>"
            "</div>"
        )

    html = template.replace('{{EPISODES}}', episodes_html)
    out_dir = settings.docs_output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'index.html').write_text(html, encoding='utf-8')


# ── SOCIAL FEED (LinkedIn) ───────────────────────────────────────────────
# A single merged EN+FR feed designed to drive an external RSS-to-LinkedIn
# automation (Buffer, Zapier, Make, etc.). The canonical podcast feeds stay
# per-locale; this feed only exists to produce LinkedIn-ready post copy.

# Per-locale metadata for the social feed. Kept inline rather than in
# podcast.yaml to avoid polluting the main config — this is presentation
# layer only, not runtime behavior.
_SOCIAL_LOCALES: dict[str, dict[str, str]] = {
    'en': {
        'state_file': 'episode_history.json',          # legacy un-suffixed path
        'site_base_url': 'https://podcast.aequitus.net',
        'hashtags': '#AI #Podcast #TechBriefing',
        'listen_label': 'Listen',
    },
    'fr': {
        'state_file': 'episode_history_fr.json',
        'site_base_url': 'https://podcast.aequitus.net/fr',
        'hashtags': '#IntelligenceArtificielle #Podcast #IA',
        'listen_label': 'Écouter',
    },
}

_SOCIAL_SUMMARY_MAX_CHARS = 200
_SOCIAL_ITEM_LIMIT = 20
_SOCIAL_CHANNEL_TITLE = 'AI Press Review — Social Feed (EN+FR)'
_SOCIAL_CHANNEL_DESC = (
    'Merged bilingual feed for LinkedIn distribution. Each item carries '
    'LinkedIn-ready copy — short summary, listen link, hashtags.'
)


def _truncate_summary(text: str, max_chars: int = _SOCIAL_SUMMARY_MAX_CHARS) -> str:
    """Cut at the last sentence/word boundary within max_chars, add ellipsis."""
    if not text:
        return ''
    text = text.strip()
    if len(text) <= max_chars:
        return text
    # Prefer a sentence boundary, then a word boundary
    cutoff = text[:max_chars]
    for marker in ('. ', '! ', '? '):
        idx = cutoff.rfind(marker)
        if idx >= max_chars * 0.5:
            return cutoff[:idx + 1].rstrip()
    idx = cutoff.rfind(' ')
    if idx >= max_chars * 0.5:
        return cutoff[:idx].rstrip() + '…'
    return cutoff.rstrip() + '…'


def _build_social_copy(ep: dict, locale_meta: dict[str, str]) -> str:
    """Build the LinkedIn-ready post body for a single episode.

    Rules (aligned with brand voice):
    - Title on its own line.
    - One-to-two sentence summary, truncated at a sentence/word boundary.
    - Single-line CTA with em-dash separator.
    - Hashtags adapted to locale.
    - No emojis. No negatives. No greetings.
    """
    title = (ep.get('title') or '').strip()
    summary = _truncate_summary(ep.get('summary') or '')
    listen_url = ep.get('brief_url') or locale_meta['site_base_url']
    hashtags = locale_meta['hashtags']
    listen_label = locale_meta['listen_label']

    parts = [title]
    if summary:
        parts.append('')
        parts.append(summary)
    parts.append('')
    parts.append(f'{listen_label} — {listen_url}')
    parts.append('')
    parts.append(hashtags)
    return '\n'.join(parts)


def _load_social_episodes() -> list[dict]:
    """Load episodes from both EN and FR histories, tagged with locale.

    Returns a list merged and sorted by published_at descending, capped at
    _SOCIAL_ITEM_LIMIT.
    """
    merged: list[dict] = []
    for locale, meta in _SOCIAL_LOCALES.items():
        state_path = DATA_DIR / 'state' / meta['state_file']
        if not state_path.exists():
            logger.info('Social feed: no history for locale=%s (%s)', locale, state_path)
            continue
        history = read_json(state_path, {'episodes': []})
        for ep in history.get('episodes', []):
            ep_copy = dict(ep)
            ep_copy['_locale'] = locale
            merged.append(ep_copy)

    def _sort_key(ep: dict) -> datetime:
        try:
            dt = datetime.fromisoformat(ep['published_at'])
        except (KeyError, ValueError):
            return datetime.min.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    merged.sort(key=_sort_key, reverse=True)
    return merged[:_SOCIAL_ITEM_LIMIT]


def build_social_feed(output_path: Path | None = None) -> Path:
    """Generate the bilingual LinkedIn-oriented RSS feed.

    Reads both EN and FR episode histories, merges them, and writes a single
    RSS file with LinkedIn-optimized <description> copy per item.

    Returns the path to the generated file.
    """
    if output_path is None:
        output_path = DOCS_DIR / 'social-feed.xml'

    episodes = _load_social_episodes()

    items: list[str] = []
    latest_pub_dt: datetime | None = None
    for ep in episodes:
        locale = ep.get('_locale', 'en')
        locale_meta = _SOCIAL_LOCALES[locale]

        try:
            ep_dt = datetime.fromisoformat(ep['published_at'])
        except (KeyError, ValueError):
            continue
        if ep_dt.tzinfo is None:
            ep_dt = ep_dt.replace(tzinfo=timezone.utc)
        if latest_pub_dt is None or ep_dt > latest_pub_dt:
            latest_pub_dt = ep_dt

        pub_date = format_datetime(ep_dt)
        post_body = _build_social_copy(ep, locale_meta)
        link = ep.get('brief_url') or locale_meta['site_base_url']
        guid = f"social-{locale}-{ep.get('date', '')}-{ep.get('slug', '')}"

        items.append(
            f"<item>"
            f"<title>{escape(ep.get('title', ''))}</title>"
            f"<link>{escape(link)}</link>"
            f"<description><![CDATA[{post_body}]]></description>"
            f"<guid isPermaLink=\"false\">{escape(guid)}</guid>"
            f"<pubDate>{pub_date}</pubDate>"
            f"</item>"
        )

    now_dt = utcnow()
    last_build_date = format_datetime(now_dt)
    channel_pub_date = format_datetime(latest_pub_dt) if latest_pub_dt else last_build_date
    self_href = 'https://podcast.aequitus.net/social-feed.xml'

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        '<channel>'
        f"<title>{escape(_SOCIAL_CHANNEL_TITLE)}</title>"
        f"<link>{escape('https://podcast.aequitus.net')}</link>"
        f'<atom:link href="{escape(self_href)}" rel="self" type="application/rss+xml" />'
        '<language>mul</language>'
        f"<description>{escape(_SOCIAL_CHANNEL_DESC)}</description>"
        f"<lastBuildDate>{last_build_date}</lastBuildDate>"
        f"<pubDate>{channel_pub_date}</pubDate>"
        '<ttl>60</ttl>'
        f"{''.join(items)}"
        '</channel></rss>'
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml, encoding='utf-8')
    logger.info('Social feed written: %s (%d items)', output_path, len(items))
    return output_path
