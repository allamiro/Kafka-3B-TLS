# syntax=docker/dockerfile:1
###############################################################################
# Apache Kafka 3.9.2 image (ZooKeeper mode — NOT KRaft).
#
# Build context MUST be the repository root so that vendor/ is reachable for
# air-gapped builds.
#
#   Internet build : downloads kafka_2.13-3.9.2.tgz from downloads.apache.org
#   Air-gapped     : place vendor/kafka_2.13-3.9.2.tgz and it is used instead.
###############################################################################
FROM eclipse-temurin:17-jre

ARG KAFKA_VERSION=3.9.2
ARG SCALA_VERSION=2.13
ARG KAFKA_TGZ=kafka_${SCALA_VERSION}-${KAFKA_VERSION}.tgz
ARG KAFKA_DOWNLOAD_URL=https://downloads.apache.org/kafka/${KAFKA_VERSION}/${KAFKA_TGZ}

ENV KAFKA_HOME=/opt/kafka \
    PATH=/opt/kafka/bin:$PATH

# Runtime deps: gettext-base (envsubst) for templating, openssl/netcat for
# health/wait helpers.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gettext-base netcat-openbsd curl openssl; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd -r -g 996 kafka; \
    useradd -r -u 996 -g kafka -s /usr/sbin/nologin -d /opt/kafka kafka

COPY vendor/ /tmp/vendor/

RUN set -eux; \
    if [ -f "/tmp/vendor/${KAFKA_TGZ}" ]; then \
        echo "Using vendored ${KAFKA_TGZ} (air-gapped build)"; \
        cp "/tmp/vendor/${KAFKA_TGZ}" "/tmp/${KAFKA_TGZ}"; \
    else \
        echo "Downloading ${KAFKA_DOWNLOAD_URL}"; \
        curl -fSL -o "/tmp/${KAFKA_TGZ}" "${KAFKA_DOWNLOAD_URL}"; \
    fi; \
    tar -xzf "/tmp/${KAFKA_TGZ}" -C /opt; \
    mv "/opt/kafka_${SCALA_VERSION}-${KAFKA_VERSION}" "${KAFKA_HOME}"; \
    rm -rf "/tmp/${KAFKA_TGZ}" /tmp/vendor; \
    mkdir -p /var/lib/kafka/data /etc/kafka/secrets "${KAFKA_HOME}/config"; \
    chown -R kafka:kafka "${KAFKA_HOME}" /var/lib/kafka /etc/kafka

COPY images/kafka/templates/ ${KAFKA_HOME}/templates/
COPY images/kafka/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && chown -R kafka:kafka "${KAFKA_HOME}/templates"

USER kafka
WORKDIR /opt/kafka

EXPOSE 9092 9093

# Readiness is enforced primarily by scripts/wait-for-kafka.sh + compose
# health checks; this is a lightweight liveness probe on the API versions.
HEALTHCHECK --interval=15s --timeout=10s --start-period=45s --retries=10 \
    CMD bash -c '/opt/kafka/bin/kafka-broker-api-versions.sh \
        --bootstrap-server localhost:9092 >/dev/null 2>&1 \
        || /opt/kafka/bin/kafka-broker-api-versions.sh \
        --bootstrap-server localhost:9093 \
        --command-config /etc/kafka/secrets/healthcheck.properties >/dev/null 2>&1' \
        || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
