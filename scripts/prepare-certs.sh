#!/usr/bin/env bash
###############################################################################
# prepare-certs.sh — single user-facing entrypoint for SSL material.
#
# Decides what to do based on .env:
#   KAFKA_SECURITY_MODE=plaintext        -> nothing to do (certs not required)
#   KAFKA_CERT_MODE=generate             -> scripts/generate-certs.sh
#   KAFKA_CERT_MODE=import               -> scripts/import-certs.sh
#
# Invoked by `make certs` or directly: ./scripts/prepare-certs.sh
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"
load_env

# Validate the security/cert mode selectors first.
bash "${SCRIPT_DIR}/validate-security-mode.sh"

if [[ "${KAFKA_SECURITY_MODE}" == "plaintext" ]]; then
  ok "PLAINTEXT mode selected; certificates are not required."
  exit 0
fi

case "${KAFKA_CERT_MODE}" in
  generate)
    log "KAFKA_CERT_MODE=generate → generating local CA and broker certificates"
    bash "${SCRIPT_DIR}/generate-certs.sh"
    ;;
  import)
    log "KAFKA_CERT_MODE=import → importing external CA and broker certificates"
    bash "${SCRIPT_DIR}/import-certs.sh"
    ;;
  *)
    err "Invalid KAFKA_CERT_MODE='${KAFKA_CERT_MODE}' (expected generate|import)"
    exit 1
    ;;
esac

ok "Certificates are ready under ${CERT_OUTPUT_DIR}/"
