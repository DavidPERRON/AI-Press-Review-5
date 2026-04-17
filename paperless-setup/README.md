# Mac Organizer + Paperless-ngx

Kit clé-en-main pour **reprendre en main** un stockage Mac éclaté sur plusieurs
années : VM, migrations, clouds multiples (iCloud, OneDrive). Le kit **scanne
tout**, **détecte les doublons** (SHA-256), **classe** chaque document via LLM
(DeepInfra / Llama 3.3 70B), et **range** sur un SSD cible dans une arborescence
cohérente de **3 niveaux maximum**. Paperless-ngx peut ensuite indexer le tout
pour la recherche full-text.

## Ce que ça fait

| Étape | Ce qui se passe |
| --- | --- |
| `scan` | Parcourt tous les `scan_roots` (Mac, VM, OneDrive, disques externes) et inventorie les fichiers. |
| `hash` | Calcule SHA-256 pour chaque fichier (base de la détection de doublons). |
| `dedupe` | Groupe les fichiers identiques. Garde UN canonique (meilleure localisation, plus ancien), marque les autres comme doublons. |
| `extract` | Texte des PDF (pdfminer + OCR fallback), DOCX, TXT. Dates EXIF pour photos/vidéos. |
| `classify` | Envoie chaque document au LLM avec la **taxonomie fermée** → catégorie + sous-catégorie + année + nom de fichier normalisé + score de confiance. Tout < 0.85 part dans `99_NonClasse/`. |
| `plan` | Construit le plan de déplacement (dry-run par défaut). Exportable en JSONL. |
| `apply` | Exécute les déplacements. Doublons → `00_Doublons/<catégorie>/`. |

## Arborescence cible (3 niveaux max)

```
/Volumes/SSD2TB/
├── 00_Doublons/<catégorie_du_canonique>/<fichier>
├── 01_Identite/{Officiel|Diplomes_Certifications}/
├── 02_Logement/{Contrats|Factures_Charges|Assurance|Travaux}/<AAAA>/
├── 03_Finances/{Banque|Credits|Epargne_Placements|Impots}/<AAAA>/
├── 04_Travail/{Contrats|Salaires|Attestations|PoleEmploi}/<AAAA>/
├── 05_Sante/{Remboursements|Ordonnances_Analyses|Mutuelle}/<AAAA>/
├── 06_Vehicule/{Administratif|Assurance|Entretien}/<AAAA>/
├── 07_Famille/{Enfants|Animaux|Successions}/
├── 08_Abonnements/{Telecom_Internet|Streaming_Medias|Logiciels}/<AAAA>/
├── 09_Achats_Garanties/{Factures_Garanties|Notices}/<AAAA>/
├── 10_Juridique/{Contrats|Litiges_Courriers}/<AAAA>/
├── 11_Voyages/{Reservations_Billets|Visas_Documents}/<AAAA>/
├── 12_Photos/<AAAA>/                (EXIF)
├── 13_Videos/<AAAA>/                (ffprobe)
├── 14_Medias/{Musique|Ebooks|Divers}/
├── 15_Projets/{Actif|Archive}/<NomProjet>/
├── 16_Personnel/{Correspondance|Notes}/<AAAA>/
├── 17_Travail_Fichiers/{Bureautique|Presentations|Donnees}/
└── 99_NonClasse/                    (confiance < seuil, revue manuelle)
```

La taxonomie est **fermée** : le LLM ne peut pas inventer de nouveaux dossiers,
ce qui garantit une structure reproductible et une fiabilité >95% sur
documents français. Modifier `mac_organizer/taxonomy.py` pour l'adapter.

## Prérequis (Mac)

- **Docker Desktop** installé et démarré.
- **Homebrew** (recommandé, pour OCR et ffprobe).
- **Python 3.10+**.
- **SSD 2 To** monté (APFS, pas exFAT — préserve les métadonnées macOS).
- **Clé API DeepInfra** : <https://deepinfra.com/dash/api_keys>.
- **Rapatriement cloud préalable** : iCloud (Photos → Originaux, Drive →
  Télécharger une copie), OneDrive (Toujours sur cet appareil), Google Drive
  idem. Fais-le **avant** de lancer le scan.

## Installation

```bash
git clone <ce-repo>
cd paperless-setup
./install.sh
```

`install.sh` :
1. Vérifie Docker, Python.
2. Installe `ocrmypdf`, `tesseract-lang`, `ffmpeg` via Homebrew.
3. Crée un venv, installe `mac-organizer`.
4. Copie `.env.example` → `.env` et `config.example.yaml` → `config.yaml`.
5. Démarre Paperless-ngx (http://localhost:8000).

## Configuration

**1. `.env`** — Paperless + clé DeepInfra.

```env
PAPERLESS_DATA_ROOT=/Volumes/SSD2TB/paperless-data
PAPERLESS_ADMIN_PASSWORD=<secret>
DEEPINFRA_API_KEY=<ta_cle>
```

**2. `organizer/config.yaml`** — scan + cible.

```yaml
scan_roots:
  - "~/Desktop"
  - "~/Documents"
  - "~/Downloads"
  - "~/Pictures"
  - "~/Library/Mobile Documents/com~apple~CloudDocs"
  - "~/Library/CloudStorage"
  # - "~/Parallels"                     # si tu veux scanner la VM aussi
target_root: "/Volumes/SSD2TB"
dry_run: true
```

## Utilisation

```bash
source organizer/.venv/bin/activate

# 1) Tout en une passe (scan + hash + dedupe + extract + classify + plan)
mac-organizer --config organizer/config.yaml pipeline --export plan.jsonl

# 2) Inspecte plan.jsonl (chaque ligne = 1 déplacement prévu)
head -20 plan.jsonl
less plan.jsonl

# 3) Stats
mac-organizer --config organizer/config.yaml stats

# 4) Quand tu es prêt : exécute
mac-organizer --config organizer/config.yaml apply --force
```

Chaque phase est **individuellement relançable** (SQLite) :

```bash
mac-organizer -c organizer/config.yaml scan
mac-organizer -c organizer/config.yaml hash
mac-organizer -c organizer/config.yaml dedupe
mac-organizer -c organizer/config.yaml extract
mac-organizer -c organizer/config.yaml classify
mac-organizer -c organizer/config.yaml plan --export plan.jsonl
mac-organizer -c organizer/config.yaml apply --force
```

## Fiabilité du LLM

**Seuil de confiance 0.85** + **taxonomie fermée** + **validation JSON stricte**
= >95% sur documents administratifs français standards (EDF, CPAM, impôts,
banques, opérateurs). Tout ce qui ne passe pas le seuil atterrit dans
`99_NonClasse/` pour tri manuel (quelques %).

Modèle par défaut : `meta-llama/Llama-3.3-70B-Instruct` (DeepInfra,
~$0.0002-0.001 par document). Alternatives dans `config.yaml` :
`Qwen/Qwen2.5-72B-Instruct`, `deepseek-ai/DeepSeek-V3`.

## Doublons

Pour chaque groupe de fichiers identiques (même SHA-256) :
- **1 canonique** rangé dans son dossier normal (choix : meilleure localisation
  — pas dans `Downloads`/`.Trash`/`Desktop` — puis plus ancien `mtime`).
- **Tous les autres** (doublons, triplons, n-plons) → `00_Doublons/<catégorie>/`.
- Un manifeste dans la DB SQLite garde la correspondance `doublon → canonique`.

## Sécurité / sauvegarde

**AVANT d'exécuter `apply --force`** :
1. Sauvegarde Time Machine complète.
2. Lance `pipeline` en `dry_run: true` et inspecte `plan.jsonl`.
3. Garde le SSD **APFS chiffré** si données sensibles.
4. Les déplacements sont des `shutil.move` — **réversibles manuellement** via
   la table `moves` de la DB SQLite (chemin source + cible mémorisés).

## VM

Depuis la VM Windows/Linux : monte `/Volumes/SSD2TB/` en **lecture seule** via
les dossiers partagés Parallels/VMware/UTM. Aucun fichier n'est stocké dans la
VM — seules les applis tournent là.

## Limites

- **PDF scannés sans texte** : si `ocrmypdf` n'est pas installé, le classement
  retombe sur le nom de fichier (précision dégradée).
- **Fichiers > 5 Go** : ignorés par défaut (images disque, VM). Ajustable dans
  `max_file_size_mb`.
- **Formats Apple (Pages, Numbers, Keynote)** : texte extrait via `textutil`
  si dispo, sinon classé au nom.
- **Zip, archives** : indexés comme fichiers, pas décompressés (évite
  l'explosion de l'arborescence).

## Troubleshooting

```bash
# Voir l'état phase par phase
mac-organizer -c organizer/config.yaml stats

# Voir les erreurs
sqlite3 organizer/mac_organizer.db "SELECT phase, status, details FROM run_log ORDER BY id DESC LIMIT 20"

# Voir les non-classés
sqlite3 organizer/mac_organizer.db "SELECT f.path, cl.confidence FROM files f JOIN classifications cl ON cl.file_id=f.id WHERE cl.category='99_NonClasse'"

# Relancer juste la classification (après réglage du seuil)
rm -f organizer/mac_organizer.db   # ⚠ repart de zéro — ne pas faire si apply déjà exécuté
```

## Licence

Voir le repo principal.
