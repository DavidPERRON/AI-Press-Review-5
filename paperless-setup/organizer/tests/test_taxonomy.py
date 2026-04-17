from mac_organizer.taxonomy import (
    TAXONOMY, validate_classification, allowed_category_slugs,
    CATEGORIES_BY_SLUG,
)


def test_taxonomy_has_17_categories():
    assert len(TAXONOMY) == 17


def test_slugs_unique():
    slugs = allowed_category_slugs()
    assert len(slugs) == len(set(slugs))


def test_slugs_prefixed_with_digits():
    for c in TAXONOMY:
        assert c.slug[:2].isdigit(), c.slug


def test_validate_ok():
    assert validate_classification("02_Logement", "Contrats")


def test_validate_wrong_sub():
    assert not validate_classification("02_Logement", "Banque")


def test_validate_unknown_cat():
    assert not validate_classification("foo", "bar")


def test_all_cats_have_subs():
    for c in TAXONOMY:
        assert len(c.subcategories) >= 1
