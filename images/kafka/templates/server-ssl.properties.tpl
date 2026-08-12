
############################# SSL CONFIGS ####################################
ssl.keystore.type=PKCS12
ssl.keystore.location=/etc/kafka/secrets/kafka.server.keystore.p12
ssl.keystore.password=${KAFKA_SSL_PASSWORD}
ssl.key.password=${KAFKA_SSL_PASSWORD}

# Trust material is PEM, not PKCS12. Java only treats PKCS12 entries as trust
# anchors when they were written by keytool; an openssl -nokeys export gives
# "trustAnchors parameter must be non-empty". Kafka reads PEM trust material
# directly (KIP-651), which keeps the whole tool-chain openssl-only and needs
# no truststore password.
ssl.truststore.type=PEM
ssl.truststore.location=/etc/kafka/secrets/ca-chain.crt

ssl.client.auth=${SSL_CLIENT_AUTH}
ssl.enabled.protocols=${SSL_ENABLED_PROTOCOLS}
ssl.endpoint.identification.algorithm=https
