"""scripts/render-compose.py — topology generation and its validation rules.

The rendered Compose file is the single source of truth for cluster topology,
so these tests assert on the parsed YAML rather than on text.
"""
import pytest
import yaml


def services(doc, prefix):
    return sorted(name for name in doc["services"] if name.startswith(prefix))


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("brokers", ["0", "1", "2"])
def test_rejects_fewer_than_three_brokers(sandbox, brokers):
    proc = sandbox.render(["--brokers", brokers, "--zookeepers", "3"])
    assert proc.returncode == 2
    assert "broker count must be >= 3" in proc.stderr


@pytest.mark.parametrize("zks", ["1", "2", "4", "6"])
def test_rejects_even_or_undersized_zookeeper_quorum(sandbox, zks):
    proc = sandbox.render(["--brokers", "3", "--zookeepers", zks])
    assert proc.returncode == 2
    assert "ZooKeeper count must be 3 or 5" in proc.stderr


def test_rejects_unknown_security_mode(sandbox):
    proc = sandbox.render(["--security-mode", "sasl"])
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


@pytest.mark.parametrize("zks", ["3", "5"])
def test_accepts_supported_quorum_sizes(sandbox, zks):
    doc = sandbox.render_yaml(["--brokers", "3", "--zookeepers", zks])
    assert len(services(doc, "zookeeper")) == int(zks)


# ---------------------------------------------------------------------------
# Defaults and structure
# ---------------------------------------------------------------------------


def test_defaults_are_three_brokers_three_zookeepers_dual(sandbox):
    doc = sandbox.render_yaml()
    assert services(doc, "kafka") == ["kafka1", "kafka2", "kafka3"]
    assert services(doc, "zookeeper") == ["zookeeper1", "zookeeper2", "zookeeper3"]
    assert doc["name"] == "kafka-zookeeper-lab"
    assert doc["networks"]["kafka-net"]["name"] == "kafka-net"


def test_every_service_gets_its_own_named_volumes(sandbox):
    doc = sandbox.render_yaml(["--brokers", "5", "--zookeepers", "3"])
    volumes = set(doc["volumes"])
    for i in range(1, 6):
        assert "kafka{}-data".format(i) in volumes
    for i in range(1, 4):
        assert "zookeeper{}-data".format(i) in volumes
        assert "zookeeper{}-log".format(i) in volumes


def test_broker_ids_are_unique_and_sequential(sandbox):
    doc = sandbox.render_yaml(["--brokers", "5"])
    ids = [doc["services"]["kafka{}".format(i)]["environment"]["BROKER_ID"] for i in range(1, 6)]
    assert ids == ["1", "2", "3", "4", "5"]
    assert len(set(ids)) == len(ids)


def test_brokers_wait_for_every_zookeeper_to_be_healthy(sandbox):
    doc = sandbox.render_yaml(["--brokers", "3", "--zookeepers", "5"])
    depends = doc["services"]["kafka1"]["depends_on"]
    assert sorted(depends) == ["zookeeper{}".format(i) for i in range(1, 6)]
    assert all(d["condition"] == "service_healthy" for d in depends.values())


def test_zookeeper_ensemble_definition_is_identical_on_every_node(sandbox):
    doc = sandbox.render_yaml(["--zookeepers", "3"])
    expected = "|".join(
        "server.{i}=zookeeper{i}:2888:3888;2181".format(i=i) for i in range(1, 4)
    )
    for i in range(1, 4):
        env = doc["services"]["zookeeper{}".format(i)]["environment"]
        assert env["ZOO_SERVERS"] == expected
        assert env["ZOO_MY_ID"] == str(i)


def test_brokers_connect_to_the_full_zookeeper_connect_string(sandbox):
    doc = sandbox.render_yaml(["--zookeepers", "5"])
    expected = ",".join("zookeeper{}:2181".format(i) for i in range(1, 6))
    assert doc["services"]["kafka1"]["environment"]["KAFKA_ZOOKEEPER_CONNECT"] == expected


def test_quorum_ports_are_never_published_to_the_host(sandbox):
    doc = sandbox.render_yaml()
    for i in range(1, 4):
        assert "ports" not in doc["services"]["zookeeper{}".format(i)]


# ---------------------------------------------------------------------------
# Security modes
# ---------------------------------------------------------------------------


def test_dual_mode_publishes_both_listeners(sandbox):
    doc = sandbox.render_yaml(["--security-mode", "dual"])
    assert doc["services"]["kafka1"]["ports"] == ["19092:9092", "19093:9093"]
    assert doc["services"]["kafka2"]["ports"] == ["29092:9092", "29093:9093"]
    assert doc["services"]["kafka3"]["ports"] == ["39092:9092", "39093:9093"]


def test_plaintext_mode_has_no_ssl_port_certs_or_password(sandbox):
    doc = sandbox.render_yaml(["--security-mode", "plaintext"])
    kafka1 = doc["services"]["kafka1"]
    assert kafka1["ports"] == ["19092:9092"]
    assert kafka1["volumes"] == ["kafka1-data:/var/lib/kafka/data"]
    assert "KAFKA_SSL_PASSWORD" not in kafka1["environment"]
    assert "9093" not in yaml.safe_dump(kafka1)


def test_plaintext_mode_forces_plaintext_inter_broker_traffic(sandbox):
    """--inter-broker SSL is impossible without an SSL listener; it is overridden."""
    doc = sandbox.render_yaml(["--security-mode", "plaintext", "--inter-broker", "SSL"])
    env = doc["services"]["kafka1"]["environment"]
    assert env["INTER_BROKER_LISTENER_NAME"] == "PLAINTEXT"


def test_ssl_mode_publishes_only_the_ssl_port_and_mounts_per_broker_certs(sandbox):
    doc = sandbox.render_yaml(["--security-mode", "ssl"])
    for i in (1, 2, 3):
        kafka = doc["services"]["kafka{}".format(i)]
        assert kafka["ports"] == ["{}9093:9093".format(i)]
        assert "./certs/generated/kafka{}:/etc/kafka/secrets:ro".format(i) in kafka["volumes"]
        assert kafka["environment"]["INTER_BROKER_LISTENER_NAME"] == "SSL"


def test_ssl_mode_healthcheck_speaks_tls(sandbox):
    doc = sandbox.render_yaml(["--security-mode", "ssl"])
    test = doc["services"]["kafka1"]["healthcheck"]["test"][1]
    assert "localhost:9093" in test
    assert "--command-config /opt/kafka/config/client-ssl.properties" in test


def test_plaintext_and_dual_healthchecks_use_the_plaintext_port(sandbox):
    for mode in ("plaintext", "dual"):
        doc = sandbox.render_yaml(["--security-mode", mode])
        test = doc["services"]["kafka1"]["healthcheck"]["test"][1]
        assert "localhost:9092" in test, mode


def test_certificate_mounts_are_read_only(sandbox):
    doc = sandbox.render_yaml(["--security-mode", "dual", "--brokers", "3"])
    mounts = [v for v in doc["services"]["kafka1"]["volumes"] if "secrets" in v]
    assert mounts == ["./certs/generated/kafka1:/etc/kafka/secrets:ro"]


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("brokers", [3, 5, 7])
def test_scales_to_larger_broker_counts(sandbox, brokers):
    doc = sandbox.render_yaml(["--brokers", str(brokers), "--zookeepers", "3"])
    assert len(services(doc, "kafka")) == brokers
    assert len(services(doc, "zookeeper")) == 3, "ZooKeeper must not scale with brokers"


def test_brokers_beyond_index_nine_are_network_only(sandbox):
    """Host ports are <index><port>, which stops being unique past index 9."""
    proc = sandbox.render(["--brokers", "12", "--zookeepers", "3"])
    assert proc.returncode == 0
    doc = yaml.safe_load(proc.stdout)
    assert "ports" in doc["services"]["kafka9"]
    for i in (10, 11, 12):
        assert "ports" not in doc["services"]["kafka{}".format(i)]
    assert "no host port mapping" in proc.stdout


def test_host_ports_never_collide(sandbox):
    doc = sandbox.render_yaml(["--brokers", "9", "--security-mode", "dual"])
    published = [p.split(":")[0] for s in doc["services"].values() for p in s.get("ports", [])]
    assert len(published) == len(set(published))


# ---------------------------------------------------------------------------
# Environment defaults and output
# ---------------------------------------------------------------------------


def test_dotenv_supplies_defaults_when_flags_are_omitted(sandbox):
    sandbox.write_env(
        {"BROKER_COUNT": "5", "ZOOKEEPER_COUNT": "5", "KAFKA_SECURITY_MODE": "plaintext"}
    )
    doc = sandbox.render_yaml()
    assert len(services(doc, "kafka")) == 5
    assert len(services(doc, "zookeeper")) == 5
    assert doc["services"]["kafka1"]["ports"] == ["19092:9092"]


def test_environment_overrides_dotenv(sandbox):
    sandbox.write_env({"BROKER_COUNT": "5"})
    doc = sandbox.render_yaml(env={"BROKER_COUNT": "3"})
    assert len(services(doc, "kafka")) == 3


def test_explicit_flags_win_over_everything(sandbox):
    sandbox.write_env({"BROKER_COUNT": "5"})
    doc = sandbox.render_yaml(["--brokers", "7"], env={"BROKER_COUNT": "3"})
    assert len(services(doc, "kafka")) == 7


def test_output_flag_writes_a_file(sandbox):
    proc = sandbox.render(["-o", "docker-compose.generated.yml"])
    assert proc.returncode == 0
    assert proc.stdout == ""
    written = sandbox.read("docker-compose.generated.yml")
    assert yaml.safe_load(written)["services"]["kafka1"]["container_name"] == "kafka1"


def test_rendering_is_deterministic(sandbox):
    first = sandbox.render(["--brokers", "5", "--security-mode", "dual"])
    second = sandbox.render(["--brokers", "5", "--security-mode", "dual"])
    assert first.stdout == second.stdout


def test_output_carries_a_do_not_edit_banner(sandbox):
    proc = sandbox.render(["--brokers", "3", "--zookeepers", "3"])
    assert "DO NOT EDIT BY HAND" in proc.stdout
    assert "brokers=3  zookeepers=3  security_mode=dual" in proc.stdout


def test_image_versions_stay_overridable_from_the_environment(sandbox):
    doc = sandbox.render_yaml()
    kafka_args = doc["services"]["kafka1"]["build"]["args"]
    assert kafka_args["KAFKA_VERSION"] == "${KAFKA_VERSION:-3.9.2}"
    assert kafka_args["SCALA_VERSION"] == "${SCALA_VERSION:-2.13}"
    zk_args = doc["services"]["zookeeper1"]["build"]["args"]
    assert zk_args["ZOOKEEPER_VERSION"] == "${ZOOKEEPER_VERSION:-3.9.5}"
