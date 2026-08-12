#!/usr/bin/env bash
###############################################################################
# wait-for-zookeeper.sh — block until every ZooKeeper node answers 'imok'.
#   TIMEOUT=120 (seconds)
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"; load_env

TIMEOUT="${TIMEOUT:-120}"
deadline=$(( $(date +%s) + TIMEOUT ))

for ((z=1; z<=ZOOKEEPER_COUNT; z++)); do
  svc="zookeeper${z}"
  echo -n "Waiting for ${svc} ... "
  while :; do
    if dc exec -T "${svc}" bash -c 'echo ruok | nc -w 2 localhost 2181' 2>/dev/null | grep -q imok; then
      echo "imok"
      break
    fi
    if (( $(date +%s) > deadline )); then
      echo "TIMEOUT"
      echo "ERROR: ${svc} did not return imok within ${TIMEOUT}s" >&2
      exit 1
    fi
    sleep 2
  done
done
echo "All ${ZOOKEEPER_COUNT} ZooKeeper nodes are healthy."
