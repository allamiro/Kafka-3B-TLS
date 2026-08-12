#!/usr/bin/env bash
###############################################################################
# validate-certs.sh — verify a broker cert/key pair and its SANs.
#
# Can be run standalone:
#   ./scripts/validate-certs.sh            # validate all generated/imported brokers
# or sourced for its functions: cert_key_match, cert_has_san, validate_broker.
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_env.sh"

# Returns 0 if the certificate and key share the same public modulus.
# SHA-256 rather than MD5: MD5 is unavailable on FIPS-enabled hosts.
cert_key_match() {
  local cert="$1" key="$2"
  local cmod kmod
  cmod="$(openssl x509 -noout -modulus -in "${cert}" 2>/dev/null | openssl sha256)"
  kmod="$(openssl rsa  -noout -modulus -in "${key}"  2>/dev/null | openssl sha256)"
  [[ -n "${cmod}" && "${cmod}" == "${kmod}" ]]
}

# Returns 0 if the certificate's SAN list contains the given entry (e.g. DNS:kafka1).
cert_has_san() {
  local cert="$1" san="$2"
  openssl x509 -noout -ext subjectAltName -in "${cert}" 2>/dev/null | grep -q "${san}"
}

# Validate one broker directory. Args: <index> <dir> [<root_ca_for_chain>]
validate_broker() {
  local idx="$1" dir="$2" ca_bundle="${3:-}"
  local name="kafka${idx}"
  local fqdn; fqdn="$(broker_fqdn "${idx}")"
  local cert="${dir}/${name}.crt" key="${dir}/${name}.key"

  [[ -f "${cert}" ]] || { err "missing certificate: ${cert}"; return 1; }
  [[ -f "${key}"  ]] || { err "missing private key: ${key}"; return 1; }

  if ! cert_key_match "${cert}" "${key}"; then
    err "${name}: certificate and private key do NOT match"
    return 1
  fi

  # Required SAN: DNS:kafkaN. Recommended (warn-only): fqdn, localhost, 127.0.0.1.
  if ! cert_has_san "${cert}" "DNS:${name}"; then
    err "${name}: required SAN 'DNS:${name}' is MISSING"
    return 1
  fi
  cert_has_san "${cert}" "DNS:${fqdn}"      || warn "${name}: recommended SAN 'DNS:${fqdn}' missing"
  cert_has_san "${cert}" "DNS:localhost"    || warn "${name}: recommended SAN 'DNS:localhost' missing"
  cert_has_san "${cert}" "127.0.0.1"        || warn "${name}: recommended SAN 'IP:127.0.0.1' missing"

  # Chain validation (only when a CA bundle is supplied).
  if [[ -n "${ca_bundle}" && -f "${ca_bundle}" ]]; then
    if ! openssl verify -CAfile "${ca_bundle}" "${cert}" >/dev/null 2>&1; then
      err "${name}: certificate does NOT validate against CA bundle ${ca_bundle}"
      return 1
    fi
  fi

  ok "${name}: cert/key match, SANs present, chain valid"
  return 0
}

main() {
  load_env
  local out="${REPO_ROOT}/${CERT_OUTPUT_DIR}"
  local ca_bundle="${out}/ca/chain.crt"
  local rc=0
  for ((i=1; i<=BROKER_COUNT; i++)); do
    validate_broker "${i}" "${out}/kafka${i}" "${ca_bundle}" || rc=1
  done
  [[ "${rc}" -eq 0 ]] && ok "All ${BROKER_COUNT} broker certificates validated." \
                      || err "Certificate validation FAILED."
  return "${rc}"
}

# Run main only if executed directly (not when sourced).
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
