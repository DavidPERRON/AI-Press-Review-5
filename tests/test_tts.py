import pytest

from ai_press_review.tts.cartesia import normalize_pronunciations, split_script


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


def test_normalize_pronunciations_en_rewrites_known_acronyms():
    text = "Transformers like BERT beat LaTeX on arXiv benchmarks."
    out = normalize_pronunciations(text, 'en')
    assert 'BERT' not in out
    assert 'LaTeX' not in out
    assert 'arXiv' not in out
    assert 'Burt' in out
    assert 'Lay-Tech' in out
    assert 'ar-kive' in out


def test_normalize_pronunciations_preserves_unrelated_text():
    text = "OpenAI released GPT-5.4 alongside SOLARIS and GPU upgrades."
    out = normalize_pronunciations(text, 'en')
    # SOLARIS/GPU are not in the dictionary → stay untouched
    assert out == text


def test_normalize_pronunciations_word_boundary():
    # A token that merely *contains* BERT must stay untouched (no false hit).
    text = "ROBERTA and ALBERT are related models."
    out = normalize_pronunciations(text, 'en')
    assert out == text


def test_normalize_pronunciations_fr_uses_french_table():
    text = "Les transformeurs comme BERT utilisent LaTeX."
    out = normalize_pronunciations(text, 'fr')
    assert 'BERT' not in out
    assert 'LaTeX' not in out
    assert 'Beurt' in out
    assert 'La-Tek' in out


def test_normalize_pronunciations_default_locale_is_english():
    text = "BERT model."
    assert normalize_pronunciations(text, '') == "Burt model."
    assert normalize_pronunciations(text, 'en') == normalize_pronunciations(text, '')


# FR pause hints: Cartesia's native sentence-end pauses were compressing to
# near-imperceptible on full episodes, so we insert an ellipsis at sentence
# boundaries. These tests lock the regex against common false positives —
# French abbreviations and alternate sentence-end punctuation.


def test_fr_pause_hints_basic_sentence_boundary():
    text = "C'est vrai. Le modele est solide."
    out = normalize_pronunciations(text, 'fr')
    assert out == "C'est vrai... Le modele est solide."


def test_fr_pause_hints_skip_monsieur_abbreviation():
    # "M. Dupont" must NOT be split — single uppercase before the period
    # signals an abbreviation, not a sentence end.
    text = "L'annonce de M. Dupont concerne Paris."
    out = normalize_pronunciations(text, 'fr')
    assert "M... Dupont" not in out
    assert "M. Dupont" in out


def test_fr_pause_hints_apply_after_abbreviation_at_sentence_end():
    # Sentence ends with lowercase word before the period → should be split
    # even when the prior sentence contains an abbreviation.
    text = "L'annonce de M. Dupont est confirmee. Le ministre reagit."
    out = normalize_pronunciations(text, 'fr')
    assert "M. Dupont" in out  # abbreviation preserved
    assert "confirmee... Le ministre" in out  # true sentence boundary hit


def test_fr_pause_hints_preserve_question_and_exclamation():
    text = "Est-ce vrai? Le benchmark confirme. Excellent! Le resultat tient."
    out = normalize_pronunciations(text, 'fr')
    # ? and ! carry their own prosody — we do not add ellipsis there
    assert "vrai? Le" in out
    assert "Excellent! Le" in out
    # But the "confirme. Excellent" boundary gets the hint
    assert "confirme... Excellent" in out


def test_fr_pause_hints_digit_ending_sentence():
    text = "Le score atteint 95.5. La difference est reelle."
    out = normalize_pronunciations(text, 'fr')
    # Decimal "95.5" must stay intact; only the terminal "5. L" splits
    assert "95.5" in out
    assert "95.5... La difference" in out


def test_fr_pause_hints_accented_word_ending():
    text = "Le projet est acheve. Ensuite, on pivote."
    out = normalize_pronunciations(text, 'fr')
    assert "acheve... Ensuite" in out


def test_fr_pause_hints_composes_with_pronunciation_rewrite():
    # "arXiv" → "ar-kive", and the sentence boundary after it should still fire
    text = "Le papier arXiv. Le laboratoire confirme."
    out = normalize_pronunciations(text, 'fr')
    assert "ar-kive... Le laboratoire" in out


def test_fr_pause_hints_do_not_apply_to_en():
    # EN path must remain unchanged — this is the regression guard for users
    # who never touch FR content.
    text = "Sentence one. Sentence two."
    out = normalize_pronunciations(text, 'en')
    assert out == text
