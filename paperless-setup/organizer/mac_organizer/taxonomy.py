"""
Taxonomie fermée — max 3 niveaux.

Principe : l'IA doit choisir dans un ensemble FIXE de catégories/sous-catégories.
Cela garantit la reproductibilité et une fiabilité >95% (pas de variations
"Factures" vs "Facture" vs "Bills" d'un run à l'autre).

Niveau 1 : grand thème (17 catégories)
Niveau 2 : sous-thème (2-4 par catégorie)
Niveau 3 : année (AAAA) pour docs datés, nom projet pour Projets, optionnel ailleurs
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Category:
    slug: str
    label: str
    subcategories: tuple[str, ...]
    use_year: bool = True
    description: str = ""


TAXONOMY: tuple[Category, ...] = (
    Category(
        "01_Identite", "Identité",
        ("Officiel", "Diplomes_Certifications"),
        use_year=False,
        description="CNI, passeport, permis, carte vitale, livret de famille, diplômes.",
    ),
    Category(
        "02_Logement", "Logement",
        ("Contrats", "Factures_Charges", "Assurance", "Travaux"),
        description="Bail, propriété, EDF/eau/gaz, syndic, assurance habitation, travaux.",
    ),
    Category(
        "03_Finances", "Finances",
        ("Banque", "Credits", "Epargne_Placements", "Impots"),
        description="Relevés, cartes, crédits, épargne, avis et déclarations d'impôts.",
    ),
    Category(
        "04_Travail", "Travail",
        ("Contrats", "Salaires", "Attestations", "PoleEmploi"),
        description="Contrats de travail, bulletins de salaire, attestations, Pôle Emploi.",
    ),
    Category(
        "05_Sante", "Santé",
        ("Remboursements", "Ordonnances_Analyses", "Mutuelle"),
        description="Remboursements CPAM, ordonnances, analyses, mutuelle santé.",
    ),
    Category(
        "06_Vehicule", "Véhicule",
        ("Administratif", "Assurance", "Entretien"),
        description="Carte grise, contrôle technique, assurance auto, entretien.",
    ),
    Category(
        "07_Famille", "Famille",
        ("Enfants", "Animaux", "Successions"),
        use_year=False,
        description="Scolarité/santé enfants, animaux, successions.",
    ),
    Category(
        "08_Abonnements", "Abonnements",
        ("Telecom_Internet", "Streaming_Medias", "Logiciels"),
        description="Téléphone, internet, streaming, logiciels SaaS.",
    ),
    Category(
        "09_Achats_Garanties", "Achats & garanties",
        ("Factures_Garanties", "Notices"),
        description="Factures produits, garanties, notices.",
    ),
    Category(
        "10_Juridique", "Juridique",
        ("Contrats", "Litiges_Courriers"),
        description="Contrats divers, litiges, courriers recommandés.",
    ),
    Category(
        "11_Voyages", "Voyages",
        ("Reservations_Billets", "Visas_Documents"),
        description="Billets, réservations, visas, documents de voyage.",
    ),
    Category(
        "12_Photos", "Photos",
        ("Personnel",),
        description="Photos personnelles — classées par année via EXIF, pas via LLM.",
    ),
    Category(
        "13_Videos", "Vidéos",
        ("Personnel",),
        description="Vidéos personnelles — classées par année via métadonnées.",
    ),
    Category(
        "14_Medias", "Médias",
        ("Musique", "Ebooks", "Divers"),
        use_year=False,
        description="Musique, ebooks, autres médias non-photos.",
    ),
    Category(
        "15_Projets", "Projets",
        ("Actif", "Archive"),
        use_year=False,
        description="Projets personnels ou pro avec sous-dossier par projet.",
    ),
    Category(
        "16_Personnel", "Personnel",
        ("Correspondance", "Notes"),
        description="Correspondance privée, notes, divers personnels.",
    ),
    Category(
        "17_Travail_Fichiers", "Fichiers de travail",
        ("Bureautique", "Presentations", "Donnees"),
        use_year=False,
        description="Documents pro non-administratifs : bureautique, présentations, data.",
    ),
)

DUPLICATES_CATEGORY = "00_Doublons"
UNCLASSIFIED_CATEGORY = "99_NonClasse"

CATEGORIES_BY_SLUG: dict[str, Category] = {c.slug: c for c in TAXONOMY}


def allowed_category_slugs() -> list[str]:
    return [c.slug for c in TAXONOMY]


def allowed_subcategories(category_slug: str) -> list[str]:
    cat = CATEGORIES_BY_SLUG.get(category_slug)
    return list(cat.subcategories) if cat else []


def taxonomy_description_for_prompt() -> str:
    lines = []
    for cat in TAXONOMY:
        subs = " | ".join(cat.subcategories)
        lines.append(f"- {cat.slug} ({cat.label}): {cat.description} Sous-catégories: [{subs}]")
    return "\n".join(lines)


def validate_classification(category: str, subcategory: str) -> bool:
    if category not in CATEGORIES_BY_SLUG:
        return False
    return subcategory in CATEGORIES_BY_SLUG[category].subcategories
