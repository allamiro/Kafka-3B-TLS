#!/usr/bin/env bash
###############################################################################
# create-stores.sh — keystore and trust-material helpers (openssl-only).
#
# Sourced by generate-certs.sh and import-certs.sh. Uses ONLY openssl so the
# host does not need the Java `keytool`. PKCS12 trusted-cert entries are read
# correctly by Kafka on Java 17.
#
# Permissions: the keystore is written 0644 on purpose. The broker containers
# run as an unprivileged non-root user (uid 996) and bind-mount
# certs/generated/kafkaN read-only, so they must be able to read them. The
# contents are protected by KAFKA_SSL_PASSWORD; the bare private keys stay 0600.
#
# Functions:
#   make_keystore        <cert> <key> <chain_ca> <alias> <out.p12> <password>
#   install_trust_material <chain_ca> <out.crt>
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
  chmod 644 "${out}"
}

# Trust material: the CA chain as PEM. A PKCS12 built with `openssl -nokeys`
# is NOT usable as a Java truststore — the JDK only recognises trust anchors
# that keytool marked as trustedCertEntry, and Kafka fails at startup with
# "trustAnchors parameter must be non-empty". Kafka accepts PEM trust material
# directly (ssl.truststore.type=PEM, KIP-651), so this lab stays openssl-only.
install_trust_material() {
  local chain_ca="$1" out="$2"
  cp -f "${chain_ca}" "${out}"
  chmod 644 "${out}"
}
