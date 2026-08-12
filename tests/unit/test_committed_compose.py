"""The three pre-rendered Compose files that ship in the repository.

They exist so that `docker compose up` works before anyone runs `make render`.
That makes them a copy of generated output, and copies drift — these tests fail
the moment scripts/render-compose.py and the committed files disagree.
"""
import pytest
import yaml

from helpers import COMMITTED_COMPOSE, run, require


@pytest.fixture(params=sorted(COMMITTED_COMPOSE))
def committed(request, repo_root):
    name = request.param
    mode, inter_broker = COMMITTED_COMPOSE[name]
    return name, mode, inter_broker, (repo_root / name)


def test_committed_file_is_valid_yaml(committed):
    _, _, _, path = committed
    doc = yaml.safe_load(path.read_text())
    assert doc["name"] == "kafka-zookeeper-lab"
    assert set(doc["services"]) == {
        "kafka1", "kafka2", "kafka3", "zookeeper1", "zookeeper2", "zookeeper3",
    }


def test_committed_file_matches_the_renderer(committed, sandbox):
    """`make render` for the same mode must reproduce the committed topology."""
    name, mode, inter_broker, path = committed
    generated = sandbox.render_yaml(
        ["--brokers", "3", "--zookeepers", "3", "--security-mode", mode,
         "--inter-broker", inter_broker]
    )
    assert yaml.safe_load(path.read_text()) == generated, (
        "{} has drifted from scripts/render-compose.py — re-render it".format(name)
    )


def test_committed_file_warns_against_hand_editing(committed):
    _, _, _, path = committed
    assert "DO NOT EDIT BY HAND" in path.read_text()


def test_generated_variant_is_not_committed(repo_root):
    """docker-compose.generated.yml is per-developer output and stays untracked."""
    proc = run(["git", "ls-files", "docker-compose.generated.yml"], cwd=repo_root)
    assert proc.stdout.strip() == ""


def test_docker_compose_accepts_every_committed_file(committed, repo_root):
    """The real Compose schema check — catches what YAML parsing cannot."""
    require("docker")
    name, _, _, _ = committed
    proc = run(["docker", "compose", "-f", name, "config", "-q"], cwd=repo_root)
    assert proc.returncode == 0, proc.stderr
