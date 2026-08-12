
############################# SSL CONFIGS ####################################
ssl.keystore.type=PKCS12
ssl.keystore.location=/etc/kafka/secrets/kafka.server.keystore.p12
ssl.keystore.password=${KAFKA_SSL_PASSWORD}
ssl.key.password=${KAFKA_SSL_PASSWORD}

ssl.truststore.type=PKCS12
ssl.truststore.location=/etc/kafka/secrets/kafka.server.truststore.p12
ssl.truststore.password=${KAFKA_SSL_PASSWORD}

ssl.client.auth=${SSL_CLIENT_AUTH}
ssl.enabled.protocols=${SSL_ENABLED_PROTOCOLS}
ssl.endpoint.identification.algorithm=https
