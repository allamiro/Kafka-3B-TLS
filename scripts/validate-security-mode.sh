#!/usr/bin/env bash
###############################################################################
# validate-security-mode.sh — sanity-check security/cert selectors from .env.
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"
load_env

rc=0

case "${KAFKA_SECURITY_MODE}" in
  plaintext|ssl|dual) ;;
  *) err "KAFKA_SECURITY_MODE must be plaintext|ssl|dual (got '${KAFKA_SECURITY_MODE}')"; rc=1 ;;
esac

case "${KAFKA_CERT_MODE}" in
  generate|import) ;;
  *) err "KAFKA_CERT_MODE must be generate|import (got '${KAFKA_CERT_MODE}')"; rc=1 ;;
esac

case "${SSL_CLIENT_AUTH}" in
  none|required|requested) ;;
  *) err "SSL_CLIENT_AUTH must be none|requested|required (got '${SSL_CLIENT_AUTH}')"; rc=1 ;;
esac

# Inter-broker listener must be a valid choice for the mode.
if [[ "${KAFKA_SECURITY_MODE}" == "ssl" && "${INTER_BROKER_LISTENER_NAME}" != "SSL" ]]; then
  warn "KAFKA_SECURITY_MODE=ssl forces inter-broker to SSL (ignoring INTER_BROKER_LISTENER_NAME='${INTER_BROKER_LISTENER_NAME}')"
fi
if [[ "${KAFKA_SECURITY_MODE}" == "plaintext" && "${INTER_BROKER_LISTENER_NAME}" == "SSL" ]]; then
  warn "KAFKA_SECURITY_MODE=plaintext forces inter-broker to PLAINTEXT (ignoring INTER_BROKER_LISTENER_NAME=SSL)"
fi

# import mode requires external paths to exist.
if [[ "${KAFKA_SECURITY_MODE}" != "plaintext" && "${KAFKA_CERT_MODE}" == "import" ]]; then
  [[ -n "${EXTERNAL_ROOT_CA_CERT:-}"     && -f "${EXTERNAL_ROOT_CA_CERT}"   ]] || { err "import mode: EXTERNAL_ROOT_CA_CERT missing/not found"; rc=1; }
  [[ -n "${EXTERNAL_BROKER_CERTS_DIR:-}" && -d "${EXTERNAL_BROKER_CERTS_DIR}" ]] || { err "import mode: EXTERNAL_BROKER_CERTS_DIR missing/not found"; rc=1; }
fi

[[ "${rc}" -eq 0 ]] && ok "Security mode configuration is valid (mode=${KAFKA_SECURITY_MODE}, certs=${KAFKA_CERT_MODE})."
exit "${rc}"
