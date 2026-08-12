#!/usr/bin/env bash
###############################################################################
# import-certs.sh — build Kafka PKCS12 stores from an EXISTING enterprise PKI.
#
# Used when KAFKA_CERT_MODE=import. Reads from .env:
#   EXTERNAL_ROOT_CA_CERT          (required)
#   EXTERNAL_INTERMEDIATE_CA_CERT  (optional)
#   EXTERNAL_BROKER_CERTS_DIR      (required; kafkaN.crt / kafkaN.key inside)
#   EXTERNAL_CLIENT_CERT / KEY     (optional; for mutual TLS)
#
# Validates cert/key matching, required SANs, and chain, then produces the
# same PKCS12 store layout as generate-certs.sh. openssl-only.
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/create-stores.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/validate-certs.sh"

load_env
command -v openssl >/dev/null 2>&1 || { err "openssl is required on the host"; exit 1; }

OUT="${REPO_ROOT}/${CERT_OUTPUT_DIR}"
CA="${OUT}/ca"
PASS="${KAFKA_SSL_PASSWORD}"

# ---- validate required inputs ----
[[ -n "${EXTERNAL_ROOT_CA_CERT:-}" ]]     || { err "EXTERNAL_ROOT_CA_CERT is required for import mode"; exit 1; }
[[ -f "${EXTERNAL_ROOT_CA_CERT}" ]]       || { err "Root CA not found: ${EXTERNAL_ROOT_CA_CERT}"; exit 1; }
[[ -n "${EXTERNAL_BROKER_CERTS_DIR:-}" ]] || { err "EXTERNAL_BROKER_CERTS_DIR is required for import mode"; exit 1; }
[[ -d "${EXTERNAL_BROKER_CERTS_DIR}" ]]   || { err "Broker certs dir not found: ${EXTERNAL_BROKER_CERTS_DIR}"; exit 1; }

mkdir -p "${CA}"
cp -f "${EXTERNAL_ROOT_CA_CERT}" "${CA}/root-ca.crt"

if [[ -n "${EXTERNAL_INTERMEDIATE_CA_CERT:-}" ]]; then
  [[ -f "${EXTERNAL_INTERMEDIATE_CA_CERT}" ]] || { err "Intermediate CA not found: ${EXTERNAL_INTERMEDIATE_CA_CERT}"; exit 1; }
  cp -f "${EXTERNAL_INTERMEDIATE_CA_CERT}" "${CA}/intermediate-ca.crt"
  cat "${CA}/intermediate-ca.crt" "${CA}/root-ca.crt" > "${CA}/chain.crt"
else
  warn "No intermediate CA configured — using Root CA as the full chain"
  cp -f "${CA}/root-ca.crt" "${CA}/chain.crt"
fi
ok "Imported CA material"

# ---- per-broker ----
for ((i=1; i<=BROKER_COUNT; i++)); do
  name="kafka${i}"
  dir="${OUT}/${name}"
  src_crt="${EXTERNAL_BROKER_CERTS_DIR}/${name}.crt"
  src_key="${EXTERNAL_BROKER_CERTS_DIR}/${name}.key"

  [[ -f "${src_crt}" ]] || { err "${name}: missing ${src_crt}"; exit 1; }
  [[ -f "${src_key}" ]] || { err "${name}: missing ${src_key}"; exit 1; }

  mkdir -p "${dir}"
  cp -f "${src_crt}" "${dir}/${name}.crt"
  cp -f "${src_key}" "${dir}/${name}.key"
  chmod 600 "${dir}/${name}.key"

  # Validate cert/key match, required SANs, and chain BEFORE building stores.
  validate_broker "${i}" "${dir}" "${CA}/chain.crt" || {
    err "${name}: validation failed — refusing to build stores"; exit 1; }

  cat "${dir}/${name}.crt" "${CA}/chain.crt" > "${dir}/${name}.chain.crt"
  make_keystore "${dir}/${name}.crt" "${dir}/${name}.key" "${CA}/chain.crt" \
                "${name}" "${dir}/kafka.server.keystore.p12" "${PASS}"
  install_trust_material "${CA}/chain.crt" "${dir}/ca-chain.crt"
  ok "${name}: stores built from imported material"
done

# ---- client ----
CLIENT="${OUT}/client"
mkdir -p "${CLIENT}"
install_trust_material "${CA}/chain.crt" "${CLIENT}/ca-chain.crt"
cat > "${CLIENT}/client-ssl.properties" <<EOF
security.protocol=SSL
ssl.truststore.type=PEM
ssl.truststore.location=${CERT_OUTPUT_DIR}/client/ca-chain.crt
ssl.endpoint.identification.algorithm=https
EOF

if [[ "${SSL_CLIENT_AUTH}" == "required" ]]; then
  [[ -n "${EXTERNAL_CLIENT_CERT:-}" && -f "${EXTERNAL_CLIENT_CERT}" ]] || { err "SSL_CLIENT_AUTH=required but EXTERNAL_CLIENT_CERT missing"; exit 1; }
  [[ -n "${EXTERNAL_CLIENT_KEY:-}"  && -f "${EXTERNAL_CLIENT_KEY}"  ]] || { err "SSL_CLIENT_AUTH=required but EXTERNAL_CLIENT_KEY missing"; exit 1; }
  cp -f "${EXTERNAL_CLIENT_CERT}" "${CLIENT}/kafka-client.crt"
  cp -f "${EXTERNAL_CLIENT_KEY}"  "${CLIENT}/kafka-client.key"
  chmod 600 "${CLIENT}/kafka-client.key"
  make_keystore "${CLIENT}/kafka-client.crt" "${CLIENT}/kafka-client.key" "${CA}/chain.crt" \
                "kafka-client" "${CLIENT}/kafka.client.keystore.p12" "${PASS}"
  cat >> "${CLIENT}/client-ssl.properties" <<EOF
ssl.keystore.type=PKCS12
ssl.keystore.location=${CERT_OUTPUT_DIR}/client/kafka.client.keystore.p12
ssl.keystore.password=${PASS}
ssl.key.password=${PASS}
EOF
  ok "Imported client keystore (mutual TLS)"
fi

mkdir -p "${REPO_ROOT}/config/ssl"
cp -f "${CLIENT}/client-ssl.properties" "${REPO_ROOT}/config/ssl/client.properties"

# ----------------------------------------------------------------------------
# Permissions for the containers
# ----------------------------------------------------------------------------
# Brokers run as an unprivileged non-root user and mount these directories
# read-only, so directories must be traversable and certificates readable.
# Private keys (broker and CA) stay 0600 — the broker reads the PKCS12 store,
# never the bare key.
chmod 755 "${OUT}" 2>/dev/null || true
for d in "${OUT}"/kafka* "${OUT}/client"; do
  if [[ -d "${d}" ]]; then chmod 755 "${d}"; fi
done
find "${OUT}" -maxdepth 2 -name '*.crt' ! -path "${CA}/*" -exec chmod 644 {} +

ok "Certificate import complete → ${CERT_OUTPUT_DIR}/"
