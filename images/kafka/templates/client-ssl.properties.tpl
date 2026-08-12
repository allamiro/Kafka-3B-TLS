security.protocol=SSL
ssl.truststore.type=PKCS12
ssl.truststore.location=/etc/kafka/secrets/kafka.server.truststore.p12
ssl.truststore.password=${KAFKA_SSL_PASSWORD}
ssl.endpoint.identification.algorithm=https
