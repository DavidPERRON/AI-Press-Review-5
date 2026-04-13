from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import logging

from ..models import PublishedEpisode
from ..settings import DOCS_DIR, load_settings
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
        'source_manifest': [],
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
    for ep in episodes:
        pub_date = format_datetime(datetime.fromisoformat(ep['published_at']))
        duration_secs = ep.get('duration_seconds', 0)
        duration_str = f"{duration_secs // 3600}:{(duration_secs % 3600) // 60:02d}:{duration_secs % 60:02d}"
        brief_url = ep.get('brief_url') or ep.get('source_manifest_url', '')
        content_encoded = (
            f"<p>{escape(ep['summary'])}</p>"
            f'<p><a href="{escape(ep.get("source_manifest_url", ""))}">Source manifest</a></p>'
        )
        items.append(
            f"<item><title>{escape(ep['title'])}</title>"
            f"<description>{escape(ep['summary'])}</description>"
            f"<content:encoded><![CDATA[{content_encoded}]]></content:encoded>"
            f"<guid isPermaLink=\"false\">{escape(ep.get('date', '') + '-' + ep.get('slug', ''))}</guid>"
            f"<pubDate>{pub_date}</pubDate>"
            f'<enclosure url="{escape(ep["audio_url"])}" length="{ep["audio_bytes"]}" type="audio/mpeg" />'
            f"<itunes:summary>{escape(ep['summary'])}</itunes:summary>"
            f"<itunes:duration>{escape(duration_str)}</itunes:duration>"
            f"<link>{escape(brief_url)}</link></item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<?xml-stylesheet type="text/xsl" href="/feed.xsl"?>\n'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">'
        '<channel>'
        f"<title>{escape(settings.podcast_title)}</title>"
        f"<link>{escape(settings.site_base_url)}</link>"
        f'<atom:link href="{escape(settings.rss_feed_url)}" rel="self" type="application/rss+xml" />'
        f"<language>{escape(settings.podcast_language)}</language>"
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
    (DOCS_DIR / 'podcast-feed.xml').write_text(xml, encoding='utf-8')


_INDEX_TEMPLATE_PATH = Path(__file__).parent / 'templates' / 'index-template.html'


def _write_index(episodes: list[dict]) -> None:
    template = _INDEX_TEMPLATE_PATH.read_text(encoding='utf-8')
    cards = []
    for ep in episodes:
        pub_dt = datetime.fromisoformat(ep['published_at'])
        date_str = pub_dt.strftime('%b %d, %Y')
        dur = ep.get('duration_seconds') or 0
        dur_str = f'{dur // 60} min' if dur else ''
        brief_url = ep.get('brief_url', '')
        title_link = escape(brief_url) if brief_url else escape(ep["audio_url"])
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
    (DOCS_DIR / 'index.html').write_text(html, encoding='utf-8')
