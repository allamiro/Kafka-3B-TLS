#!/usr/bin/env bash
###############################################################################
# create-topic.sh — create a Kafka topic (runs inside the kafka1 container).
#
# Env overrides:
#   TOPIC=test-events PARTITIONS=6 REPLICATION_FACTOR=3
#   SECURITY=plaintext|ssl   BOOTSTRAP_SERVER=<host:port>
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"

TOPIC="${TOPIC:-test-events}"
PARTITIONS="${PARTITIONS:-6}"
REPLICATION_FACTOR="${REPLICATION_FACTOR:-3}"
SECURITY="${SECURITY:-plaintext}"

if [[ "${SECURITY}" == "ssl" ]]; then
  BOOTSTRAP_SERVER="${BOOTSTRAP_SERVER:-kafka1:9093}"
  kexec kafka-topics.sh \
    --bootstrap-server "${BOOTSTRAP_SERVER}" \
    --command-config "${SSL_CLIENT_CONFIG_IN_CONTAINER}" \
    --create --if-not-exists \
    --topic "${TOPIC}" \
    --partitions "${PARTITIONS}" \
    --replication-factor "${REPLICATION_FACTOR}"
else
  BOOTSTRAP_SERVER="${BOOTSTRAP_SERVER:-kafka1:9092}"
  kexec kafka-topics.sh \
    --bootstrap-server "${BOOTSTRAP_SERVER}" \
    --create --if-not-exists \
    --topic "${TOPIC}" \
    --partitions "${PARTITIONS}" \
    --replication-factor "${REPLICATION_FACTOR}"
fi
echo "Created topic '${TOPIC}' (${PARTITIONS} partitions, RF=${REPLICATION_FACTOR}) via ${BOOTSTRAP_SERVER}"
