#!/usr/bin/env bash
###############################################################################
# list-topics.sh — list topics (runs inside the kafka1 container).
#   SECURITY=plaintext|ssl   BOOTSTRAP_SERVER=<host:port>
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"

SECURITY="${SECURITY:-plaintext}"
if [[ "${SECURITY}" == "ssl" ]]; then
  kexec kafka-topics.sh --bootstrap-server "${BOOTSTRAP_SERVER:-kafka1:9093}" \
    --command-config "${SSL_CLIENT_CONFIG_IN_CONTAINER}" --list
else
  kexec kafka-topics.sh --bootstrap-server "${BOOTSTRAP_SERVER:-kafka1:9092}" --list
fi
