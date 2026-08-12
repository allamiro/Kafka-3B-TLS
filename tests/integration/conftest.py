"""Fixtures for end-to-end cluster tests.

These tests build the real images and start a real 3-broker / 3-ZooKeeper
cluster with Docker Compose, so they are opt-in:

    pytest -m integration

They run from the repository root (the Dockerfiles need it as build context)
and therefore touch the working tree:

  * docker-compose.itest.yml  — rendered per run, git-ignored
  * certs/generated/          — populated for the SSL suite, as `make certs` does

The fixed container names (kafka1, zookeeper1, ...) mean a lab started with
`make up` must be down first.
"""
import pytest

from helpers import run


@pytest.fixture(scope="session", autouse=True)
def docker_daemon():
    proc = run(["docker", "info", "--format", "{{.ServerVersion}}"], cwd=".", timeout=60)
    if proc.returncode != 0:
        pytest.skip("no usable Docker daemon: {}".format(proc.stderr.strip()))
    return proc.stdout.strip()
