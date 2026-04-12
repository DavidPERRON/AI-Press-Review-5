from __future__ import annotations

import logging
from datetime import timedelta

import requests

from ..models import SourceItem
from ..utils import clean_text, domain_from_url, normalize_url, utcnow, within_hours

logger = logging.getLogger(__name__)

NEWSAPI_URL = 'https://newsapi.org/v2/everything'


def fetch_newsapi_articles(api_key: str, query: str, page_size: int = 50, freshness_hours: int = 48) -> list[SourceItem]:
    if not api_key:
        logger.info("NewsAPI key not set, skipping")
        return []

    since = (utcnow() - timedelta(hours=freshness_hours)).isoformat()
    try:
        response = requests.get(
            NEWSAPI_URL,
            params={
                'q': query,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': min(page_size, 100),
                'from': since,
            },
            headers={'X-Api-Key': api_key},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("NewsAPI request failed: %s", exc)
        return []

    payload = response.json()
    items: list[SourceItem] = []

    for article in payload.get('articles', []):
        url = normalize_url(article.get('url', ''))
        if not url:
            continue
        published = article.get('publishedAt')
        if not within_hours(published, freshness_hours):
            continue
        title = clean_text(article.get('title', 'Untitled'))
        summary = clean_text(article.get('description', '') or article.get('content', ''))[:1200]
        items.append(
            SourceItem(
                url=url,
                title=title,
                domain=domain_from_url(url),
                published_at=published,
                summary=summary,
                queries=[query],
                sections=[],
            )
        )

    logger.info("NewsAPI: %d articles collected", len(items))
    return items
