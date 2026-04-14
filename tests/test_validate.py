import pytest

from ai_press_review.editorial.validate import (
    CLOSING_SENTENCE,
    DEFAULT_CLOSING_SENTENCE,
    EXPECTED_SECTION_COUNTS,
    REQUIRED_SECTION_KEYS,
    SECTION_COUNT_TOLERANCE,
    assemble_script,
    build_intro_line,
    validate_final_script,
    validate_section_payload,
)


def _make_payload(overrides=None):
    base = {
        "highlights_label": "Highlights",
        "tomorrow_pedagogical_concept": "What is inference",
        "sections": {
            "ai_news": ["OpenAI launched a new model today with significant performance gains." * 2] * 4,
            "use_cases_and_deployments": ["Banks are deploying AI agents for customer service automation." * 2] * 3,
            "tools_and_practice": ["New developer tools simplify fine-tuning of large language models." * 2] * 3,
            "weak_signals_and_trends": ["Experts observe a shift toward smaller more efficient models." * 2] * 2,
            "research_and_breakthroughs": ["A new paper demonstrates improved reasoning in language models." * 2] * 3,
            "education_and_pedagogy": ["Retrieval augmented generation combines search with text generation." * 2] * 2,
        },
    }
    if overrides:
        base.update(overrides)
    return base


def test_build_intro_line():
    line = build_intro_line("2026-04-12", "Highlights")
    assert line == "Your Daily AI Press Review — April 12, 2026: Highlights."


def test_build_intro_line_empty_label():
    line = build_intro_line("2026-01-01", "")
    assert "Highlights" in line


def test_validate_section_payload_valid():
    validate_section_payload(_make_payload())


def test_validate_section_payload_missing_section():
    payload = _make_payload()
    del payload["sections"]["ai_news"]
    with pytest.raises(ValueError, match="Section order"):
        validate_section_payload(payload)


def test_validate_section_payload_empty_paragraphs():
    payload = _make_payload()
    payload["sections"]["ai_news"] = []
    with pytest.raises(ValueError, match="Missing section content"):
        validate_section_payload(payload)


def test_validate_section_payload_missing_tomorrow():
    payload = _make_payload({"tomorrow_pedagogical_concept": ""})
    with pytest.raises(ValueError, match="Tomorrow pedagogical concept is missing"):
        validate_section_payload(payload)


def test_validate_section_payload_tomorrow_too_long():
    payload = _make_payload({"tomorrow_pedagogical_concept": " ".join(["word"] * 15)})
    with pytest.raises(ValueError, match="too long"):
        validate_section_payload(payload)


def test_assemble_script_produces_valid_output():
    script = assemble_script("2026-04-12", _make_payload())
    assert script.startswith("Your Daily AI Press Review")
    assert CLOSING_SENTENCE in script
    assert script.endswith(".")


def test_assemble_script_accepts_dict_paragraphs():
    """Some LLMs (notably Claude) emit each paragraph as {'text': '...'}
    instead of a plain string. The assembler must coerce rather than crash.
    """
    payload = _make_payload()
    sample_text = "OpenAI launched a new model today with significant performance gains." * 2
    payload["sections"]["ai_news"] = [{"text": sample_text}] * 4
    script = assemble_script("2026-04-12", payload)
    assert sample_text.strip() in script


def test_assemble_script_accepts_content_keyed_dict_paragraphs():
    payload = _make_payload()
    sample_text = "Banks are deploying AI agents for customer service automation." * 2
    payload["sections"]["use_cases_and_deployments"] = [{"content": sample_text}] * 3
    script = assemble_script("2026-04-12", payload)
    assert sample_text.strip() in script


def test_validate_final_script_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_final_script("")


def test_validate_final_script_rejects_bullets():
    intro = "Your Daily AI Press Review — April 12, 2026: Test."
    body = "Some paragraph content here for the body."
    bullet = "- This is a bullet point"
    script = f"{intro}\n\n{body}\n\n{bullet}\n\n{CLOSING_SENTENCE}\n\nWhat is inference."
    with pytest.raises(ValueError, match="Bullet points"):
        validate_final_script(script)


def test_validate_final_script_rejects_headings():
    intro = "Your Daily AI Press Review — April 12, 2026: Test."
    body = "Some paragraph content here for the body."
    heading = "This ends with a colon:"
    script = f"{intro}\n\n{body}\n\n{heading}\n\n{CLOSING_SENTENCE}\n\nWhat is inference."
    with pytest.raises(ValueError, match="Heading-style"):
        validate_final_script(script)


# Phase 5 / E1: section count ±2 flex


def test_section_count_tolerance_accepts_expected_minus_tolerance():
    """A section at its expected count minus tolerance should pass."""
    payload = _make_payload()
    # ai_news expected=5, tolerance=2 → min allowed = 3
    payload["sections"]["ai_news"] = [
        "OpenAI launched a new model today with significant performance gains." * 2
    ] * 3
    validate_section_payload(payload)


def test_section_count_tolerance_rejects_too_many():
    """A section above expected+tolerance should fail."""
    payload = _make_payload()
    # tools_and_practice expected=3, tolerance=2 → max allowed = 5, so 6 fails
    payload["sections"]["tools_and_practice"] = [
        "New developer tools simplify fine-tuning of large language models." * 2
    ] * 6
    with pytest.raises(ValueError, match="paragraphs; expected"):
        validate_section_payload(payload)


def test_section_count_tolerance_rejects_too_few():
    """A section below expected-tolerance should fail (floor at 1)."""
    payload = _make_payload()
    # ai_news expected=5, tolerance=2 → min allowed = 3, so 2 fails
    payload["sections"]["ai_news"] = [
        "OpenAI launched a new model today with significant performance gains." * 2
    ] * 2
    with pytest.raises(ValueError, match="paragraphs; expected"):
        validate_section_payload(payload)


def test_expected_section_counts_cover_all_required_keys():
    """Sanity: the EXPECTED_SECTION_COUNTS map aligns with REQUIRED_SECTION_KEYS."""
    assert set(EXPECTED_SECTION_COUNTS.keys()) == set(REQUIRED_SECTION_KEYS)
    assert SECTION_COUNT_TOLERANCE == 2


# Phase 5 / B4: closing sentence is configurable via assemble_script parameter


def test_assemble_script_uses_default_closing_when_not_provided():
    script = assemble_script("2026-04-12", _make_payload())
    assert DEFAULT_CLOSING_SENTENCE in script


def test_assemble_script_honours_custom_closing():
    custom = "This is a custom closing line for regression testing."
    script = assemble_script("2026-04-12", _make_payload(), closing_sentence=custom)
    assert custom in script
    assert DEFAULT_CLOSING_SENTENCE not in script


def test_validate_final_script_honours_custom_closing():
    intro = "Your Daily AI Press Review — April 12, 2026: Test."
    body = "Some paragraph content here for the body."
    custom_closing = "This is a custom closing line for regression testing."
    script = f"{intro}\n\n{body}\n\n{custom_closing}\n\nWhat is inference."
    validate_final_script(script, closing_sentence=custom_closing)


def test_validate_final_script_rejects_mismatched_closing():
    intro = "Your Daily AI Press Review — April 12, 2026: Test."
    body = "Some paragraph content here for the body."
    script = f"{intro}\n\n{body}\n\nWrong closing line.\n\nWhat is inference."
    with pytest.raises(ValueError, match="Closing sentence"):
        validate_final_script(script, closing_sentence="Expected closing line.")
