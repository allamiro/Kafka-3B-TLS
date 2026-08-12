#!/usr/bin/env bash
###############################################################################
# consume-plaintext.sh — PLAINTEXT console consumer from beginning (inside kafka1).
#   TOPIC=test-events  BOOTSTRAP_SERVER=kafka1:9092
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"

TOPIC="${TOPIC:-test-events}"
BOOTSTRAP_SERVER="${BOOTSTRAP_SERVER:-kafka1:9092}"
echo "PLAINTEXT consumer ← topic '${TOPIC}' via ${BOOTSTRAP_SERVER} (from beginning). Ctrl-C to stop."
dc exec "${BROKER_SVC}" kafka-console-consumer.sh \
  --bootstrap-server "${BOOTSTRAP_SERVER}" \
  --topic "${TOPIC}" \
  --from-beginning
