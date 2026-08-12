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
# downloads.apache.org only carries the newest release of each line; once a
# version ages out it is served from archive.apache.org, so try both.
ARG KAFKA_DOWNLOAD_URL=https://downloads.apache.org/kafka/${KAFKA_VERSION}/${KAFKA_TGZ}
ARG KAFKA_ARCHIVE_URL=https://archive.apache.org/dist/kafka/${KAFKA_VERSION}/${KAFKA_TGZ}

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
        curl -fSL -o "/tmp/${KAFKA_TGZ}" "${KAFKA_DOWNLOAD_URL}" || { \
            echo "Not on downloads.apache.org; trying ${KAFKA_ARCHIVE_URL}"; \
            curl -fSL -o "/tmp/${KAFKA_TGZ}" "${KAFKA_ARCHIVE_URL}"; \
        }; \
    fi; \
    tar -xzf "/tmp/${KAFKA_TGZ}" -C /opt; \
    mv "/opt/kafka_${SCALA_VERSION}-${KAFKA_VERSION}" "${KAFKA_HOME}"; \
    rm -rf "/tmp/${KAFKA_TGZ}" /tmp/vendor; \
    mkdir -p /var/lib/kafka/data /etc/kafka/secrets "${KAFKA_HOME}/config"; \
    chown -R kafka:kafka "${KAFKA_HOME}" /var/lib/kafka /etc/kafka

# --chmod pins the in-image permissions so the build does not inherit a
# restrictive umask from the developer's working tree: the kafka user has to
# read the templates and execute the entrypoint.
COPY images/kafka/templates/ ${KAFKA_HOME}/templates/
COPY --chmod=0755 images/kafka/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod -R a+rX "${KAFKA_HOME}/templates" \
    && chown -R kafka:kafka "${KAFKA_HOME}/templates"

USER kafka
WORKDIR /opt/kafka

EXPOSE 9092 9093

# Readiness is enforced primarily by scripts/wait-for-kafka.sh + compose
# health checks; this is a lightweight liveness probe on the API versions.
# Exec form so the probe does not depend on a shell being PID 1's child.
HEALTHCHECK --interval=15s --timeout=10s --start-period=45s --retries=10 \
    CMD ["bash", "-c", "/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1 || /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9093 --command-config /opt/kafka/config/client-ssl.properties >/dev/null 2>&1"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
