"""Semantic clustering of collected sources.

Purpose: before handing the manifest to the LLM, group sources that
report the same story. The LLM then sees N distinct stories (each
backed by several corroborating sources) instead of a flat list of
raw articles — which avoids redundant paragraphs, preserves cross-
source verification, and enables single-source outliers to be marked
as "weak signals" automatically.

Design:
- Embed each source's (title + summary) via an OpenAI-compatible
  embeddings endpoint.
- Greedy single-linkage clustering on cosine similarity (O(n²)).
- For each cluster, pick K representative sources biased toward
  primary sources and domain diversity.
- Gracefully degrade to per-source singleton clusters if the
  embedding endpoint is unreachable or not configured.
"""
from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field

import requests

from ..models import SourceItem

logger = logging.getLogger(__name__)


DEFAULT_CLUSTERING_THRESHOLD = 0.82
DEFAULT_EMBEDDING_MODEL = 'text-embedding-3-small'
DEFAULT_REPRESENTATIVES_PER_CLUSTER = 3


@dataclass
class SourceCluster:
    """A group of sources reporting the same story."""
    id: int
    sources: list[SourceItem] = field(default_factory=list)
    embedding_centroid: list[float] | None = None

    @property
    def total_score(self) -> float:
        return sum(s.relevance_score for s in self.sources)

    @property
    def domains(self) -> set[str]:
        return {(s.domain or '').lower() for s in self.sources if s.domain}

    @property
    def size(self) -> int:
        return len(self.sources)


# ── Embedding call ───────────────────────────────────────────────────────────

def _embedding_config() -> tuple[str, str, str] | None:
    """Return (base_url, api_key, model) or None if not configured.

    Reuses LLM credentials if a dedicated EMBEDDING_* is not set, since
    most OpenAI-compatible gateways expose both on the same endpoint.
    """
    base = (os.getenv('EMBEDDING_BASE_URL') or os.getenv('LLM_BASE_URL') or '').strip().rstrip('/')
    key = (os.getenv('EMBEDDING_API_KEY') or os.getenv('LLM_API_KEY') or '').strip()
    model = (os.getenv('EMBEDDING_MODEL') or DEFAULT_EMBEDDING_MODEL).strip()
    if not base or not key:
        return None
    return base, key, model


def embed_texts(texts: list[str], timeout: int = 60) -> list[list[float]] | None:
    """Call an OpenAI-compatible /embeddings endpoint. Returns None on
    any failure — caller must fall back to singleton clusters."""
    config = _embedding_config()
    if not config:
        logger.info("Embeddings not configured; skipping clustering")
        return None
    base, key, model = config

    try:
        t0 = time.monotonic()
        response = requests.post(
            f"{base}/embeddings",
            headers={
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json',
            },
            json={'model': model, 'input': texts},
            timeout=timeout,
        )
        if response.status_code >= 400:
            logger.warning("Embedding API HTTP %s: %s", response.status_code, response.text[:200])
            return None
        data = response.json()
        vectors = [item['embedding'] for item in data.get('data', [])]
        if len(vectors) != len(texts):
            logger.warning("Embedding count mismatch: %d != %d", len(vectors), len(texts))
            return None
        logger.info(
            "Embedded %d sources in %.1fs (model=%s)",
            len(vectors), time.monotonic() - t0, model,
        )
        return vectors
    except Exception as exc:
        logger.warning("Embedding call failed: %s", exc)
        return None


# ── Vector math ──────────────────────────────────────────────────────────────

def _norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def _cosine(a: list[float], b: list[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _mean(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    acc = [0.0] * dim
    for vec in vectors:
        for i, v in enumerate(vec):
            acc[i] += v
    return [v / len(vectors) for v in acc]


# ── Clustering ───────────────────────────────────────────────────────────────

def _source_text(source: SourceItem) -> str:
    parts = [source.title or '', source.summary or '']
    content = source.content_text or ''
    if content:
        # Limit to first 400 chars — enough for topical clustering without
        # blowing token budget.
        parts.append(content[:400])
    return ' '.join(p.strip() for p in parts if p.strip())


def cluster_sources(
    sources: list[SourceItem],
    threshold: float = DEFAULT_CLUSTERING_THRESHOLD,
) -> list[SourceCluster]:
    """Cluster sources semantically. Returns one cluster per source
    if embedding is unavailable (graceful degradation)."""
    if not sources:
        return []

    texts = [_source_text(s) for s in sources]
    vectors = embed_texts(texts)
    if vectors is None:
        return _singleton_clusters(sources)

    clusters: list[SourceCluster] = []
    for idx, (source, vector) in enumerate(zip(sources, vectors)):
        best_cluster = None
        best_sim = 0.0
        for cluster in clusters:
            sim = _cosine(vector, cluster.embedding_centroid or [])
            if sim > best_sim:
                best_sim = sim
                best_cluster = cluster
        if best_cluster is not None and best_sim >= threshold:
            best_cluster.sources.append(source)
            # Incremental centroid update (exact mean of member vectors).
            k = best_cluster.size
            best_cluster.embedding_centroid = [
                (c * (k - 1) + v) / k
                for c, v in zip(best_cluster.embedding_centroid or [], vector)
            ]
        else:
            clusters.append(SourceCluster(
                id=len(clusters),
                sources=[source],
                embedding_centroid=list(vector),
            ))

    # Sort cluster members by relevance_score DESC for downstream picking.
    for cluster in clusters:
        cluster.sources.sort(key=lambda s: s.relevance_score, reverse=True)

    logger.info(
        "Clustered %d sources into %d groups (threshold=%.2f)",
        len(sources), len(clusters), threshold,
    )
    return clusters


def _singleton_clusters(sources: list[SourceItem]) -> list[SourceCluster]:
    return [SourceCluster(id=i, sources=[s]) for i, s in enumerate(sources)]


# ── Representative selection ────────────────────────────────────────────────

def pick_representatives(
    cluster: SourceCluster,
    k: int = DEFAULT_REPRESENTATIVES_PER_CLUSTER,
) -> list[SourceItem]:
    """Pick up to k sources per cluster, maximizing domain diversity
    and favoring higher-scored sources first."""
    if len(cluster.sources) <= k:
        return list(cluster.sources)

    picked: list[SourceItem] = []
    seen_domains: set[str] = set()
    for source in cluster.sources:
        domain = (source.domain or '').lower()
        if domain in seen_domains:
            continue
        picked.append(source)
        seen_domains.add(domain)
        if len(picked) >= k:
            return picked

    # If domain diversity alone did not fill k slots, top up with highest
    # scored remaining regardless of domain.
    remaining = [s for s in cluster.sources if s not in picked]
    picked.extend(remaining[: k - len(picked)])
    return picked


# ── Ranking & flat reduction ────────────────────────────────────────────────

def rank_clusters(clusters: list[SourceCluster]) -> list[SourceCluster]:
    """Rank clusters by aggregated signal: total score, then size, then
    domain diversity."""
    return sorted(
        clusters,
        key=lambda c: (c.total_score, c.size, len(c.domains)),
        reverse=True,
    )


def reduce_to_sources(
    clusters: list[SourceCluster],
    k_per_cluster: int = DEFAULT_REPRESENTATIVES_PER_CLUSTER,
) -> list[SourceItem]:
    """Flatten ranked clusters into a single ordered list of sources,
    with up to k per cluster. Used as a drop-in replacement for the
    pre-clustering flat list."""
    ranked = rank_clusters(clusters)
    flat: list[SourceItem] = []
    for cluster in ranked:
        flat.extend(pick_representatives(cluster, k=k_per_cluster))
    return flat


def cluster_manifest_summary(clusters: list[SourceCluster]) -> list[dict]:
    """Compact cluster description for the manifest (for the LLM and
    the public source page)."""
    summary = []
    for cluster in rank_clusters(clusters):
        summary.append({
            'cluster_id': cluster.id,
            'size': cluster.size,
            'total_score': round(cluster.total_score, 2),
            'domains': sorted(cluster.domains),
            'lead_title': cluster.sources[0].title if cluster.sources else '',
            'lead_url': cluster.sources[0].url if cluster.sources else '',
            'source_urls': [s.url for s in cluster.sources],
        })
    return summary
