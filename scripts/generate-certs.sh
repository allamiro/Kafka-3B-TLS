#!/usr/bin/env bash
###############################################################################
# generate-certs.sh — generate a full lab PKI for the Kafka cluster.
#
#   Root CA -> Intermediate CA -> per-broker certs (with SANs) -> PKCS12 stores
#
# Reads configuration from .env (BROKER_COUNT, KAFKA_SSL_PASSWORD, KAFKA_DOMAIN,
# CERT_ORG, CERT_ORG_UNIT, CERT_VALIDITY_DAYS, SSL_CLIENT_AUTH, ...).
# openssl-only — no Java keytool required on the host.
#
#   ./scripts/generate-certs.sh
#   BROKER_COUNT=5 ./scripts/generate-certs.sh
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/create-stores.sh"

load_env

command -v openssl >/dev/null 2>&1 || { err "openssl is required on the host"; exit 1; }

OUT="${REPO_ROOT}/${CERT_OUTPUT_DIR}"
OSSL="${REPO_ROOT}/certs/openssl"
CA="${OUT}/ca"
PASS="${KAFKA_SSL_PASSWORD}"
CAPASS="${KAFKA_CA_PASSWORD}"
DAYS="${CERT_VALIDITY_DAYS}"

log "Generating lab PKI for ${BROKER_COUNT} broker(s) into ${CERT_OUTPUT_DIR}"
mkdir -p "${CA}"

export CERT_ORG CERT_ORG_UNIT

# ----------------------------------------------------------------------------
# 1. Root CA (self-signed)
# ----------------------------------------------------------------------------
if [[ ! -f "${CA}/root-ca.crt" ]]; then
  log "Creating Root CA"
  envsubst < "${OSSL}/root-ca.cnf" > "${CA}/root-ca.cnf"
  openssl genrsa -aes256 -passout "pass:${CAPASS}" -out "${CA}/root-ca.key" 4096
  openssl req -x509 -new -nodes \
    -key "${CA}/root-ca.key" -passin "pass:${CAPASS}" \
    -days "${DAYS}" -sha256 \
    -config "${CA}/root-ca.cnf" -extensions v3_ca \
    -out "${CA}/root-ca.crt"
  chmod 600 "${CA}/root-ca.key"
  ok "Root CA created"
else
  warn "Root CA already exists — reusing ${CA}/root-ca.crt"
fi

# ----------------------------------------------------------------------------
# 2. Intermediate CA (signed by Root CA)
# ----------------------------------------------------------------------------
if [[ ! -f "${CA}/intermediate-ca.crt" ]]; then
  log "Creating Intermediate CA"
  envsubst < "${OSSL}/intermediate-ca.cnf" > "${CA}/intermediate-ca.cnf"
  openssl genrsa -aes256 -passout "pass:${CAPASS}" -out "${CA}/intermediate-ca.key" 4096
  openssl req -new \
    -key "${CA}/intermediate-ca.key" -passin "pass:${CAPASS}" \
    -config "${CA}/intermediate-ca.cnf" \
    -out "${CA}/intermediate-ca.csr"
  openssl x509 -req \
    -in "${CA}/intermediate-ca.csr" \
    -CA "${CA}/root-ca.crt" -CAkey "${CA}/root-ca.key" -passin "pass:${CAPASS}" \
    -CAcreateserial \
    -days "${DAYS}" -sha256 \
    -extfile "${CA}/intermediate-ca.cnf" -extensions v3_intermediate_ca \
    -out "${CA}/intermediate-ca.crt"
  chmod 600 "${CA}/intermediate-ca.key"
  # Chain = intermediate + root (CA bundle used for stores and verification).
  cat "${CA}/intermediate-ca.crt" "${CA}/root-ca.crt" > "${CA}/chain.crt"
  ok "Intermediate CA created"
else
  warn "Intermediate CA already exists — reusing"
fi

# ----------------------------------------------------------------------------
# 3. Helper: issue one leaf cert (broker or client) signed by the intermediate
# ----------------------------------------------------------------------------
issue_leaf() {
  # args: <dir> <name> <cnf_file>
  local dir="$1" name="$2" cnf="$3"
  mkdir -p "${dir}"
  openssl genrsa -out "${dir}/${name}.key" 2048
  openssl req -new \
    -key "${dir}/${name}.key" \
    -config "${cnf}" \
    -out "${dir}/${name}.csr"
  openssl x509 -req \
    -in "${dir}/${name}.csr" \
    -CA "${CA}/intermediate-ca.crt" -CAkey "${CA}/intermediate-ca.key" -passin "pass:${CAPASS}" \
    -CAcreateserial \
    -days "${DAYS}" -sha256 \
    -extfile "${cnf}" -extensions v3_req \
    -out "${dir}/${name}.crt"
  chmod 600 "${dir}/${name}.key"
  # Full chain for the leaf: leaf + intermediate + root.
  cat "${dir}/${name}.crt" "${CA}/intermediate-ca.crt" "${CA}/root-ca.crt" > "${dir}/${name}.chain.crt"
}

# ----------------------------------------------------------------------------
# 4. Per-broker certificates + PKCS12 stores
# ----------------------------------------------------------------------------
for ((i=1; i<=BROKER_COUNT; i++)); do
  name="kafka${i}"
  dir="${OUT}/${name}"
  fqdn="$(broker_fqdn "${i}")"
  log "Issuing certificate for ${name} (SAN: ${name}, ${fqdn}, localhost, 127.0.0.1)"

  BROKER_NAME="${name}" BROKER_FQDN="${fqdn}" \
    envsubst < "${OSSL}/broker-san.cnf.tpl" > "${dir}.cnf.tmp" 2>/dev/null || {
      mkdir -p "${dir}"; BROKER_NAME="${name}" BROKER_FQDN="${fqdn}" \
      envsubst < "${OSSL}/broker-san.cnf.tpl" > "${dir}/${name}.cnf"; }
  mkdir -p "${dir}"
  [[ -f "${dir}.cnf.tmp" ]] && mv "${dir}.cnf.tmp" "${dir}/${name}.cnf"

  issue_leaf "${dir}" "${name}" "${dir}/${name}.cnf"

  make_keystore "${dir}/${name}.crt" "${dir}/${name}.key" "${CA}/chain.crt" \
                "${name}" "${dir}/kafka.server.keystore.p12" "${PASS}"
  install_trust_material "${CA}/chain.crt" "${dir}/ca-chain.crt"
  ok "${name}: key, cert, chain, keystore, CA trust material ready"
done

# ----------------------------------------------------------------------------
# 5. Client material (CA trust chain always; keystore only for mutual TLS)
# ----------------------------------------------------------------------------
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
  log "SSL_CLIENT_AUTH=required → generating client keystore (mutual TLS)"
  cat > "${CLIENT}/client.cnf" <<EOF
[ req ]
default_bits = 2048
default_md = sha256
prompt = no
distinguished_name = dn
req_extensions = v3_req
[ dn ]
O = ${CERT_ORG}
OU = ${CERT_ORG_UNIT}
CN = kafka-client
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
EOF
  issue_leaf "${CLIENT}" "kafka-client" "${CLIENT}/client.cnf"
  make_keystore "${CLIENT}/kafka-client.crt" "${CLIENT}/kafka-client.key" "${CA}/chain.crt" \
                "kafka-client" "${CLIENT}/kafka.client.keystore.p12" "${PASS}"
  cat >> "${CLIENT}/client-ssl.properties" <<EOF
ssl.keystore.type=PKCS12
ssl.keystore.location=${CERT_OUTPUT_DIR}/client/kafka.client.keystore.p12
ssl.keystore.password=${PASS}
ssl.key.password=${PASS}
EOF
  ok "Client keystore created (mutual TLS)"
fi

# Also publish the client config into config/ssl/ for the helper scripts.
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


ok "Certificate generation complete → ${CERT_OUTPUT_DIR}/"
log "Validating generated certificates..."
bash "${SCRIPT_DIR}/validate-certs.sh"
