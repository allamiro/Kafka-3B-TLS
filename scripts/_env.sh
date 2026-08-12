#!/usr/bin/env bash
# Shared helper: load .env (if present) into the environment, then apply
# defaults. Source this from other scripts:  source "$(dirname "$0")/_env.sh"
# Existing environment variables always win over .env values.

# Resolve repository root (parent of scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

load_env() {
  local env_file="${REPO_ROOT}/.env"
  if [[ -f "${env_file}" ]]; then
    while IFS= read -r line; do
      line="${line%%$'\r'}"
      [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]] && continue
      local key="${line%%=*}"
      local val="${line#*=}"
      key="$(echo -n "${key}" | tr -d '[:space:]')"
      # Only set if not already exported (real env wins).
      if [[ -z "${!key:-}" ]]; then
        export "${key}=${val}"
      fi
    done < "${env_file}"
  fi

  # ---- defaults ----
  export KAFKA_SECURITY_MODE="${KAFKA_SECURITY_MODE:-dual}"
  export KAFKA_CERT_MODE="${KAFKA_CERT_MODE:-generate}"
  export INTER_BROKER_LISTENER_NAME="${INTER_BROKER_LISTENER_NAME:-SSL}"
  export BROKER_COUNT="${BROKER_COUNT:-3}"
  export ZOOKEEPER_COUNT="${ZOOKEEPER_COUNT:-3}"
  export KAFKA_SSL_PASSWORD="${KAFKA_SSL_PASSWORD:-changeit}"
  export KAFKA_CA_PASSWORD="${KAFKA_CA_PASSWORD:-changeit}"
  export KAFKA_DOMAIN="${KAFKA_DOMAIN:-hq.corp}"
  export CERT_ORG="${CERT_ORG:-corp}"
  export CERT_ORG_UNIT="${CERT_ORG_UNIT:-hq}"
  export CERT_VALIDITY_DAYS="${CERT_VALIDITY_DAYS:-3650}"
  export SSL_CLIENT_AUTH="${SSL_CLIENT_AUTH:-none}"
  export SSL_ENABLED_PROTOCOLS="${SSL_ENABLED_PROTOCOLS:-TLSv1.2,TLSv1.3}"
  export CERT_OUTPUT_DIR="${CERT_OUTPUT_DIR:-certs/generated}"
  export KAFKA_STORE_TYPE="${KAFKA_STORE_TYPE:-PKCS12}"
}

# Pretty logging helpers.
log()  { printf '\033[1;34m[*]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[✓]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; }

# FQDN for a broker index, legacy style: KAFKA0001.hq.corp
broker_fqdn() { printf 'KAFKA%04d.%s' "$1" "${KAFKA_DOMAIN}"; }
