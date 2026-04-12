from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import requests
import trafilatura
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..utils import clean_text

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

MAX_CONTENT_LENGTH = 6000
MIN_CONTENT_LENGTH = 400
MAX_EXTRACTION_WORKERS = 8


@dataclass
class ExtractedContent:
    url: str
    text: str
    method: str


def _extract_with_trafilatura(url: str, html: str) -> Optional[str]:
    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_links=False,
            include_images=False,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
        )
        text = clean_text(text or "")
        if len(text) >= MIN_CONTENT_LENGTH:
            return text
    except Exception:
        pass
    return None


def _extract_with_beautifulsoup(html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, 'lxml')
        paragraphs = [clean_text(p.get_text(' ', strip=True)) for p in soup.find_all('p')]
        text = ' '.join(part for part in paragraphs if part)
        text = clean_text(text)
        if len(text) >= MIN_CONTENT_LENGTH:
            return text
    except Exception:
        pass
    return None


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _fetch_html(url: str, timeout: int = 25) -> Optional[str]:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def _fetch_and_extract(url: str) -> Optional[ExtractedContent]:
    try:
        html = _fetch_html(url)
    except Exception:
        return None

    if not html:
        return None

    text = _extract_with_trafilatura(url, html)
    if text:
        return ExtractedContent(url=url, text=text[:MAX_CONTENT_LENGTH], method="trafilatura")

    text = _extract_with_beautifulsoup(html)
    if text:
        return ExtractedContent(url=url, text=text[:MAX_CONTENT_LENGTH], method="beautifulsoup")

    return None


async def _crawl4ai_extract_async(url: str) -> Optional[ExtractedContent]:
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            markdown = clean_text(getattr(result, "markdown", "") or "")
            if len(markdown) >= MIN_CONTENT_LENGTH:
                return ExtractedContent(url=url, text=markdown[:MAX_CONTENT_LENGTH], method="crawl4ai")
    except Exception:
        pass
    return None


def _extract_with_crawl4ai(url: str) -> Optional[ExtractedContent]:
    try:
        return asyncio.run(_crawl4ai_extract_async(url))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_crawl4ai_extract_async(url))
        finally:
            loop.close()
    except Exception:
        return None


@lru_cache(maxsize=512)
def extract_article_content(url: str) -> Optional[ExtractedContent]:
    extracted = _extract_with_crawl4ai(url)
    if extracted:
        return extracted

    extracted = _fetch_and_extract(url)
    if extracted:
        return extracted

    logger.debug("All extraction methods failed for %s", url)
    return None


def fetch_article_text(url: str) -> str:
    result = extract_article_content(url)
    return result.text if result else ''


def batch_extract(urls: list[str], max_workers: int = MAX_EXTRACTION_WORKERS) -> dict[str, Optional[ExtractedContent]]:
    unique_urls = list(dict.fromkeys(urls))
    results: dict[str, Optional[ExtractedContent]] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(extract_article_content, url): url for url in unique_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception:
                logger.warning("Extraction failed for %s", url)
                results[url] = None

    return results
