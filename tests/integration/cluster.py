"""Docker Compose plumbing for the end-to-end cluster tests."""
import json
import time

from helpers import run

PROJECT = "kafka-lab-itest"
COMPOSE_FILE = "docker-compose.itest.yml"

BROKERS = 3
ZOOKEEPERS = 3

BUILD_TIMEOUT = 1800
READY_TIMEOUT = 300


class Cluster:
    """A running Compose project, scoped to one security mode."""

    def __init__(self, repo_root, mode):
        self.repo_root = repo_root
        self.mode = mode

    # -- compose plumbing ---------------------------------------------------
    def compose(self, args, timeout=300, check=False):
        proc = run(
            ["docker", "compose", "-p", PROJECT, "-f", COMPOSE_FILE] + list(args),
            cwd=self.repo_root,
            timeout=timeout,
        )
        if check:
            assert proc.returncode == 0, "docker compose {}\n{}\n{}".format(
                " ".join(args), proc.stdout, proc.stderr
            )
        return proc

    def exec(self, service, args, timeout=180, check=True, stdin=None):
        proc = run(
            ["docker", "compose", "-p", PROJECT, "-f", COMPOSE_FILE, "exec", "-T", service] + list(args),
            cwd=self.repo_root,
            timeout=timeout,
            stdin=stdin,
        )
        if check:
            assert proc.returncode == 0, "{} in {}\n{}\n{}".format(args, service, proc.stdout, proc.stderr)
        return proc

    def logs(self, service, tail=80):
        return self.compose(["logs", "--tail", str(tail), service]).stdout

    # -- kafka helpers ------------------------------------------------------
    @property
    def bootstrap(self):
        return "kafka1:9093" if self.mode == "ssl" else "kafka1:9092"

    @property
    def client_config(self):
        """Extra CLI flags needed to talk to the listener under test."""
        if self.mode == "ssl":
            return ["--command-config", "/opt/kafka/config/client-ssl.properties"]
        return []

    def kafka_topics(self, args, **kwargs):
        return self.exec(
            "kafka1",
            ["kafka-topics.sh", "--bootstrap-server", self.bootstrap] + self.client_config + list(args),
            **kwargs
        )

    def health(self, service):
        proc = self.compose(["ps", "--format", "json", service])
        if proc.returncode != 0 or not proc.stdout.strip():
            return "unknown"
        # Compose v2 emits either a JSON array or one object per line.
        payload = proc.stdout.strip()
        try:
            entries = json.loads(payload)
            if isinstance(entries, dict):
                entries = [entries]
        except ValueError:
            entries = [json.loads(line) for line in payload.splitlines() if line.strip()]
        return entries[0].get("Health") or entries[0].get("State", "unknown") if entries else "unknown"

    def wait_until_healthy(self, timeout=READY_TIMEOUT):
        services = ["zookeeper{}".format(i) for i in range(1, ZOOKEEPERS + 1)]
        services += ["kafka{}".format(i) for i in range(1, BROKERS + 1)]
        deadline = time.time() + timeout
        pending = list(services)
        while pending and time.time() < deadline:
            pending = [s for s in pending if self.health(s) != "healthy"]
            if pending:
                time.sleep(5)
        if pending:
            details = "\n\n".join("--- {} ---\n{}".format(s, self.logs(s)) for s in pending)
            raise AssertionError("not healthy within {}s: {}\n{}".format(timeout, pending, details))


def start_cluster(repo_root, mode):
    """Render, build and start a cluster; returns a live Cluster."""
    inter_broker = "PLAINTEXT" if mode == "plaintext" else "SSL"
    rendered = run(
        ["python3", "scripts/render-compose.py",
         "--brokers", str(BROKERS), "--zookeepers", str(ZOOKEEPERS),
         "--security-mode", mode, "--inter-broker", inter_broker, "-o", COMPOSE_FILE],
        cwd=repo_root,
    )
    assert rendered.returncode == 0, rendered.stderr

    if mode != "plaintext":
        certs = run(["bash", "scripts/generate-certs.sh"], cwd=repo_root,
                    env={"BROKER_COUNT": str(BROKERS)}, timeout=600)
        assert certs.returncode == 0, certs.stdout + certs.stderr

    cluster = Cluster(repo_root, mode)
    cluster.compose(["down", "-v", "--remove-orphans"], timeout=300)
    cluster.compose(["up", "-d", "--build"], timeout=BUILD_TIMEOUT, check=True)
    cluster.wait_until_healthy()
    return cluster


def stop_cluster(cluster):
    cluster.compose(["down", "-v", "--remove-orphans"], timeout=300)
    (cluster.repo_root / COMPOSE_FILE).unlink(missing_ok=True)
