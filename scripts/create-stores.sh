#!/usr/bin/env bash
###############################################################################
# create-stores.sh — PKCS12 keystore/truststore helpers (openssl-only).
#
# Sourced by generate-certs.sh and import-certs.sh. Uses ONLY openssl so the
# host does not need the Java `keytool`. PKCS12 trusted-cert entries are read
# correctly by Kafka on Java 17.
#
# Functions:
#   make_keystore   <cert> <key> <chain_ca> <alias> <out.p12> <password>
#   make_truststore <chain_ca> <out.p12> <password>
###############################################################################

# Server/client keystore: private key + full chain, single alias.
make_keystore() {
  local cert="$1" key="$2" chain_ca="$3" alias="$4" out="$5" pass="$6"
  openssl pkcs12 -export \
    -in "${cert}" \
    -inkey "${key}" \
    -certfile "${chain_ca}" \
    -name "${alias}" \
    -out "${out}" \
    -passout "pass:${pass}"
  chmod 600 "${out}"
}

# Truststore: CA chain only (no private key). Java 17 reads these as trusted
# certificate entries.
make_truststore() {
  local chain_ca="$1" out="$2" pass="$3"
  openssl pkcs12 -export -nokeys \
    -in "${chain_ca}" \
    -caname "kafka-ca" \
    -out "${out}" \
    -passout "pass:${pass}"
  chmod 600 "${out}"
}
