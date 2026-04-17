"""LLM prompts for classification."""
from __future__ import annotations

from .taxonomy import taxonomy_description_for_prompt


SYSTEM_PROMPT = """Tu es un assistant spécialisé dans le classement de documents personnels \
et administratifs français. Tu dois classer chaque document dans UNE SEULE catégorie et \
sous-catégorie de la taxonomie fournie. Tu réponds TOUJOURS en JSON valide et uniquement en JSON."""


CLASSIFICATION_PROMPT_TEMPLATE = """Voici la taxonomie autorisée (tu DOIS choisir strictement dans cette liste) :

{taxonomy}

Document à classer :
- Nom de fichier : {filename}
- Extension : {extension}
- Extrait du contenu (tronqué) :
\"\"\"
{content}
\"\"\"

Instructions :
1. Détermine la catégorie de niveau 1 (slug exact parmi la liste).
2. Détermine la sous-catégorie de niveau 2 (slug exact dans les sous-catégories de la catégorie choisie).
3. Extrais l'année du document (AAAA) depuis le contenu si présente ; sinon null.
4. Propose un nom de fichier normalisé : "AAAA-MM-JJ_Emetteur_Objet.ext" (ASCII, underscores, pas d'espaces).
   - Si tu n'as pas la date exacte, utilise "AAAA_Emetteur_Objet.ext" ou juste "Emetteur_Objet.ext".
5. Donne un score de confiance entre 0 et 1 (0.95+ si tu es certain, 0.5 si ambigu, <0.5 si tu hésites vraiment).

Si le document ne correspond clairement à AUCUNE catégorie, mets confidence à 0 et category à "UNKNOWN".

Réponds UNIQUEMENT avec ce JSON (pas de texte avant/après) :
{{
  "category": "<slug niveau 1>",
  "subcategory": "<slug niveau 2>",
  "year": "<AAAA ou null>",
  "suggested_filename": "<nom.ext>",
  "project_name": "<null ou nom de projet si catégorie 15_Projets>",
  "confidence": <float>,
  "reasoning": "<1 phrase courte expliquant le choix>"
}}"""


def build_prompt(filename: str, extension: str, content: str) -> tuple[str, str]:
    user = CLASSIFICATION_PROMPT_TEMPLATE.format(
        taxonomy=taxonomy_description_for_prompt(),
        filename=filename,
        extension=extension,
        content=content or "(aucun texte extractible)",
    )
    return SYSTEM_PROMPT, user
