"""images/*/entrypoint.sh — configuration rendering and fail-fast behaviour.

The entrypoints run as PID 1 in the containers, so a misrendered
server.properties or a silently missing keystore would surface as a crash loop.
These tests drive the real entrypoints against a stub Kafka installation, plus
a static check that every template placeholder is actually exported.
"""
import os
import re
import shutil

import pytest

PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")

KAFKA_TEMPLATES = {
    "server.properties.tpl": "images/kafka/entrypoint.sh",
    "server-ssl.properties.tpl": "images/kafka/entrypoint.sh",
    "client-ssl.properties.tpl": "images/kafka/entrypoint.sh",
}


# ---------------------------------------------------------------------------
# Static contract: templates vs entrypoint exports
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template,entrypoint", sorted(KAFKA_TEMPLATES.items()))
def test_kafka_template_placeholders_are_exported_by_the_entrypoint(repo_root, template, entrypoint):
    body = (repo_root / "images" / "kafka" / "templates" / template).read_text()
    script = (repo_root / entrypoint).read_text()
    for name in sorted(set(PLACEHOLDER.findall(body))):
        assert re.search(r"^\s*export {}=".format(name), script, re.M), (
            "{} uses ${{{}}} but {} never exports it".format(template, name, entrypoint)
        )


def test_zookeeper_template_placeholders_are_exported_by_the_entrypoint(repo_root):
    body = (repo_root / "images/zookeeper/templates/zoo.cfg.tpl").read_text()
    script = (repo_root / "images/zookeeper/entrypoint.sh").read_text()
    for name in sorted(set(PLACEHOLDER.findall(body))):
        assert re.search(r"^\s*export {}=".format(name), script, re.M), name


# ---------------------------------------------------------------------------
# Kafka entrypoint
# ---------------------------------------------------------------------------


@pytest.fixture
def kafka_home(tmp_path, repo_root):
    """A stub /opt/kafka: real templates, a no-op kafka-server-start.sh."""
    home = tmp_path / "opt" / "kafka"
    (home / "config").mkdir(parents=True)
    (home / "bin").mkdir()
    shutil.copytree(str(repo_root / "images/kafka/templates"), str(home / "templates"))
    # Symlink rather than a script file: pytest tmp dirs may live on a noexec
    # filesystem, and the entrypoint execs this path directly.
    (home / "bin" / "kafka-server-start.sh").symlink_to(shutil.which("echo"))
    return home


def start_broker(repo_root, kafka_home, env):
    from helpers import run

    base = {"KAFKA_HOME": str(kafka_home), "PATH": os.environ["PATH"]}
    base.update(env)
    return run(
        ["bash", str(repo_root / "images/kafka/entrypoint.sh")],
        cwd=str(kafka_home),
        env=base,
        timeout=60,
    )


BROKER_ENV = {"BROKER_ID": "2", "BROKER_HOSTNAME": "kafka2", "KAFKA_ZOOKEEPER_CONNECT": "zookeeper1:2181,zookeeper2:2181"}


def rendered(kafka_home):
    return (kafka_home / "config" / "server.properties").read_text()


def test_plaintext_mode_renders_a_complete_server_properties(repo_root, kafka_home):
    env = dict(BROKER_ENV, KAFKA_SECURITY_MODE="plaintext")
    proc = start_broker(repo_root, kafka_home, env)
    assert proc.returncode == 0, proc.stderr
    # The stub start script echoes the config path it was handed.
    assert proc.stdout.strip().splitlines()[-1] == "{}/config/server.properties".format(kafka_home)

    conf = rendered(kafka_home)
    assert "broker.id=2" in conf
    assert "zookeeper.connect=zookeeper1:2181,zookeeper2:2181" in conf
    assert "listeners=PLAINTEXT://0.0.0.0:9092" in conf
    assert "advertised.listeners=PLAINTEXT://kafka2:9092" in conf
    assert "inter.broker.listener.name=PLAINTEXT" in conf
    # Kafka refuses to start if security.inter.broker.protocol is set as well.
    assert not [ln for ln in conf.splitlines() if ln.startswith("security.inter.broker.protocol")]


def test_no_placeholder_survives_rendering(repo_root, kafka_home):
    start_broker(repo_root, kafka_home, dict(BROKER_ENV, KAFKA_SECURITY_MODE="plaintext"))
    assert "${" not in rendered(kafka_home)


def test_plaintext_mode_emits_no_ssl_configuration(repo_root, kafka_home):
    start_broker(repo_root, kafka_home, dict(BROKER_ENV, KAFKA_SECURITY_MODE="plaintext"))
    conf = rendered(kafka_home)
    assert "ssl." not in conf
    assert "9093" not in conf


def test_broker_defaults_match_the_documented_values(repo_root, kafka_home):
    start_broker(repo_root, kafka_home, dict(BROKER_ENV, KAFKA_SECURITY_MODE="plaintext"))
    conf = rendered(kafka_home)
    assert "num.partitions=6" in conf
    assert "default.replication.factor=3" in conf
    assert "min.insync.replicas=2" in conf
    assert "offsets.topic.replication.factor=3" in conf
    assert "auto.create.topics.enable=false" in conf
    assert "log.dirs=/var/lib/kafka/data" in conf


def test_broker_defaults_are_overridable(repo_root, kafka_home):
    env = dict(BROKER_ENV, KAFKA_SECURITY_MODE="plaintext", NUM_PARTITIONS="12",
               MIN_INSYNC_REPLICAS="3", LOG_RETENTION_HOURS="24")
    start_broker(repo_root, kafka_home, env)
    conf = rendered(kafka_home)
    assert "num.partitions=12" in conf
    assert "min.insync.replicas=3" in conf
    assert "log.retention.hours=24" in conf


def test_broker_hostname_defaults_to_the_container_hostname(repo_root, kafka_home):
    import socket

    env = {"BROKER_ID": "1", "KAFKA_ZOOKEEPER_CONNECT": "zookeeper1:2181", "KAFKA_SECURITY_MODE": "plaintext"}
    proc = start_broker(repo_root, kafka_home, env)
    assert proc.returncode == 0, proc.stderr
    assert "advertised.listeners=PLAINTEXT://{}:9092".format(socket.gethostname()) in rendered(kafka_home)


@pytest.mark.parametrize("missing", ["BROKER_ID", "KAFKA_ZOOKEEPER_CONNECT"])
def test_required_identity_variables_fail_fast(repo_root, kafka_home, missing):
    env = dict(BROKER_ENV, KAFKA_SECURITY_MODE="plaintext")
    del env[missing]
    proc = start_broker(repo_root, kafka_home, env)
    assert proc.returncode != 0
    assert missing in proc.stderr
    assert "server.properties" not in proc.stdout


def test_unknown_security_mode_is_rejected(repo_root, kafka_home):
    proc = start_broker(repo_root, kafka_home, dict(BROKER_ENV, KAFKA_SECURITY_MODE="sasl_ssl"))
    assert proc.returncode == 1
    assert "invalid KAFKA_SECURITY_MODE" in proc.stderr


@pytest.mark.parametrize("mode", ["ssl", "dual"])
def test_missing_ssl_material_stops_the_broker_with_a_hint(repo_root, kafka_home, mode):
    """A broker must never start an SSL listener with no keystore mounted."""
    if os.path.exists("/etc/kafka/secrets/kafka.server.keystore.p12"):
        pytest.skip("host has real Kafka SSL material in /etc/kafka/secrets")
    proc = start_broker(repo_root, kafka_home, dict(BROKER_ENV, KAFKA_SECURITY_MODE=mode))
    assert proc.returncode == 1
    assert "SSL material missing" in proc.stderr
    assert "ca-chain.crt" in proc.stderr
    assert "make certs" in proc.stderr
    assert "server.properties" not in proc.stdout


# ---------------------------------------------------------------------------
# ZooKeeper entrypoint
# ---------------------------------------------------------------------------


def start_zookeeper(repo_root, tmp_path, env):
    from helpers import run

    base = {"PATH": os.environ["PATH"], "ZOOKEEPER_HOME": str(tmp_path / "opt" / "zookeeper")}
    base.update(env)
    return run(
        ["bash", str(repo_root / "images/zookeeper/entrypoint.sh")],
        cwd=str(tmp_path),
        env=base,
        timeout=60,
    )


def test_zookeeper_requires_a_node_id(repo_root, tmp_path):
    proc = start_zookeeper(repo_root, tmp_path, {"ZOO_SERVERS": "server.1=zookeeper1:2888:3888;2181"})
    assert proc.returncode != 0
    assert "ZOO_MY_ID" in proc.stderr


def test_zookeeper_requires_an_ensemble_definition(repo_root, tmp_path):
    proc = start_zookeeper(repo_root, tmp_path, {"ZOO_MY_ID": "1"})
    assert proc.returncode == 1
    assert "ZOO_SERVERS is required" in proc.stderr


def test_zookeeper_config_template_declares_the_lab_four_letter_words(repo_root):
    """`ruok` drives the Compose healthcheck; dropping it breaks cluster start-up."""
    cfg = (repo_root / "images/zookeeper/templates/zoo.cfg.tpl").read_text()
    assert "4lw.commands.whitelist=ruok" in cfg
    assert "admin.enableServer=false" in cfg
    assert "dataDir=/var/lib/zookeeper/data" in cfg
