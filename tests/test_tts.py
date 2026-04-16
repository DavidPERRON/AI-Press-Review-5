import pytest

from ai_press_review.tts.cartesia import (
    _normalize_tts_whitespace,
    _strip_trailing_pause_tokens,
    normalize_pronunciations,
    split_script,
)


def test_split_script_single_short():
    chunks = split_script("Hello world.")
    assert len(chunks) == 1
    assert chunks[0] == "Hello world."


def test_split_script_respects_max_chars():
    paragraphs = ["A" * 500 for _ in range(5)]
    text = "\n\n".join(paragraphs)
    chunks = split_script(text, max_chars=1200)
    for chunk in chunks:
        assert len(chunk) <= 1200


def test_split_script_preserves_all_content():
    paragraphs = [f"Paragraph {i} content." for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = split_script(text)
    reassembled = "\n\n".join(chunks)
    for p in paragraphs:
        assert p in reassembled


def test_split_script_empty():
    assert split_script("") == []
    assert split_script("   ") == []


def test_split_script_single_long_paragraph():
    long_para = "Word " * 1000
    chunks = split_script(long_para.strip(), max_chars=1800)
    assert len(chunks) == 1
    assert chunks[0] == long_para.strip()


# ─── Acronym normalization (EN) ───────────────────────────────────────────────

def test_normalize_pronunciations_en_rewrites_legacy_acronyms():
    text = "Transformers like BERT beat LaTeX on arXiv benchmarks."
    out = normalize_pronunciations(text, 'en')
    assert 'BERT' not in out
    assert 'LaTeX' not in out
    assert 'arXiv' not in out
    assert 'Burt' in out
    assert 'Lay-Tech' in out
    assert 'ar-kive' in out


def test_normalize_pronunciations_en_spells_initialisms_with_dots():
    # Letter-by-letter acronyms get spaced-and-dotted form so Cartesia treats
    # each letter as its own beat instead of slurring them into a pseudo-word.
    text = "TSMC reported strong demand from CEO and CTO."
    out = normalize_pronunciations(text, 'en')
    assert 'TSMC' not in out
    assert 'T. S. M. C.' in out
    assert 'C. E. O.' in out
    assert 'C. T. O.' in out


def test_normalize_pronunciations_en_handles_gpt_and_api_and_llm():
    text = "GPT and the API for an LLM cost a lot of GPU time."
    out = normalize_pronunciations(text, 'en')
    assert 'G. P. T.' in out
    assert 'A. P. I.' in out
    assert 'L. L. M.' in out
    assert 'G. P. U.' in out


def test_normalize_pronunciations_en_handles_word_form_acronyms():
    text = "NVIDIA shipped chips to NASA for the OpenAI cluster."
    out = normalize_pronunciations(text, 'en')
    assert 'NVIDIA' not in out
    assert 'en-vidia' in out
    # NASA stays as 'NASA' (pronounced as a word natively)
    assert 'NASA' in out
    assert 'OpenAI' not in out
    assert 'Open A. I.' in out


def test_normalize_pronunciations_en_handles_ipo_usa_uk():
    text = "The IPO closed in the USA, with secondary listing in the UK."
    out = normalize_pronunciations(text, 'en')
    assert 'I. P. O.' in out
    assert 'U. S. A.' in out
    assert 'U. K.' in out


def test_normalize_pronunciations_en_handles_plural_s():
    # Plural forms (GPUs, APIs, LLMs, URLs, PDFs) keep their trailing s but the
    # letters are still spelled.
    text = "Compare the GPUs, APIs, and LLMs in those PDFs."
    out = normalize_pronunciations(text, 'en')
    assert 'G. P. U. s' in out
    assert 'A. P. I. s' in out
    assert 'L. L. M. s' in out
    assert 'P. D. F. s' in out


def test_normalize_pronunciations_preserves_unrelated_text():
    # Unknown acronyms and tokens that merely contain a known acronym must
    # stay untouched. The \b boundary prevents NASAQ → "NASAQ" from matching
    # NASA, and "GPU-friendly" from matching the GPU rule incorrectly.
    text = "SOLARIS launched after Meta's announcement."
    out = normalize_pronunciations(text, 'en')
    assert out == text


def test_normalize_pronunciations_word_boundary_no_false_hits():
    # ROBERTA / ALBERT / BERTHA contain BERT as a substring but must not match
    text = "ROBERTA and ALBERT and BERTHA are unrelated."
    out = normalize_pronunciations(text, 'en')
    assert out == text


def test_normalize_pronunciations_word_boundary_hyphenated_token():
    # GPU-friendly: ripgrep-style \b lets the GPU rule fire here, which is
    # what we want — the engine should still spell "G. P. U." inside compounds.
    text = "A GPU-friendly architecture."
    out = normalize_pronunciations(text, 'en')
    assert 'G. P. U.' in out


# ─── Acronym normalization (FR) ───────────────────────────────────────────────

def test_normalize_pronunciations_fr_rewrites_legacy_acronyms():
    text = "Les transformeurs comme BERT utilisent LaTeX."
    out = normalize_pronunciations(text, 'fr')
    assert 'BERT' not in out
    assert 'LaTeX' not in out
    assert 'Beurt' in out
    assert 'La-Tek' in out


def test_normalize_pronunciations_fr_handles_french_acronyms():
    text = "Le PDG de la PME annonce une IA pour l'UE."
    out = normalize_pronunciations(text, 'fr')
    assert 'P. D. G.' in out
    assert 'P. M. E.' in out
    assert 'I. A.' in out
    assert 'U. E.' in out


def test_normalize_pronunciations_fr_handles_shared_acronyms():
    # Common acronyms (TSMC, GPT, CEO) must use the same dotted form in FR.
    text = "TSMC fournit des puces, le CEO d'OpenAI le confirme via GPT."
    out = normalize_pronunciations(text, 'fr')
    assert 'T. S. M. C.' in out
    assert 'C. E. O.' in out
    assert 'Open A. I.' in out
    assert 'G. P. T.' in out


def test_normalize_pronunciations_default_locale_is_english():
    text = "BERT model."
    assert normalize_pronunciations(text, '') == "Burt model."
    assert normalize_pronunciations(text, 'en') == normalize_pronunciations(text, '')


def test_normalize_pronunciations_no_longer_inserts_fr_pause_hints():
    # 2026-04-16 regression guard: previously every ". " in FR became "... "
    # which produced an audible drum-roll of pauses. Now the FR text passes
    # through unchanged at sentence boundaries — Cartesia's native prosody
    # at speed 0.82 carries the breath without manual hints.
    text = "C'est vrai. Le modele est solide."
    out = normalize_pronunciations(text, 'fr')
    assert "..." not in out
    assert out == "C'est vrai. Le modele est solide."


def test_normalize_pronunciations_fr_does_not_break_abbreviations():
    text = "L'annonce de M. Dupont concerne Paris."
    out = normalize_pronunciations(text, 'fr')
    assert "M. Dupont" in out
    assert "M..." not in out


# ─── Whitespace normalization ─────────────────────────────────────────────────

def test_normalize_tts_whitespace_collapses_double_spaces():
    assert _normalize_tts_whitespace("a  b") == "a b"
    assert _normalize_tts_whitespace("a   b   c") == "a b c"


def test_normalize_tts_whitespace_strips_trailing_line_whitespace():
    assert _normalize_tts_whitespace("line a   \nline b") == "line a\nline b"


def test_normalize_tts_whitespace_caps_blank_lines():
    text = "para 1\n\n\n\npara 2\n\n\n\n\npara 3"
    out = _normalize_tts_whitespace(text)
    assert "\n\n\n" not in out
    assert "para 1\n\npara 2\n\npara 3" == out


def test_normalize_tts_whitespace_trims_overall():
    assert _normalize_tts_whitespace("  hello\n\n") == "hello"


# ─── Trailing pause cleanup ───────────────────────────────────────────────────

def test_strip_trailing_pause_tokens_removes_ellipsis():
    assert _strip_trailing_pause_tokens("Done...") == "Done."
    assert _strip_trailing_pause_tokens("Done.....") == "Done."


def test_strip_trailing_pause_tokens_removes_dangling_dot():
    assert _strip_trailing_pause_tokens("Done . ") == "Done."
    assert _strip_trailing_pause_tokens("Done.\n") == "Done."


def test_strip_trailing_pause_tokens_preserves_clean_ending():
    assert _strip_trailing_pause_tokens("Done.") == "Done."
    assert _strip_trailing_pause_tokens("Are we done?") == "Are we done?"
    assert _strip_trailing_pause_tokens("Excellent!") == "Excellent!"


def test_strip_trailing_pause_tokens_internal_ellipsis_untouched():
    # An ellipsis inside the text (not at the very end) is left alone — only
    # the final-position run gets normalized to a single period.
    assert _strip_trailing_pause_tokens("Wait... here we go.") == "Wait... here we go."
