"""End-to-end: an SSL-only cluster with SSL inter-broker traffic.

Covers what the unit tests cannot: that the generated PKCS12 stores are
actually accepted by Kafka's JVM, that the TLS handshake succeeds against the
broker's SANs, and that no cleartext listener is left open.
"""
import pytest

from cluster import BROKERS, start_cluster, stop_cluster

pytestmark = [pytest.mark.integration, pytest.mark.ssl]

TOPIC = "itest-ssl"
MESSAGES = ["encrypted-one", "encrypted-two", "encrypted-three"]
CLIENT_CONFIG = "/opt/kafka/config/client-ssl.properties"


@pytest.fixture(scope="module")
def cluster(repo_root):
    running = start_cluster(repo_root, "ssl")
    yield running
    stop_cluster(running)


# ---------------------------------------------------------------------------
# Listener configuration
# ---------------------------------------------------------------------------


def test_only_the_ssl_listener_is_configured(cluster):
    conf = cluster.exec("kafka1", ["cat", "/opt/kafka/config/server.properties"]).stdout
    assert "listeners=SSL://0.0.0.0:9093" in conf
    assert "advertised.listeners=SSL://kafka1:9093" in conf
    assert "PLAINTEXT" not in conf.split("listener.security.protocol.map=")[1].splitlines()[0]


def test_inter_broker_traffic_is_encrypted(cluster):
    conf = cluster.exec("kafka1", ["cat", "/opt/kafka/config/server.properties"]).stdout
    assert "inter.broker.listener.name=SSL" in conf
    # Setting security.inter.broker.protocol as well makes Kafka refuse to boot.
    assert not [ln for ln in conf.splitlines() if ln.startswith("security.inter.broker.protocol")]


def test_hostname_verification_is_enabled(cluster):
    conf = cluster.exec("kafka1", ["cat", "/opt/kafka/config/server.properties"]).stdout
    assert "ssl.endpoint.identification.algorithm=https" in conf


def test_the_cleartext_port_is_closed(cluster):
    proc = cluster.exec("kafka1", ["bash", "-c", "nc -z -w 2 localhost 9092; echo rc=$?"], check=False)
    assert "rc=0" not in proc.stdout


def test_trust_material_is_pem(cluster):
    conf = cluster.exec("kafka1", ["cat", "/opt/kafka/config/server.properties"]).stdout
    assert "ssl.truststore.type=PEM" in conf
    assert "ssl.truststore.location=/etc/kafka/secrets/ca-chain.crt" in conf


def test_keystores_are_mounted_read_only(cluster):
    proc = cluster.exec("kafka1", ["bash", "-c", "touch /etc/kafka/secrets/probe; echo rc=$?"], check=False)
    assert "rc=0" not in proc.stdout


# ---------------------------------------------------------------------------
# TLS handshake
# ---------------------------------------------------------------------------


def test_the_broker_presents_its_certificate_chain(cluster):
    proc = cluster.exec(
        "kafka1",
        ["bash", "-c", "echo | openssl s_client -connect kafka1:9093 -showcerts 2>/dev/null"],
    )
    assert "subject=" in proc.stdout
    assert "CN = kafka1" in proc.stdout or "CN=kafka1" in proc.stdout
    assert proc.stdout.count("BEGIN CERTIFICATE") >= 2, "chain should include the intermediate"


def test_the_handshake_verifies_against_the_lab_certificate_authority(cluster):
    proc = cluster.exec(
        "kafka1",
        ["bash", "-c",
         "echo | openssl s_client -connect kafka1:9093 "
         "-CAfile /etc/kafka/secrets/ca-chain.crt -verify_return_error 2>&1 | "
         "grep -E 'Verify return code|verify error'"],
        check=False,
    )
    assert "Verify return code: 0 (ok)" in proc.stdout, proc.stdout


def test_modern_tls_versions_are_negotiated(cluster):
    proc = cluster.exec(
        "kafka1",
        ["bash", "-c", "echo | openssl s_client -connect kafka1:9093 2>/dev/null | grep -E '^\\s*Protocol'"],
    )
    assert "TLSv1.3" in proc.stdout or "TLSv1.2" in proc.stdout


def test_obsolete_tls_versions_are_refused(cluster):
    proc = cluster.exec(
        "kafka1",
        ["bash", "-c", "echo | openssl s_client -connect kafka1:9093 -tls1_1 2>&1; echo rc=$?"],
        check=False,
    )
    assert "rc=0" not in proc.stdout


# ---------------------------------------------------------------------------
# Data plane over TLS
# ---------------------------------------------------------------------------


def test_the_cluster_forms_over_ssl(cluster):
    proc = cluster.exec(
        "kafka1",
        ["kafka-broker-api-versions.sh", "--bootstrap-server", "kafka1:9093",
         "--command-config", CLIENT_CONFIG],
    )
    for i in range(1, BROKERS + 1):
        assert "kafka{}:9093".format(i) in proc.stdout


def test_create_a_replicated_topic_over_ssl(cluster):
    cluster.kafka_topics(["--create", "--if-not-exists", "--topic", TOPIC,
                          "--partitions", "3", "--replication-factor", str(BROKERS)])
    assert TOPIC in cluster.kafka_topics(["--list"]).stdout


def test_replication_works_over_encrypted_inter_broker_links(cluster):
    described = cluster.kafka_topics(["--describe", "--topic", TOPIC]).stdout
    for line in described.splitlines():
        if "Isr:" not in line:
            continue
        isr = line.split("Isr:")[1].strip().split()[0]
        assert len(isr.split(",")) == BROKERS, line


def test_produce_and_consume_over_ssl(cluster):
    cluster.exec(
        "kafka1",
        ["kafka-console-producer.sh", "--bootstrap-server", "kafka1:9093", "--topic", TOPIC,
         "--producer.config", CLIENT_CONFIG],
        stdin="\n".join(MESSAGES) + "\n",
    )
    proc = cluster.exec(
        "kafka1",
        ["kafka-console-consumer.sh", "--bootstrap-server", "kafka1:9093", "--topic", TOPIC,
         "--consumer.config", CLIENT_CONFIG, "--from-beginning",
         "--max-messages", str(len(MESSAGES)), "--timeout-ms", "60000"],
    )
    assert sorted(proc.stdout.split()) == sorted(MESSAGES)


def test_a_client_without_the_truststore_cannot_connect(cluster):
    """The negative control: TLS is enforced, not merely offered."""
    proc = cluster.exec(
        "kafka1",
        ["kafka-topics.sh", "--bootstrap-server", "kafka1:9093", "--list", "--command-config", "/dev/null"],
        check=False,
        timeout=120,
    )
    assert proc.returncode != 0
