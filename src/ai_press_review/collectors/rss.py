from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import feedparser

from ..models import SourceItem
from ..utils import clean_text, domain_from_url, normalize_url, within_hours

logger = logging.getLogger(__name__)

MAX_FEED_WORKERS = 6


def _parse_single_feed(feed_url: str, freshness_hours: int) -> list[SourceItem]:
    items: list[SourceItem] = []
    try:
        parsed = feedparser.parse(feed_url)
    except Exception:
        logger.warning("Failed to parse RSS feed: %s", feed_url)
        return items

    for entry in parsed.entries:
        link = normalize_url(entry.get('link', ''))
        if not link:
            continue
        published = entry.get('published') or entry.get('updated')
        if not within_hours(published, freshness_hours):
            continue
        summary = clean_text(entry.get('summary', ''))[:1200]
        items.append(
            SourceItem(
                url=link,
                title=clean_text(entry.get('title', 'Untitled')),
                domain=domain_from_url(link),
                published_at=published,
                summary=summary,
                queries=[feed_url],
                sections=[],
            )
        )
    return items


def fetch_rss_entries(feed_urls: Iterable[str], freshness_hours: int) -> list[SourceItem]:
    feed_list = list(feed_urls)
    all_items: list[SourceItem] = []

    with ThreadPoolExecutor(max_workers=MAX_FEED_WORKERS) as executor:
        futures = {
            executor.submit(_parse_single_feed, url, freshness_hours): url
            for url in feed_list
        }
        for future in as_completed(futures):
            feed_url = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
                logger.info("RSS feed %s: %d entries", feed_url[:80], len(items))
            except Exception:
                logger.warning("RSS feed failed: %s", feed_url)

    return all_items
