#!/usr/bin/env bash
###############################################################################
# produce-ssl.sh — interactive SSL console producer (inside kafka1).
# Uses the in-container SSL client config written by the broker entrypoint.
#   TOPIC=test-events  BOOTSTRAP_SERVER=kafka1:9093
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"

TOPIC="${TOPIC:-test-events}"
BOOTSTRAP_SERVER="${BOOTSTRAP_SERVER:-kafka1:9093}"
echo "SSL producer → topic '${TOPIC}' via ${BOOTSTRAP_SERVER}. Type messages, Ctrl-D to end."
dc exec "${BROKER_SVC}" kafka-console-producer.sh \
  --bootstrap-server "${BOOTSTRAP_SERVER}" \
  --topic "${TOPIC}" \
  --producer.config "${SSL_CLIENT_CONFIG_IN_CONTAINER}"
