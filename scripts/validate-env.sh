#!/usr/bin/env bash
###############################################################################
# validate-env.sh — validate cluster sizing and core .env values.
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"
load_env

rc=0

is_int() { [[ "$1" =~ ^[0-9]+$ ]]; }

if ! is_int "${BROKER_COUNT}" || (( BROKER_COUNT < 3 )); then
  err "BROKER_COUNT must be an integer >= 3 (got '${BROKER_COUNT}')"; rc=1
fi

if ! is_int "${ZOOKEEPER_COUNT}" || { (( ZOOKEEPER_COUNT != 3 )) && (( ZOOKEEPER_COUNT != 5 )); }; then
  err "ZOOKEEPER_COUNT must be 3 or 5 (got '${ZOOKEEPER_COUNT}')"; rc=1
fi

# Replication factor must not exceed broker count.
if is_int "${DEFAULT_REPLICATION_FACTOR:-3}" && is_int "${BROKER_COUNT}"; then
  if (( DEFAULT_REPLICATION_FACTOR > BROKER_COUNT )); then
    err "DEFAULT_REPLICATION_FACTOR (${DEFAULT_REPLICATION_FACTOR}) cannot exceed BROKER_COUNT (${BROKER_COUNT})"; rc=1
  fi
fi

# Delegate security-mode checks.
bash "${SCRIPT_DIR}/validate-security-mode.sh" || rc=1

[[ "${rc}" -eq 0 ]] && ok "Environment is valid: ${BROKER_COUNT} brokers, ${ZOOKEEPER_COUNT} zookeepers, mode=${KAFKA_SECURITY_MODE}."
exit "${rc}"
