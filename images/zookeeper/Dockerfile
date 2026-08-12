# syntax=docker/dockerfile:1
###############################################################################
# Apache ZooKeeper 3.9.5 image (external ZooKeeper for ZooKeeper-mode Kafka)
#
# Build context MUST be the repository root so that vendor/ is reachable for
# air-gapped builds. The render script / Makefile set this up for you.
#
#   Internet build : downloads the tarball from downloads.apache.org
#   Air-gapped     : place vendor/apache-zookeeper-3.9.5-bin.tar.gz and it is
#                    used automatically instead of downloading.
###############################################################################
FROM eclipse-temurin:17-jre

ARG ZOOKEEPER_VERSION=3.9.5
ARG ZOOKEEPER_TGZ=apache-zookeeper-${ZOOKEEPER_VERSION}-bin.tar.gz
ARG ZOOKEEPER_DOWNLOAD_URL=https://downloads.apache.org/zookeeper/zookeeper-${ZOOKEEPER_VERSION}/${ZOOKEEPER_TGZ}

ENV ZOOKEEPER_HOME=/opt/zookeeper \
    PATH=/opt/zookeeper/bin:$PATH

# Runtime deps: gettext-base (envsubst) for templating, netcat for healthcheck.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gettext-base netcat-openbsd curl; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd -r -g 994 zookeeper; \
    useradd -r -u 994 -g zookeeper -s /usr/sbin/nologin -d /opt/zookeeper zookeeper

# Bring in the (possibly empty) vendor dir for offline builds.
COPY vendor/ /tmp/vendor/

RUN set -eux; \
    if [ -f "/tmp/vendor/${ZOOKEEPER_TGZ}" ]; then \
        echo "Using vendored ${ZOOKEEPER_TGZ} (air-gapped build)"; \
        cp "/tmp/vendor/${ZOOKEEPER_TGZ}" "/tmp/${ZOOKEEPER_TGZ}"; \
    else \
        echo "Downloading ${ZOOKEEPER_DOWNLOAD_URL}"; \
        curl -fSL -o "/tmp/${ZOOKEEPER_TGZ}" "${ZOOKEEPER_DOWNLOAD_URL}"; \
    fi; \
    tar -xzf "/tmp/${ZOOKEEPER_TGZ}" -C /opt; \
    mv "/opt/apache-zookeeper-${ZOOKEEPER_VERSION}-bin" "${ZOOKEEPER_HOME}"; \
    rm -rf "/tmp/${ZOOKEEPER_TGZ}" /tmp/vendor; \
    mkdir -p /var/lib/zookeeper/data /var/lib/zookeeper/log "${ZOOKEEPER_HOME}/conf"; \
    chown -R zookeeper:zookeeper "${ZOOKEEPER_HOME}" /var/lib/zookeeper

COPY images/zookeeper/templates/ ${ZOOKEEPER_HOME}/conf-templates/
COPY images/zookeeper/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && chown -R zookeeper:zookeeper "${ZOOKEEPER_HOME}/conf-templates"

USER zookeeper
WORKDIR /opt/zookeeper

EXPOSE 2181 2888 3888

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=10 \
    CMD echo ruok | nc -w 2 localhost 2181 | grep -q imok || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
