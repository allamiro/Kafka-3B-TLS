#!/usr/bin/env bash
###############################################################################
# Kafka broker container entrypoint.
# Renders /opt/kafka/config/server.properties from templates according to
# KAFKA_SECURITY_MODE (plaintext | ssl | dual), then starts the broker.
###############################################################################
set -euo pipefail

KAFKA_HOME="${KAFKA_HOME:-/opt/kafka}"
TPL_DIR="${KAFKA_HOME}/templates"
CONF="${KAFKA_HOME}/config/server.properties"
SECRETS_DIR="/etc/kafka/secrets"
# The secrets directory is bind-mounted read-only, so the generated client
# config goes next to server.properties, which the broker user owns.
CLIENT_CONF="${KAFKA_HOME:-/opt/kafka}/config/client-ssl.properties"
PLAINTEXT_PORT=9092
SSL_PORT=9093

# --- Required identity -----------------------------------------------------
export BROKER_ID="${BROKER_ID:?BROKER_ID is required}"
export BROKER_HOSTNAME="${BROKER_HOSTNAME:-$(hostname)}"
export KAFKA_ZOOKEEPER_CONNECT="${KAFKA_ZOOKEEPER_CONNECT:?KAFKA_ZOOKEEPER_CONNECT is required}"

# --- Defaults (override via environment) ----------------------------------
export NUM_PARTITIONS="${NUM_PARTITIONS:-6}"
export DEFAULT_REPLICATION_FACTOR="${DEFAULT_REPLICATION_FACTOR:-3}"
export MIN_INSYNC_REPLICAS="${MIN_INSYNC_REPLICAS:-2}"
export OFFSETS_TOPIC_REPLICATION_FACTOR="${OFFSETS_TOPIC_REPLICATION_FACTOR:-3}"
export TRANSACTION_STATE_LOG_REPLICATION_FACTOR="${TRANSACTION_STATE_LOG_REPLICATION_FACTOR:-3}"
export TRANSACTION_STATE_LOG_MIN_ISR="${TRANSACTION_STATE_LOG_MIN_ISR:-2}"
export LOG_RETENTION_HOURS="${LOG_RETENTION_HOURS:-168}"
export AUTO_CREATE_TOPICS_ENABLE="${AUTO_CREATE_TOPICS_ENABLE:-false}"
export DELETE_TOPIC_ENABLE="${DELETE_TOPIC_ENABLE:-true}"

export KAFKA_SECURITY_MODE="${KAFKA_SECURITY_MODE:-dual}"
export INTER_BROKER_LISTENER_NAME="${INTER_BROKER_LISTENER_NAME:-SSL}"
export KAFKA_SSL_PASSWORD="${KAFKA_SSL_PASSWORD:-changeit}"
export SSL_CLIENT_AUTH="${SSL_CLIENT_AUTH:-none}"
export SSL_ENABLED_PROTOCOLS="${SSL_ENABLED_PROTOCOLS:-TLSv1.2,TLSv1.3}"

# --- Compute listener block from security mode -----------------------------
need_ssl=0
case "${KAFKA_SECURITY_MODE}" in
  plaintext)
    export KAFKA_LISTENERS="PLAINTEXT://0.0.0.0:${PLAINTEXT_PORT}"
    export KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://${BROKER_HOSTNAME}:${PLAINTEXT_PORT}"
    export KAFKA_LISTENER_SECURITY_PROTOCOL_MAP="PLAINTEXT:PLAINTEXT"
    export KAFKA_INTER_BROKER_LISTENER_NAME="PLAINTEXT"
    ;;
  ssl)
    export KAFKA_LISTENERS="SSL://0.0.0.0:${SSL_PORT}"
    export KAFKA_ADVERTISED_LISTENERS="SSL://${BROKER_HOSTNAME}:${SSL_PORT}"
    export KAFKA_LISTENER_SECURITY_PROTOCOL_MAP="SSL:SSL"
    export KAFKA_INTER_BROKER_LISTENER_NAME="SSL"
    need_ssl=1
    ;;
  dual)
    export KAFKA_LISTENERS="PLAINTEXT://0.0.0.0:${PLAINTEXT_PORT},SSL://0.0.0.0:${SSL_PORT}"
    export KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://${BROKER_HOSTNAME}:${PLAINTEXT_PORT},SSL://${BROKER_HOSTNAME}:${SSL_PORT}"
    export KAFKA_LISTENER_SECURITY_PROTOCOL_MAP="PLAINTEXT:PLAINTEXT,SSL:SSL"
    export KAFKA_INTER_BROKER_LISTENER_NAME="${INTER_BROKER_LISTENER_NAME}"
    need_ssl=1
    ;;
  *)
    echo "ERROR: invalid KAFKA_SECURITY_MODE='${KAFKA_SECURITY_MODE}' (expected plaintext|ssl|dual)" >&2
    exit 1
    ;;
esac

# --- Render server.properties ---------------------------------------------
envsubst < "${TPL_DIR}/server.properties.tpl" > "${CONF}"

if [[ "${need_ssl}" -eq 1 ]]; then
  if [[ ! -f "${SECRETS_DIR}/kafka.server.keystore.p12" || ! -f "${SECRETS_DIR}/ca-chain.crt" ]]; then
    echo "ERROR: SSL material missing in ${SECRETS_DIR}." >&2
    echo "       Expected kafka.server.keystore.p12 and ca-chain.crt." >&2
    echo "       Run: make certs" >&2
    exit 1
  fi
  envsubst < "${TPL_DIR}/server-ssl.properties.tpl" >> "${CONF}"

  # Client config for the image/compose health check and for CLI tools run
  # inside the container.
  envsubst < "${TPL_DIR}/client-ssl.properties.tpl" > "${CLIENT_CONF}"
fi

echo "=== Rendered ${CONF} (mode=${KAFKA_SECURITY_MODE}) ==="
cat "${CONF}"
echo "==============================================="

export KAFKA_HEAP_OPTS="${KAFKA_HEAP_OPTS:--Xms512m -Xmx1g}"
# Kafka 3.9.2 is Log4j 1.x — point it at our console-only config.
export KAFKA_LOG4J_OPTS="-Dlog4j.configuration=file:${TPL_DIR}/log4j.properties"

exec "${KAFKA_HOME}/bin/kafka-server-start.sh" "${CONF}"
