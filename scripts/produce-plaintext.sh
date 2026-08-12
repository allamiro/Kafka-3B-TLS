#!/usr/bin/env bash
###############################################################################
# produce-plaintext.sh — interactive PLAINTEXT console producer (inside kafka1).
#   TOPIC=test-events  BOOTSTRAP_SERVER=kafka1:9092
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"

TOPIC="${TOPIC:-test-events}"
BOOTSTRAP_SERVER="${BOOTSTRAP_SERVER:-kafka1:9092}"
echo "PLAINTEXT producer → topic '${TOPIC}' via ${BOOTSTRAP_SERVER}. Type messages, Ctrl-D to end."
# -it so stdin is interactive.
dc exec "${BROKER_SVC}" kafka-console-producer.sh \
  --bootstrap-server "${BOOTSTRAP_SERVER}" \
  --topic "${TOPIC}"
