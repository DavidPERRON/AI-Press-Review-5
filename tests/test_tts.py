import pytest

from ai_press_review.tts.cartesia import split_script


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
