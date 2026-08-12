#!/usr/bin/env bash
###############################################################################
# wait-for-kafka.sh — block until every Kafka broker answers API versions.
#   TIMEOUT=180 (seconds)
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"; load_env

TIMEOUT="${TIMEOUT:-180}"
deadline=$(( $(date +%s) + TIMEOUT ))

if [[ "${KAFKA_SECURITY_MODE}" == "ssl" ]]; then
  port=9093; cfg=(--command-config /etc/kafka/secrets/healthcheck.properties)
else
  port=9092; cfg=()
fi

for ((b=1; b<=BROKER_COUNT; b++)); do
  svc="kafka${b}"
  echo -n "Waiting for ${svc} ... "
  while :; do
    if dc exec -T "${svc}" kafka-broker-api-versions.sh \
         --bootstrap-server "localhost:${port}" "${cfg[@]}" >/dev/null 2>&1; then
      echo "ready"
      break
    fi
    if (( $(date +%s) > deadline )); then
      echo "TIMEOUT"
      echo "ERROR: ${svc} not ready within ${TIMEOUT}s" >&2
      exit 1
    fi
    sleep 3
  done
done
echo "All ${BROKER_COUNT} Kafka brokers are ready."
