#!/usr/bin/env bash
# =============================================================================
# install.sh — one-shot installer for the paperless-setup stack + mac-organizer.
#
# Run on your Mac with the SSD mounted. Requires:
#   - Homebrew  (https://brew.sh)
#   - Docker Desktop running
#   - Python 3.10+
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

log()  { printf "\033[1;34m[install]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[err]\033[0m %s\n" "$*" >&2; exit 1; }

# --- Checks ------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker not found. Install Docker Desktop first."
docker info >/dev/null 2>&1 || die "Docker daemon not reachable. Start Docker Desktop."
command -v python3 >/dev/null 2>&1 || die "python3 not found."

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
log "Python $PYVER detected."

# --- Homebrew optional extras (OCR + ffprobe for videos) ---------------------
if command -v brew >/dev/null 2>&1; then
  log "Installing optional OCR and media tools via Homebrew..."
  brew list ocrmypdf >/dev/null 2>&1 || brew install ocrmypdf || warn "ocrmypdf install failed."
  brew list tesseract-lang >/dev/null 2>&1 || brew install tesseract-lang || warn "tesseract-lang install failed."
  brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg || warn "ffmpeg install failed."
else
  warn "Homebrew not found — skipping ocrmypdf/ffmpeg. Scanned PDFs will be classified by filename only."
fi

# --- .env --------------------------------------------------------------------
if [[ ! -f .env ]]; then
  log "Creating .env from .env.example"
  cp .env.example .env
  warn "Edit .env before first run: set PAPERLESS_ADMIN_PASSWORD, DEEPINFRA_API_KEY, PAPERLESS_DATA_ROOT."
fi

# --- Python venv for the organizer ------------------------------------------
if [[ ! -d organizer/.venv ]]; then
  log "Creating Python venv in organizer/.venv"
  python3 -m venv organizer/.venv
fi
# shellcheck disable=SC1091
source organizer/.venv/bin/activate
log "Installing organizer dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r organizer/requirements.txt
pip install --quiet -e organizer/

# --- Config for the organizer ------------------------------------------------
if [[ ! -f organizer/config.yaml ]]; then
  log "Creating organizer/config.yaml from template"
  cp organizer/config.example.yaml organizer/config.yaml
  warn "Edit organizer/config.yaml to set scan_roots and target_root."
fi

# --- Paperless stack ---------------------------------------------------------
log "Starting Paperless-ngx stack..."
docker compose up -d

log "Waiting for Paperless webserver..."
for i in {1..60}; do
  if curl -sf http://localhost:8000/api/ >/dev/null 2>&1; then
    log "Paperless is up: http://localhost:8000"
    break
  fi
  sleep 2
done

cat <<EOF

==============================================================================
  Install complete.

  Next steps:
  1. Edit .env (admin password, DeepInfra key, SSD path).
  2. Edit organizer/config.yaml (scan_roots, target_root).
  3. Activate venv:       source organizer/.venv/bin/activate
  4. Dry-run pipeline:    mac-organizer --config organizer/config.yaml pipeline \\
                                  --export plan.jsonl
  5. Review plan.jsonl, then: mac-organizer --config organizer/config.yaml apply --force

  Paperless UI:           http://localhost:8000
==============================================================================
EOF
