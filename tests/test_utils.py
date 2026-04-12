from ai_press_review.utils import (
    clean_text,
    domain_from_url,
    fingerprint,
    normalize_title,
    normalize_url,
    safe_slug,
    title_similarity,
    within_hours,
)


def test_clean_text_collapses_whitespace():
    assert clean_text("  hello   world  ") == "hello world"


def test_clean_text_empty():
    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_normalize_url_strips_query_and_fragment():
    url = "https://example.com/page?ref=abc#section"
    assert normalize_url(url) == "https://example.com/page"


def test_domain_from_url():
    assert domain_from_url("https://www.example.com/page") == "example.com"
    assert domain_from_url("https://blog.google/ai") == "blog.google"


def test_normalize_title():
    assert normalize_title("Hello, World! (2024)") == "hello world 2024"


def test_title_similarity_identical():
    assert title_similarity("OpenAI launches GPT-5", "OpenAI launches GPT-5") == 1.0


def test_title_similarity_different():
    assert title_similarity("OpenAI launches GPT-5", "NVIDIA releases new chip") < 0.5


def test_title_similarity_similar():
    assert title_similarity("OpenAI launches GPT-5", "OpenAI has launched GPT-5 model") > 0.7


def test_fingerprint_deterministic():
    fp1 = fingerprint("title", "https://example.com")
    fp2 = fingerprint("title", "https://example.com")
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_different_inputs():
    fp1 = fingerprint("title a", "https://a.com")
    fp2 = fingerprint("title b", "https://b.com")
    assert fp1 != fp2


def test_safe_slug():
    assert safe_slug("Hello World! (2024)") == "hello-world-2024"
    assert len(safe_slug("a" * 200)) <= 80


def test_within_hours_no_value():
    assert within_hours(None, 48) is True
    assert within_hours("", 48) is True


def test_within_hours_recent():
    from datetime import datetime, timezone
    recent = datetime.now(timezone.utc).isoformat()
    assert within_hours(recent, 48) is True
