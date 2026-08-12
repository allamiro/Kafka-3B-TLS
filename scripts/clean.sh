#!/usr/bin/env bash
###############################################################################
# clean.sh — tear down the lab and remove generated artifacts.
#
#   ./scripts/clean.sh            # stop + remove containers, networks, volumes
#   ./scripts/clean.sh --certs    # also delete generated certificates
#   ./scripts/clean.sh --all      # volumes + certs + generated compose file
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"

DO_CERTS=0; DO_GENERATED=0
for a in "$@"; do
  case "$a" in
    --certs) DO_CERTS=1 ;;
    --all)   DO_CERTS=1; DO_GENERATED=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

if [[ -f "${COMPOSE_FILE}" ]]; then
  echo "Stopping cluster and removing volumes (${COMPOSE_FILE}) ..."
  dc down -v --remove-orphans || true
else
  echo "No compose file found; skipping docker compose down."
fi

if [[ "${DO_CERTS}" -eq 1 ]]; then
  echo "Removing generated certificates under certs/generated/ ..."
  find "${REPO_ROOT}/certs/generated" -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
fi

if [[ "${DO_GENERATED}" -eq 1 ]]; then
  echo "Removing docker-compose.generated.yml ..."
  rm -f "${REPO_ROOT}/docker-compose.generated.yml"
fi

echo "Clean complete."
