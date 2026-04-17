#!/usr/bin/env bash
# Convenience wrapper: activate venv, run pipeline, print stats.
set -euo pipefail
cd "$( dirname "${BASH_SOURCE[0]}" )/.."

source organizer/.venv/bin/activate

mac-organizer --config organizer/config.yaml pipeline --export plan.jsonl
mac-organizer --config organizer/config.yaml stats

cat <<EOF

Plan exported to: $(pwd)/plan.jsonl

To apply the moves (non-reversible by default):
  source organizer/.venv/bin/activate
  mac-organizer --config organizer/config.yaml apply --force
EOF
