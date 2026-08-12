#!/usr/bin/env bash
###############################################################################
# describe-cluster.sh — show broker and topic metadata (inside kafka1).
#   SECURITY=plaintext|ssl
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_compose.sh"

SECURITY="${SECURITY:-plaintext}"
if [[ "${SECURITY}" == "ssl" ]]; then
  BS="${BOOTSTRAP_SERVER:-kafka1:9093}"
  CFG=(--command-config "${SSL_CLIENT_CONFIG_IN_CONTAINER}")
else
  BS="${BOOTSTRAP_SERVER:-kafka1:9092}"
  CFG=()
fi

echo "================ Broker API versions / liveness ================"
kexec kafka-broker-api-versions.sh --bootstrap-server "${BS}" "${CFG[@]}" 2>/dev/null \
  | grep -E '^[a-zA-Z0-9._-]+:[0-9]+' | sed 's/ (.*//' || true

echo
echo "================ Cluster / quorum metadata ====================="
kexec kafka-metadata-quorum.sh --bootstrap-server "${BS}" "${CFG[@]}" describe --status 2>/dev/null \
  || echo "(kafka-metadata-quorum is KRaft-only; this is a ZooKeeper cluster — see ZooKeeper instead)"

echo
echo "================ Topics (detailed) ============================="
kexec kafka-topics.sh --bootstrap-server "${BS}" "${CFG[@]}" --describe || true
