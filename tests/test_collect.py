from ai_press_review.collect import (
    _ai_relevance_score,
    _contains_banned_topic,
    _is_duplicate_of_previous,
    _score_source,
)
from ai_press_review.models import SourceItem


def _make_source(**kwargs) -> SourceItem:
    defaults = {
        "url": "https://example.com/article",
        "title": "AI model achieves new benchmark",
        "domain": "example.com",
        "published_at": "2026-04-12T10:00:00Z",
        "summary": "A new AI model has set records on major benchmarks.",
        "content_text": "Detailed article content about AI advances " * 50,
    }
    defaults.update(kwargs)
    return SourceItem(**defaults)


def test_contains_banned_topic_positive():
    assert _contains_banned_topic("New AI regulation policy announced") is True


def test_contains_banned_topic_negative():
    assert _contains_banned_topic("OpenAI launches new model") is False


def test_ai_relevance_high():
    score = _ai_relevance_score(["artificial intelligence breakthrough"])
    assert score >= 3.0


def test_ai_relevance_none():
    score = _ai_relevance_score(["cooking recipe for pasta"])
    assert score == 0.0


def test_score_source_rich_content():
    item = _make_source(content_text="benchmark launch funding deploy " * 100)
    score = _score_source(item)
    assert score >= 5.0


def test_score_source_poor_content():
    item = _make_source(
        title="random news story",
        content_text="short",
        summary="short",
    )
    score = _score_source(item)
    assert score < 5.0


def test_score_source_domain_authority():
    item_auth = _make_source(domain="openai.com")
    item_unknown = _make_source(domain="randomsite.xyz")
    assert _score_source(item_auth) > _score_source(item_unknown)


def test_is_duplicate_fingerprint():
    item = _make_source()
    from ai_press_review.utils import fingerprint
    fp = fingerprint(item.title, item.url)
    assert _is_duplicate_of_previous(item, {fp}, [], []) is True


def test_is_duplicate_similar_title():
    item = _make_source(title="OpenAI launches GPT-5 model")
    assert _is_duplicate_of_previous(item, set(), ["OpenAI launches GPT-5 model today"], []) is True


def test_not_duplicate():
    item = _make_source(title="NVIDIA releases new chip")
    assert _is_duplicate_of_previous(item, set(), ["OpenAI launches GPT-5"], []) is False
