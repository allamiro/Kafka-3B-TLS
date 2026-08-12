#!/usr/bin/env bash
###############################################################################
# ZooKeeper container entrypoint.
# Renders zoo.cfg from a template, writes the myid file, then starts ZooKeeper
# in the foreground so Docker can supervise it.
###############################################################################
set -euo pipefail

ZOOKEEPER_HOME="${ZOOKEEPER_HOME:-/opt/zookeeper}"
CONF_DIR="${ZOOKEEPER_HOME}/conf"
TPL_DIR="${ZOOKEEPER_HOME}/conf-templates"
DATA_DIR="/var/lib/zookeeper/data"
LOG_DIR="/var/lib/zookeeper/log"

# --- Defaults (override via environment) ----------------------------------
export ZOO_MY_ID="${ZOO_MY_ID:?ZOO_MY_ID is required (this node's id)}"
export ZOO_CLIENT_PORT="${ZOO_CLIENT_PORT:-2181}"
export ZOO_TICK_TIME="${ZOO_TICK_TIME:-2000}"
export ZOO_INIT_LIMIT="${ZOO_INIT_LIMIT:-10}"
export ZOO_SYNC_LIMIT="${ZOO_SYNC_LIMIT:-5}"
export ZOO_MAX_CLIENT_CNXNS="${ZOO_MAX_CLIENT_CNXNS:-60}"

# ZOO_SERVERS is passed as a single env var with entries separated by '|'
# (compose-friendly). Convert to the newline-separated block zoo.cfg expects.
#   e.g. "server.1=zookeeper1:2888:3888;2181|server.2=zookeeper2:2888:3888;2181"
if [[ -z "${ZOO_SERVERS:-}" ]]; then
  echo "ERROR: ZOO_SERVERS is required (the ensemble definition)." >&2
  exit 1
fi
export ZOO_SERVERS="${ZOO_SERVERS//|/$'\n'}"

mkdir -p "${DATA_DIR}" "${LOG_DIR}"

# --- myid -----------------------------------------------------------------
echo "${ZOO_MY_ID}" > "${DATA_DIR}/myid"

# --- Render zoo.cfg -------------------------------------------------------
envsubst < "${TPL_DIR}/zoo.cfg.tpl" > "${CONF_DIR}/zoo.cfg"
# ZooKeeper 3.9.x uses Logback — install our console-only config into the conf dir.
cp -f "${TPL_DIR}/logback.xml" "${CONF_DIR}/logback.xml"

echo "=== Rendered ${CONF_DIR}/zoo.cfg ==="
cat "${CONF_DIR}/zoo.cfg"
echo "=== myid=${ZOO_MY_ID} ==="

# JVM heap (zkServer.sh honours JVMFLAGS).
export JVMFLAGS="${ZOOKEEPER_HEAP_OPTS:--Xms256m -Xmx512m} ${JVMFLAGS:-}"
export ZOO_LOG_DIR="${LOG_DIR}"

# start-foreground keeps the JVM in the foreground (PID 1 supervision).
exec "${ZOOKEEPER_HOME}/bin/zkServer.sh" --config "${CONF_DIR}" start-foreground
