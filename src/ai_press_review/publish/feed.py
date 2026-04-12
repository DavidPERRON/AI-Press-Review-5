from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

from ..models import PublishedEpisode
from ..settings import DOCS_DIR, load_settings
from ..state import load_episode_history, save_episode_history
from ..storage.r2 import delete_key
from ..utils import utcnow


def publish_episode(episode: PublishedEpisode, source_fingerprints: list[str], source_titles: list[str]) -> None:
    history = load_episode_history()
    episodes = history.get('episodes', [])
    payload = episode.to_dict()
    payload['source_fingerprints'] = source_fingerprints
    payload['source_titles'] = source_titles
    episodes.insert(0, payload)

    settings = load_settings()
    cutoff = utcnow() - timedelta(days=settings.retention_days)

    kept = []
    for item in episodes:
        published_at = datetime.fromisoformat(item['published_at'])
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
        items.append(
            f"<item><title>{escape(ep['title'])}</title>"
            f"<description>{escape(ep['summary'])}</description>"
            f"<guid>{escape(ep['audio_url'])}</guid>"
            f"<pubDate>{pub_date}</pubDate>"
            f'<enclosure url="{escape(ep["audio_url"])}" length="{ep["audio_bytes"]}" type="audio/mpeg" />'
            f"<itunes:summary>{escape(ep['summary'])}</itunes:summary>"
            f"<link>{escape(ep['source_manifest_url'])}</link></item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
        '<channel>'
        f"<title>{escape(settings.podcast_title)}</title>"
        f"<link>{escape(settings.site_base_url)}</link>"
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


def _write_index(episodes: list[dict]) -> None:
    settings = load_settings()
    cards = []
    for ep in episodes:
        cards.append(
            f"<article class='card'>"
            f"<h3>{escape(ep['title'])}</h3>"
            f"<p>{escape(ep['summary'])}</p>"
            f"<p><a href='{escape(ep['audio_url'])}'>Listen</a> · "
            f"<a href='{escape(ep['source_manifest_url'])}'>Sources</a></p>"
            f"</article>"
        )
    empty = "<div class='card'><strong>No episodes published yet.</strong></div>"
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(settings.podcast_title)}</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:760px;margin:2rem auto;line-height:1.55;color:#111}"
        "img{max-width:240px;border-radius:20px}.card{border:1px solid #ddd;border-radius:16px;padding:1rem 1.25rem;margin:1rem 0}</style>"
        "</head><body>"
        f"<img src='{escape(settings.cover_image_path)}' alt='cover'>"
        f"<h1>{escape(settings.podcast_title)}</h1>"
        f"<p>{escape(settings.podcast_subtitle)}</p>"
        "<p><a href='podcast-feed.xml'>Podcast RSS feed</a></p>"
        f"{''.join(cards) if cards else empty}"
        "</body></html>"
    )
    (DOCS_DIR / 'index.html').write_text(html, encoding='utf-8')
