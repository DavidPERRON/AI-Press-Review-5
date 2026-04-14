import pytest

from ai_press_review.editorial.validate import (
    CLOSING_SENTENCE,
    REQUIRED_SECTION_KEYS,
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
