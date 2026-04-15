# HANDOFF — Périmètre site vitrine vs backend éditorial

**Date** : 2026-04-15
**Auteur** : Claude (instance backend, branche `stage4/fr-production` mergée sur `main`)
**Destinataire** : Claude (instance site, branche `claude/resume-seo-visibility-SIXI6`)

---

## Décision propriétaire (David Perron)

> « le site doit être une vitrine pas de code autre »
> « il sont maître » (sur les narratifs)

Donc :
- **Tu es maître** sur la vitrine (HTML/CSS/contenu narratif des pages publiques).
- **Je suis maître** sur le backend éditorial (pipeline, prompts, settings, RSS, TTS).
- Tu peux toucher au RSS **uniquement** pour les champs SEO/transcripts/Podcasting 2.0 si tu réémets clairement le brief — mais en PR séparée.

---

## Ce qui est dans ton périmètre (à garder / merger)

Pages publiques et assets statiques :

- `docs/index.html`
- `docs/how-it-works.html`
- `docs/fr/index.html`
- `docs/fr/how-it-works.html`
- `docs/fr/podcast-feed.xml` *(s'il s'agit d'un placeholder statique — sinon c'est généré côté backend, voir plus bas)*
- `docs/robots.txt`
- `docs/sitemap.xml`
- `preview-site.html`, `preview-site-fr.html`
- `preview-how-it-works.html`, `preview-how-it-works-fr.html`
- `preview-standalone.html`
- Tout asset `assets/site/*` que tu ajoutes

Note : les narratifs FR de tes pages doivent être en français professionnel adapté, pas une traduction littérale. Ce point est validé.

---

## Ce qui est HORS périmètre (à dégager de ta branche)

Ces fichiers ont été modifiés ou créés sur ta branche mais relèvent du backend éditorial. **Reverte-les** vers l'état actuel de `main` (commit `9600233`) :

### Backend éditorial (purement out-of-scope)

- `src/ai_press_review/editorial/clustering.py` *(nouveau, 271 lignes)*
- `src/ai_press_review/editorial/grounding.py` *(nouveau, 220 lignes)*
- `src/ai_press_review/editorial/passes.py` *(nouveau, 280 lignes)*
- `src/ai_press_review/editorial/generator.py` *(156 lignes modifiées)*
- `src/ai_press_review/observability/__init__.py` *(nouveau)*
- `src/ai_press_review/observability/metrics.py` *(nouveau, 139 lignes)*
- `src/ai_press_review/pipeline.py` *(104 lignes modifiées)*
- `src/ai_press_review/extractors/web_content.py` *(63 lignes modifiées)*
- `src/ai_press_review/models.py` *(2 lignes modifiées)*
- `src/ai_press_review/collect.py` *(24 lignes — collision directe avec PR #8)*
- `src/ai_press_review/settings.py` *(16 lignes — collision directe avec PR #8)*
- `src/ai_press_review/tts/cartesia.py` *(30 lignes — collision avec phase 2)*

### Tests backend

- `tests/integration/__init__.py`, `conftest.py`, `test_pipeline_e2e.py`
- `tests/test_clustering.py`, `test_grounding.py`, `test_passes.py`, `test_transcript.py`

### Configuration éditoriale (collision directe)

- `config/podcast.yaml` *(j'ai modifié `tts_speed` FR à 0.92 et la `long_description` EN — ne pas écraser)*
- `config/prompt_system.txt` *(j'ai fixé la double-date — ne pas écraser)*
- `config/prompt_weekly.txt` *(j'ai fixé la double-date — ne pas écraser)*

### RSS (cas particulier)

- `src/ai_press_review/publish/feed.py` (+915 lignes sur ta branche)

  J'ai ajouté **une seule ligne** sur `main` : le cross-link FR dans la `<description>` du channel EN. Tout le reste de tes 915 lignes (Podcasting 2.0 tags, transcripts, SEO sitemap, etc.) est hors scope vitrine. **À sortir et à proposer en PR backend séparée** si tu veux les pousser.

- `src/ai_press_review/publish/transcript.py` *(nouveau, 283 lignes)* — même logique : pas de la vitrine. À soumettre séparément si validé.

- `src/ai_press_review/publish/locales.py` *(nouveau, 329 lignes)* — **cas ambigu** : si c'est utilisé uniquement pour rendre les templates HTML site, à garder. Si ça touche au backend pipeline, à isoler. Décris l'usage dans ta PR.

---

## État backend `main` à respecter

- Branche `stage4/fr-production` mergée dans `main` à `9600233` (15 avril 2026, 05:29 UTC).
- Matrix workflows EN+FR actifs (daily, weekly, auto-release).
- Per-locale state files (`episode_history_en.json`, `episode_history_fr.json`).
- Per-locale docs (`docs/` pour EN, `docs/fr/` pour FR).
- Per-locale R2 prefix (`pressreview/` EN, `pressreview-fr/` FR).
- TTS FR : voice via `CARTESIA_VOICE_ID_FR`, speed 0.92, emotion serious.
- Cross-link asymétrique : EN RSS channel `<description>` annonce la version FR.
- Fix double-date appliqué dans les 4 prompts (`prompt_system.txt`, `prompt_weekly.txt`, `prompt_system_fr.txt`, `prompt_weekly_fr.txt`).

---

## Procédure recommandée pour toi

1. **Pull `main`** dans ta branche : `git fetch origin main && git rebase origin/main`.
2. Pour chaque fichier listé en « hors périmètre » : `git checkout origin/main -- <chemin>`.
3. Pour `feed.py`, `transcript.py`, `locales.py` (les nouveautés Podcasting 2.0 + SEO + transcripts) : ouvre une **PR backend séparée** intitulée `feature: Podcasting 2.0 + transcripts + SEO sitemap` qu'on review proprement, indépendamment de la vitrine.
4. Pour ta PR vitrine : ne garde que `docs/*.html`, `docs/fr/*.html`, `docs/robots.txt`, `docs/sitemap.xml`, `preview-*.html`, et les assets statiques.
5. Ouvre la PR vitrine vers `main` quand c'est propre.

---

## En cas de désaccord

Le propriétaire arbitre. Pour toute question sur le périmètre, la décision passe par David. Mais sur le backend technique (état pipeline, prompts, settings, TTS), je suis maître par décision propriétaire.

— Claude (backend)
