from __future__ import annotations

import logging
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable
from xml.sax.saxutils import escape

from .collectors.newsapi import fetch_newsapi_articles
from .collectors.rss import fetch_rss_entries
from .editorial.clustering import (
    cluster_manifest_summary,
    cluster_sources,
    rank_clusters,
    reduce_to_sources,
)
from .extractors.web_content import batch_extract
from .models import SourceItem
from .settings import DATA_DIR, DOCS_DIR, ScoringConfig, load_settings, load_sources_config
from .state import load_episode_history, load_used_sources, save_used_sources
from .utils import fingerprint, iso_now, title_similarity, within_hours, write_json

logger = logging.getLogger(__name__)


def _previous_episode_memory() -> tuple[set[str], list[str]]:
    history = load_episode_history()
    episodes = history.get("episodes", [])
    if not episodes:
        return set(), []
    latest = episodes[0]
    return set(latest.get("source_fingerprints", [])), list(latest.get("source_titles", []))


def _all_used_this_week() -> tuple[set[str], list[str]]:
    """Fingerprints and titles from all recent episodes (for weekly recap)."""
    history = load_episode_history()
    fps: set[str] = set()
    titles: list[str] = []
    for ep in history.get("episodes", [])[:7]:
        fps.update(ep.get("source_fingerprints", []))
        titles.extend(ep.get("source_titles", []))
    used = load_used_sources()
    titles.extend(item.get("title", "") for item in used.get("items", []))
    return fps, titles


def _recent_used_titles() -> list[str]:
    payload = load_used_sources()
    return [item.get("title", "") for item in payload.get("items", [])]


def _contains_banned_topic(text: str, scoring: ScoringConfig) -> bool:
    value = (text or "").lower()
    return any(term in value for term in scoring.banned_terms)


def _ai_relevance_score(texts: Iterable[str], scoring: ScoringConfig) -> float:
    joined = " ".join(text or "" for text in texts).lower()
    score = 0.0
    for term in scoring.ai_terms_high:
        if term in joined:
            score += 3.0
    for term in scoring.ai_terms_mid:
        if term in joined:
            score += 1.5
    for term in scoring.ai_terms_low:
        if term in joined:
            score += 0.5
    return score


def _score_source(item: SourceItem, scoring: ScoringConfig) -> float:
    score = 0.0
    combined = " ".join(filter(None, [item.title, item.summary, item.content_text])).lower()

    # Content depth
    content_len = len(item.content_text or "")
    if content_len >= 2000:
        score += 4.0
    elif content_len >= 1200:
        score += 3.0
    elif content_len >= 700:
        score += 2.0
    elif item.summary and len(item.summary) >= 180:
        score += 1.0

    # Numerical data density
    digit_count = sum(1 for char in combined if char.isdigit())
    if digit_count >= 10:
        score += 2.0
    elif digit_count >= 3:
        score += 1.0

    # Strong signal words
    strong_matches = sum(1 for w in scoring.signal_words_strong if w in combined)
    score += min(strong_matches * 1.0, 4.0)

    # Medium signal words
    medium_matches = sum(1 for w in scoring.signal_words_medium if w in combined)
    score += min(medium_matches * 0.5, 2.0)

    # Domain authority
    domain = (item.domain or "").lower()
    for auth_domain, bonus in scoring.domain_authority.items():
        if domain.endswith(auth_domain):
            score += bonus
            break

    # AI relevance
    ai_score = _ai_relevance_score([item.title, item.summary, item.content_text or ""], scoring)
    score += min(ai_score, 5.0)

    return round(score, 2)


def _is_editorially_valid(item: SourceItem, settings) -> bool:
    scoring = settings.scoring

    if not item.url or not item.title or not item.domain:
        return False

    if not within_hours(item.published_at, settings.freshness_hours):
        return False

    combined = " ".join(filter(None, [item.title, item.summary, item.content_text]))
    if _contains_banned_topic(combined, scoring):
        return False

    ai_score = _ai_relevance_score([item.title, item.summary, item.content_text or ""], scoring)
    if ai_score < 1.0:
        return False

    effective_text = (item.content_text or item.summary or "").strip()
    if len(effective_text) < scoring.min_text_length:
        return False

    item.relevance_score = _score_source(item, scoring)
    return item.relevance_score >= scoring.min_relevance


def _is_duplicate_of_previous(
    item: SourceItem,
    previous_fingerprints: set[str],
    previous_titles: list[str],
    recent_titles: list[str],
    threshold: float,
) -> bool:
    fp = fingerprint(item.title, item.url)
    if fp in previous_fingerprints:
        return True

    for prior_title in previous_titles + recent_titles:
        if title_similarity(item.title, prior_title) >= threshold:
            return True

    return False


def _apply_weekly_bonus(
    sources: list[SourceItem],
    used_fps: set[str],
    used_titles: list[str],
    settings,
) -> list[SourceItem]:
    """For weekly recap: boost unused sources, penalize reused ones."""
    threshold = settings.scoring.similarity_threshold
    kept: list[SourceItem] = []
    for item in sources:
        fp = fingerprint(item.title, item.url)
        is_reused = fp in used_fps or any(
            title_similarity(item.title, t) >= threshold for t in used_titles
        )
        if is_reused:
            if item.relevance_score < settings.reuse_min_score:
                continue
            item.relevance_score = round(item.relevance_score - 1.0, 2)
        else:
            item.relevance_score = round(item.relevance_score + settings.unused_score_bonus, 2)
        kept.append(item)
    kept.sort(key=lambda s: (s.relevance_score, s.published_at or ""), reverse=True)
    return kept


def _update_used_sources(sources: list[SourceItem]) -> None:
    payload = load_used_sources()
    items = payload.get("items", [])
    fresh = [{"title": src.title, "url": src.url, "used_at": iso_now()} for src in sources[:80]]
    merged = (fresh + items)[:400]
    payload["items"] = merged
    save_used_sources(payload)


def collect_sources(run_date: str, local_preview: bool = False, profile: str | None = None) -> dict:
    settings = load_settings(local_preview=local_preview, profile=profile)
    cfg = load_sources_config()

    # Phase 1: Collect metadata in parallel (RSS feeds + NewsAPI)
    logger.info("Phase 1: Collecting metadata from RSS and NewsAPI...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        rss_future = executor.submit(
            fetch_rss_entries,
            list(cfg.get("google_news_rss", [])) + list(cfg.get("curated_rss", [])),
            settings.freshness_hours,
        )
        newsapi_future = executor.submit(
            fetch_newsapi_articles,
            settings.newsapi_api_key,
            settings.newsapi_query,
            settings.newsapi_page_size,
            settings.freshness_hours,
        )
        rss_items = rss_future.result()
        newsapi_items = newsapi_future.result()

    logger.info("Collected %d RSS + %d NewsAPI items", len(rss_items), len(newsapi_items))

    # Phase 2: Pre-filter and deduplicate before expensive extraction
    if settings.exclude_previous_episode:
        previous_fingerprints, previous_titles = _previous_episode_memory()
        recent_titles = _recent_used_titles()
    else:
        previous_fingerprints, previous_titles, recent_titles = set(), [], []

    # For weekly recap: load all used data even though we don't pre-filter
    weekly_used_fps: set[str] = set()
    weekly_used_titles: list[str] = []
    if settings.prefer_unused:
        weekly_used_fps, weekly_used_titles = _all_used_this_week()

    candidates: list[SourceItem] = []
    seen_urls: set[str] = set()

    google_news_skipped = 0
    for item in rss_items + newsapi_items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)

        # Drop unresolved Google News URLs — content is inaccessible
        if "news.google.com" in (item.url or ""):
            google_news_skipped += 1
            continue

        if settings.exclude_previous_episode and _is_duplicate_of_previous(
            item, previous_fingerprints, previous_titles, recent_titles, settings.scoring.similarity_threshold
        ):
            continue

        if _contains_banned_topic(" ".join(filter(None, [item.title, item.summary])), settings.scoring):
            continue

        candidates.append(item)

    if google_news_skipped:
        logger.info("Dropped %d unresolved Google News URLs", google_news_skipped)

    logger.info("Phase 2: %d candidates after pre-filtering", len(candidates))

    # Phase 3: Batch extract content in parallel for items missing content
    urls_to_extract = [item.url for item in candidates if not (item.content_text or "").strip()]
    if urls_to_extract:
        logger.info("Phase 3: Extracting content for %d articles...", len(urls_to_extract))
        extracted_map = batch_extract(urls_to_extract)
        for item in candidates:
            if not (item.content_text or "").strip() and item.url in extracted_map:
                result = extracted_map[item.url]
                if result:
                    item.content_text = result.text
    else:
        logger.info("Phase 3: All candidates already have content")

    # Phase 4: Score and filter
    deduped: OrderedDict[str, SourceItem] = OrderedDict()
    for item in candidates:
        if not _is_editorially_valid(item, settings):
            continue

        fp = fingerprint(item.title, item.url)
        existing = deduped.get(fp)
        if existing is None or item.relevance_score > existing.relevance_score:
            deduped[fp] = item

    sources = list(deduped.values())
    sources.sort(key=lambda s: (s.relevance_score, s.published_at or ""), reverse=True)

    # Phase 4b: Weekly bonus/penalty for unused vs reused sources
    if settings.prefer_unused and weekly_used_fps:
        sources = _apply_weekly_bonus(sources, weekly_used_fps, weekly_used_titles, settings)

    # Phase 4c: Semantic clustering — group sources that report the same
    # story so the LLM receives deduplicated stories, not raw articles.
    # Gracefully degrades to singleton clusters if the embedding endpoint
    # is unavailable.
    clusters = cluster_sources(sources)
    clusters_ranked = rank_clusters(clusters)
    reps_per_cluster = int(getattr(settings.scoring, 'cluster_representatives', 0) or 3)
    sources = reduce_to_sources(clusters_ranked, k_per_cluster=reps_per_cluster)
    cluster_summary = cluster_manifest_summary(clusters_ranked)
    logger.info(
        "Clustering: %d sources grouped into %d stories; keeping top %d per story",
        sum(c.size for c in clusters_ranked), len(clusters_ranked), reps_per_cluster,
    )

    # Phase 4d: Cap per domain to ensure source diversity across stories
    max_per_domain = settings.scoring.max_per_domain
    if max_per_domain > 0:
        domain_counts: dict[str, int] = {}
        capped: list[SourceItem] = []
        for item in sources:
            d = (item.domain or "").lower()
            count = domain_counts.get(d, 0)
            if count >= max_per_domain:
                continue
            domain_counts[d] = count + 1
            capped.append(item)
        if len(capped) < len(sources):
            logger.info("Domain cap applied: %d → %d sources (max %d per domain)", len(sources), len(capped), max_per_domain)
        sources = capped

    logger.info(
        "Phase 4: %d sources selected (min required: %d)",
        len(sources), settings.min_source_count,
    )

    _update_used_sources(sources)

    manifest = {
        "run_date": run_date,
        "generated_at": iso_now(),
        "source_count": len(sources),
        "profile": settings.profile_name,
        "sources": [s.to_dict() for s in sources],
        "clusters": cluster_summary,
        "cluster_count": len(cluster_summary),
    }

    data_sources_dir = DATA_DIR / "sources"
    docs_sources_dir = DOCS_DIR / "sources"
    data_sources_dir.mkdir(parents=True, exist_ok=True)
    docs_sources_dir.mkdir(parents=True, exist_ok=True)

    write_json(data_sources_dir / f"{run_date}.json", manifest)
    write_json(data_sources_dir / "latest.json", manifest)

    md = _manifest_to_markdown(manifest)
    html = _manifest_to_html(manifest)

    (data_sources_dir / f"{run_date}.md").write_text(md, encoding="utf-8")
    (data_sources_dir / "latest.md").write_text(md, encoding="utf-8")
    (docs_sources_dir / f"{run_date}.html").write_text(html, encoding="utf-8")
    (docs_sources_dir / "latest.html").write_text(html, encoding="utf-8")

    return manifest


def _manifest_to_markdown(manifest: dict) -> str:
    lines = [
        f"# Source manifest — {manifest['run_date']}",
        "",
        f"Generated at: {manifest['generated_at']}",
        f"Profile: {manifest.get('profile', 'daily')}",
        f"Relevant source count: {manifest['source_count']}",
        "",
    ]

    for idx, src in enumerate(manifest["sources"], start=1):
        lines.extend(
            [
                f"## {idx}. {src['title']}",
                f"- Domain: {src['domain']}",
                f"- URL: {src['url']}",
                f"- Relevance score: {src.get('relevance_score', 0.0)}",
            ]
        )

        if src.get("published_at"):
            lines.append(f"- Published: {src['published_at']}")
        if src.get("summary"):
            lines.append(f"- Summary: {src['summary']}")
        if src.get("content_text"):
            lines.append(f"- Extract: {src['content_text'][:800]}")

        lines.append("")

    return "\n".join(lines)


def _manifest_to_html(manifest: dict) -> str:
    cards = []

    for src in manifest["sources"]:
        summary = (src.get("summary") or src.get("content_text") or "")[:900]
        cards.append(
            "<article class='card'>"
            f"<h3>{escape(src['title'])}</h3>"
            f"<p><strong>{escape(src['domain'])}</strong></p>"
            f"<p>{escape(summary)}</p>"
            f"<p><a href='{escape(src['url'])}'>Open source</a></p>"
            "</article>"
        )

    return (
        "<!doctype html>"
        "<html lang='en'>"
        "<head>"
        "<meta charset='utf-8'>"
        f"<title>Sources {escape(manifest['run_date'])}</title>"
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:900px;margin:2rem auto;line-height:1.5}"
        ".card{border:1px solid #ddd;border-radius:14px;padding:1rem;margin:1rem 0}"
        "</style>"
        "</head>"
        "<body>"
        f"<h1>Sources — {escape(manifest['run_date'])} ({escape(manifest.get('profile', 'daily'))})</h1>"
        f"<p>Generated at {escape(manifest['generated_at'])}</p>"
        f"{''.join(cards)}"
        "</body>"
        "</html>"
    )
