"""End-to-end: a PLAINTEXT 3-broker cluster on a 3-node ZooKeeper ensemble."""
import pytest

from cluster import BROKERS, ZOOKEEPERS, start_cluster, stop_cluster

pytestmark = pytest.mark.integration

TOPIC = "itest-plaintext"
MESSAGES = ["alpha", "bravo", "charlie", "delta", "echo"]


@pytest.fixture(scope="module")
def cluster(repo_root):
    running = start_cluster(repo_root, "plaintext")
    yield running
    stop_cluster(running)


# ---------------------------------------------------------------------------
# Cluster formation
# ---------------------------------------------------------------------------


def test_every_zookeeper_answers_the_liveness_probe(cluster):
    for i in range(1, ZOOKEEPERS + 1):
        proc = cluster.exec("zookeeper{}".format(i),
                            ["bash", "-c", "echo ruok | nc -w 2 localhost 2181"])
        assert "imok" in proc.stdout


def test_the_ensemble_elects_exactly_one_leader(cluster):
    roles = []
    for i in range(1, ZOOKEEPERS + 1):
        proc = cluster.exec("zookeeper{}".format(i),
                            ["bash", "-c", "echo srvr | nc -w 2 localhost 2181"])
        roles += [line.split(":")[1].strip() for line in proc.stdout.splitlines()
                  if line.startswith("Mode:")]
    assert roles.count("leader") == 1, roles
    assert roles.count("follower") == ZOOKEEPERS - 1, roles


def test_every_broker_registers_in_zookeeper(cluster):
    proc = cluster.exec("zookeeper1", ["zkCli.sh", "-server", "localhost:2181", "ls", "/brokers/ids"])
    for i in range(1, BROKERS + 1):
        assert str(i) in proc.stdout, proc.stdout


def test_the_cluster_reports_all_brokers(cluster):
    proc = cluster.exec("kafka1", ["kafka-broker-api-versions.sh", "--bootstrap-server", cluster.bootstrap])
    for i in range(1, BROKERS + 1):
        assert "kafka{}:9092".format(i) in proc.stdout


def test_brokers_advertise_their_service_name_not_localhost(cluster):
    """Clients bootstrap off kafka1 and must be handed routable addresses."""
    proc = cluster.exec("kafka1", ["grep", "advertised.listeners", "/opt/kafka/config/server.properties"])
    assert proc.stdout.strip() == "advertised.listeners=PLAINTEXT://kafka1:9092"


def test_no_ssl_listener_is_open_in_plaintext_mode(cluster):
    proc = cluster.exec("kafka1", ["bash", "-c", "nc -z -w 2 localhost 9093; echo rc=$?"], check=False)
    assert "rc=0" not in proc.stdout


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


def test_create_a_replicated_topic(cluster):
    cluster.kafka_topics(["--create", "--if-not-exists", "--topic", TOPIC,
                          "--partitions", "3", "--replication-factor", str(BROKERS)])
    assert TOPIC in cluster.kafka_topics(["--list"]).stdout


def test_partitions_are_fully_replicated_and_in_sync(cluster):
    described = cluster.kafka_topics(["--describe", "--topic", TOPIC]).stdout
    partitions = [line for line in described.splitlines() if "\tPartition:" in line or " Partition:" in line]
    assert len(partitions) == 3, described
    for line in partitions:
        replicas = line.split("Replicas:")[1].split("Isr:")[0].strip()
        isr = line.split("Isr:")[1].strip().split()[0]
        assert sorted(replicas.split(",")) == sorted(isr.split(",")), line


def test_leadership_is_spread_across_brokers(cluster):
    described = cluster.kafka_topics(["--describe", "--topic", TOPIC]).stdout
    leaders = {line.split("Leader:")[1].split()[0] for line in described.splitlines() if "Leader:" in line}
    assert len(leaders) > 1, "all partitions led by one broker:\n{}".format(described)


def test_replication_factor_above_the_broker_count_is_refused(cluster):
    proc = cluster.kafka_topics(
        ["--create", "--topic", "itest-too-many-replicas", "--partitions", "1",
         "--replication-factor", str(BROKERS + 1)],
        check=False,
    )
    assert proc.returncode != 0
    assert "replication factor" in (proc.stdout + proc.stderr).lower()


# ---------------------------------------------------------------------------
# Data plane
# ---------------------------------------------------------------------------


def test_produce_and_consume_over_plaintext(cluster):
    cluster.exec(
        "kafka1",
        ["kafka-console-producer.sh", "--bootstrap-server", cluster.bootstrap, "--topic", TOPIC],
        stdin="\n".join(MESSAGES) + "\n",
    )
    proc = cluster.exec(
        "kafka1",
        ["kafka-console-consumer.sh", "--bootstrap-server", cluster.bootstrap, "--topic", TOPIC,
         "--from-beginning", "--max-messages", str(len(MESSAGES)), "--timeout-ms", "60000"],
    )
    assert sorted(proc.stdout.split()) == sorted(MESSAGES)


def test_a_consumer_group_commits_its_offsets(cluster):
    group = "itest-group"
    cluster.exec(
        "kafka1",
        ["kafka-console-consumer.sh", "--bootstrap-server", cluster.bootstrap, "--topic", TOPIC,
         "--from-beginning", "--group", group, "--max-messages", str(len(MESSAGES)), "--timeout-ms", "60000"],
    )
    proc = cluster.exec(
        "kafka1",
        ["kafka-consumer-groups.sh", "--bootstrap-server", cluster.bootstrap, "--describe", "--group", group],
    )
    assert TOPIC in proc.stdout
    assert "CURRENT-OFFSET" in proc.stdout


def test_messages_survive_a_broker_restart(cluster):
    """Data lives on a named volume, so a bounce must not lose the log."""
    cluster.compose(["restart", "kafka2"], timeout=300, check=True)
    cluster.wait_until_healthy()
    proc = cluster.exec(
        "kafka1",
        ["kafka-console-consumer.sh", "--bootstrap-server", cluster.bootstrap, "--topic", TOPIC,
         "--from-beginning", "--max-messages", str(len(MESSAGES)), "--timeout-ms", "90000"],
    )
    assert sorted(proc.stdout.split()) == sorted(MESSAGES)
