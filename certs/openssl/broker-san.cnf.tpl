# OpenSSL config TEMPLATE for a Kafka broker certificate.
# Rendered per broker by generate-certs.sh via envsubst. Variables:
#   BROKER_NAME  e.g. kafka1
#   BROKER_FQDN  e.g. KAFKA0001.hq.corp
#   CERT_ORG / CERT_ORG_UNIT
[ req ]
default_bits        = 2048
default_md          = sha256
prompt              = no
distinguished_name  = dn
req_extensions      = v3_req

[ dn ]
O  = ${CERT_ORG}
OU = ${CERT_ORG_UNIT}
CN = ${BROKER_NAME}

[ v3_req ]
basicConstraints       = CA:FALSE
keyUsage               = critical, digitalSignature, keyEncipherment
extendedKeyUsage       = serverAuth, clientAuth
subjectAltName         = @alt_names

[ alt_names ]
DNS.1 = ${BROKER_NAME}
DNS.2 = ${BROKER_FQDN}
DNS.3 = localhost
IP.1  = 127.0.0.1
