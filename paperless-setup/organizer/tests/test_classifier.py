from mac_organizer.classifier import (
    parse_json_response, sanitize_filename, validate_and_clean,
)
from mac_organizer.taxonomy import UNCLASSIFIED_CATEGORY


def test_parse_clean_json():
    r = parse_json_response('{"a": 1}')
    assert r == {"a": 1}


def test_parse_fenced_json():
    r = parse_json_response('```json\n{"a": 1}\n```')
    assert r == {"a": 1}


def test_parse_embedded_json():
    r = parse_json_response('Voici ma réponse: {"a": 1} merci.')
    assert r == {"a": 1}


def test_sanitize_filename():
    assert sanitize_filename("hello world.pdf", "x.pdf") == "hello_world.pdf"
    # Leading dot stripped -> fallback (defensive)
    assert sanitize_filename("..évil/../path.pdf", "fallback.pdf") == "fallback.pdf"
    assert sanitize_filename("", "fallback.pdf") == "fallback.pdf"
    # Accents removed, structure kept
    assert sanitize_filename("Facture Énergie 2024.pdf", "x.pdf") == "Facture_nergie_2024.pdf"


def test_validate_valid():
    resp = {
        "category": "02_Logement",
        "subcategory": "Contrats",
        "year": "2024",
        "suggested_filename": "2024-01-15_EDF_Facture.pdf",
        "confidence": 0.95,
    }
    r = validate_and_clean(resp, "x.pdf", 0.85)
    assert r["valid"] is True
    assert r["category"] == "02_Logement"
    assert r["year"] == "2024"


def test_validate_low_confidence():
    resp = {
        "category": "02_Logement",
        "subcategory": "Contrats",
        "confidence": 0.5,
    }
    r = validate_and_clean(resp, "x.pdf", 0.85)
    assert r["valid"] is False
    assert r["category"] == UNCLASSIFIED_CATEGORY


def test_validate_bad_subcategory():
    resp = {
        "category": "02_Logement",
        "subcategory": "DoesNotExist",
        "confidence": 0.99,
    }
    r = validate_and_clean(resp, "x.pdf", 0.85)
    assert r["valid"] is False


def test_validate_bad_year():
    resp = {
        "category": "02_Logement",
        "subcategory": "Contrats",
        "year": "not-a-year",
        "confidence": 0.95,
    }
    r = validate_and_clean(resp, "x.pdf", 0.85)
    assert r["year"] is None
