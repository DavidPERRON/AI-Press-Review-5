from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import logging

from ..models import PublishedEpisode
from ..settings import load_settings
from ..state import load_episode_history, save_episode_history
from ..storage.r2 import delete_key
from ..utils import utcnow
from .episode_brief import generate_episode_brief

logger = logging.getLogger(__name__)


def _build_brief_data(episode: PublishedEpisode, source_titles: list[str], episode_number: int) -> dict:
    """Build the data dict expected by generate_episode_brief."""
    pub_dt = datetime.fromisoformat(episode.published_at)
    dur = episode.duration_seconds or 0
    dur_str = f"{dur // 60}:{dur % 60:02d}"

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


_INDEX_TEMPLATE_PATH = Path(__file__).parent / 'templates' / 'index-template.html'


def _write_index(episodes: list[dict]) -> None:
    template = _INDEX_TEMPLATE_PATH.read_text(encoding='utf-8')
    cards = []
    settings = load_settings()
    for ep in episodes:
        pub_dt = datetime.fromisoformat(ep['published_at'])
        date_str = pub_dt.strftime('%b %d, %Y')
        dur = ep.get('duration_seconds') or 0
        dur_str = f'{dur // 60} min' if dur else ''
        # Fallback chain for title link: brief page -> site homepage.
        # Never link the title to the .mp3 directly (that triggers a download
        # and looks like a blank page in the browser).
        title_link = escape(ep.get('brief_url') or settings.site_base_url or '/')
        cards.append(
            f'<div class="episode-item">'
            f'<div>'
            f'<a href="{title_link}" class="episode-title">{escape(ep["title"])}</a>'
            f'<div class="episode-meta">{date_str}</div>'
            f'<p class="episode-summary">{escape(ep["summary"])}</p>'
            f'<a href="{escape(ep["audio_url"])}" class="episode-listen">Listen &rarr;</a>'
            f'</div>'
            f'<span class="episode-duration">{dur_str}</span>'
            f'</div>'
        )
    episodes_html = '\n'.join(cards) if cards else '<div class="empty-state">First episode coming soon.</div>'
    html = template.replace('{{EPISODES}}', episodes_html)
    out_dir = settings.docs_output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
