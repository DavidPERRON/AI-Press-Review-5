import pytest

from ai_press_review.editorial.validate import (
    CLOSING_SENTENCE,
    CLOSING_SENTENCES_BY_LOCALE,
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


# --- FR locale tests -------------------------------------------------------
# Regression coverage for the 2026-04-15 bug where FR episodes were generated
# with an English opening ("Your Daily AI Press Review — April 15, 2026")
# and an English closing paragraph. The TTS voice drifted mid-sentence because
# a FR Cartesia voice was asked to read English prose.


def test_build_intro_line_fr_daily():
    line = build_intro_line("2026-04-15", "En bref", locale='fr')
    assert line == "Votre Revue de Presse IA du jour — 15 avril 2026: En bref."


def test_build_intro_line_fr_weekly():
    line = build_intro_line("2026-04-15", "En bref", intro_format='weekly', locale='fr')
    assert line == "Votre Revue de Presse IA hebdo — semaine du 15 avril 2026: En bref."


def test_build_intro_line_unknown_locale_falls_back_to_en():
    # Defensive: bad locale strings shouldn't crash the pipeline mid-publish.
    line = build_intro_line("2026-04-15", "Highlights", locale='zz')
    assert line.startswith("Your Daily AI Press Review")


def test_assemble_script_fr_uses_french_closing():
    script = assemble_script("2026-04-15", _make_payload(), locale='fr')
    assert script.startswith("Votre Revue de Presse IA du jour")
    assert CLOSING_SENTENCES_BY_LOCALE['fr'] in script
    # And critically: the EN closing must NOT leak into a FR script.
    assert CLOSING_SENTENCES_BY_LOCALE['en'] not in script


def test_validate_final_script_rejects_en_closing_in_fr_script():
    intro = "Votre Revue de Presse IA du jour — 15 avril 2026: Test."
    body = "Un paragraphe de contenu narratif en français."
    script = (
        f"{intro}\n\n{body}\n\n{body}\n\n"
        f"{CLOSING_SENTENCES_BY_LOCALE['en']}\n\nQu'est-ce que l'inférence."
    )
    with pytest.raises(ValueError, match="Closing sentence"):
        validate_final_script(script, locale='fr')
