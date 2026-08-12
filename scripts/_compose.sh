#!/usr/bin/env bash
# Shared helper for operational scripts: locate the compose file and provide a
# convenience wrapper to run Kafka CLI tools inside the kafka1 container.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Prefer the generated file; fall back to the committed default.
if [[ -f "${REPO_ROOT}/docker-compose.generated.yml" ]]; then
  COMPOSE_FILE="${REPO_ROOT}/docker-compose.generated.yml"
else
  COMPOSE_FILE="${REPO_ROOT}/docker-compose.yml"
fi
export COMPOSE_FILE

BROKER_SVC="${BROKER_SVC:-kafka1}"

dc() { docker compose -f "${COMPOSE_FILE}" "$@"; }

# Run a Kafka CLI tool inside the broker container.
kexec() { dc exec -T "${BROKER_SVC}" "$@"; }

# In-container SSL client config, written by the broker entrypoint in ssl/dual
# mode. It lives beside server.properties because /etc/kafka/secrets is
# bind-mounted read-only.
export SSL_CLIENT_CONFIG_IN_CONTAINER="/opt/kafka/config/client-ssl.properties"
