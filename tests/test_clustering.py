"""Unit tests for semantic clustering — exercise pure math paths
without calling the embedding API."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_press_review.editorial import clustering as clust_mod
from ai_press_review.editorial.clustering import (
    SourceCluster,
    _cosine,
    cluster_manifest_summary,
    cluster_sources,
    pick_representatives,
    rank_clusters,
    reduce_to_sources,
)
from ai_press_review.models import SourceItem


def _src(title: str, domain: str, score: float = 5.0, url: str | None = None) -> SourceItem:
    return SourceItem(
        url=url or f'https://{domain}/{title.lower().replace(" ", "-")}',
        title=title,
        domain=domain,
        summary=title,
        content_text=title,
        relevance_score=score,
    )


def test_cosine_basics():
    assert _cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert _cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert _cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert _cosine([0, 0], [1, 1]) == 0.0  # guards against zero norm


def test_cluster_sources_degrades_gracefully_without_embeddings():
    """When embed_texts returns None, each source becomes its own cluster."""
    sources = [_src('a', 'x.com'), _src('b', 'y.com'), _src('c', 'z.com')]
    with patch.object(clust_mod, 'embed_texts', return_value=None):
        clusters = cluster_sources(sources)
    assert len(clusters) == 3
    for cluster in clusters:
        assert cluster.size == 1


def test_cluster_sources_groups_similar_vectors():
    sources = [
        _src('OpenAI launches new model', 'openai.com', score=8.0),
        _src('OpenAI unveils latest release', 'reuters.com', score=7.0),  # similar
        _src('Google DeepMind publishes new paper', 'deepmind.com', score=6.0),  # different
        _src('Tesla reports quarterly earnings', 'tesla.com', score=5.0),  # different
    ]
    fake_vectors = [
        [1.0, 0.0, 0.0],  # OpenAI article 1
        [0.95, 0.05, 0.0],  # close to article 1 → same cluster
        [0.0, 1.0, 0.0],  # DeepMind → new cluster
        [0.0, 0.0, 1.0],  # Tesla → new cluster
    ]
    with patch.object(clust_mod, 'embed_texts', return_value=fake_vectors):
        clusters = cluster_sources(sources, threshold=0.9)

    assert len(clusters) == 3
    sizes = sorted(c.size for c in clusters)
    assert sizes == [1, 1, 2]

    # Largest cluster should aggregate the two OpenAI-related items.
    big = max(clusters, key=lambda c: c.size)
    titles = sorted(s.title for s in big.sources)
    assert titles == ['OpenAI launches new model', 'OpenAI unveils latest release']


def test_pick_representatives_prefers_domain_diversity():
    cluster = SourceCluster(id=0, sources=[
        _src('Story A', 'reuters.com', score=9.0),
        _src('Story A v2', 'reuters.com', score=8.5),  # same domain — should be dropped
        _src('Story A v3', 'ft.com', score=7.0),  # different domain — should be kept
        _src('Story A v4', 'bloomberg.com', score=6.5),  # different domain — should be kept
    ])
    picks = pick_representatives(cluster, k=3)
    domains = [s.domain for s in picks]
    assert len(set(domains)) == 3
    assert 'reuters.com' in domains  # highest-scored reuters kept, not both


def test_pick_representatives_tops_up_if_domain_diversity_insufficient():
    cluster = SourceCluster(id=0, sources=[
        _src('Story A', 'reuters.com', score=9.0),
        _src('Story A v2', 'reuters.com', score=8.0),
    ])
    picks = pick_representatives(cluster, k=3)
    # Only one domain available — we still pick both available sources.
    assert len(picks) == 2


def test_rank_clusters_by_total_score():
    c1 = SourceCluster(id=0, sources=[_src('a', 'x', score=3.0)])
    c2 = SourceCluster(id=1, sources=[
        _src('b', 'y', score=5.0),
        _src('c', 'z', score=4.0),
    ])
    c3 = SourceCluster(id=2, sources=[_src('d', 'w', score=10.0)])
    ranked = rank_clusters([c1, c2, c3])
    assert [c.id for c in ranked] == [2, 1, 0]


def test_reduce_to_sources_flattens_in_rank_order():
    c1 = SourceCluster(id=0, sources=[_src('low', 'a', score=1.0)])
    c2 = SourceCluster(id=1, sources=[
        _src('hi1', 'b', score=10.0),
        _src('hi2', 'c', score=9.0),
    ])
    flat = reduce_to_sources([c1, c2], k_per_cluster=2)
    # c2 ranks first (higher total), then c1.
    assert flat[0].title == 'hi1'
    assert flat[1].title == 'hi2'
    assert flat[2].title == 'low'


def test_cluster_manifest_summary_shape():
    c = SourceCluster(id=0, sources=[
        _src('A', 'reuters.com', score=8.0),
        _src('A bis', 'ft.com', score=6.0),
    ])
    summary = cluster_manifest_summary([c])
    assert len(summary) == 1
    entry = summary[0]
    assert entry['size'] == 2
    assert entry['total_score'] == 14.0
    assert set(entry['domains']) == {'reuters.com', 'ft.com'}
    assert entry['lead_title'] == 'A'
