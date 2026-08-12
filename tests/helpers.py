"""Shared helpers for the Kafka + ZooKeeper Compose lab test suite.

Unit tests never run against the developer's working tree: the `sandbox`
fixture copies the small, script-relevant subtrees into a temporary directory
and runs the shell scripts there. The scripts derive their own repository root
from `dirname $0/..`, so a copied `scripts/` directory transparently becomes a
self-contained repository root.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Subtrees a script under scripts/ may legitimately read or write.
SANDBOX_TREES = ("scripts", "certs/openssl", "config", "images")
SANDBOX_FILES = (".env.example", "Makefile")

# Committed, pre-rendered Compose files and the renderer flags that reproduce them.
COMMITTED_COMPOSE = {
    "docker-compose.yml": ("dual", "SSL"),
    "docker-compose.ssl.yml": ("ssl", "SSL"),
    "docker-compose.plaintext.yml": ("plaintext", "PLAINTEXT"),
}


def run(args, cwd, env=None, timeout=300, stdin=None):
    """Run a command, capturing output. Never raises on a non-zero exit."""
    full_env = dict(os.environ)
    # Keep child processes from inheriting host settings the scripts read.
    for key in list(full_env):
        if key.startswith(("KAFKA_", "ZOO", "BROKER_", "SSL_", "CERT_", "EXTERNAL_")):
            del full_env[key]
    if env:
        full_env.update({k: str(v) for k, v in env.items()})
    return subprocess.run(
        args,
        cwd=str(cwd),
        env=full_env,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )


class Sandbox:
    """An isolated copy of the repository that shell scripts can safely mutate."""

    def __init__(self, path):
        self.path = path

    # -- helpers ------------------------------------------------------------
    def script(self, name):
        return str(self.path / "scripts" / name)

    def run_script(self, name, args=(), env=None, timeout=300):
        return run(["bash", self.script(name)] + list(args), self.path, env, timeout)

    def bash(self, snippet, env=None, timeout=60):
        """Run a bash snippet inside the sandbox (used to probe sourced helpers)."""
        return run(["bash", "-c", snippet], self.path, env, timeout)

    def render(self, args=(), env=None):
        return run(
            ["python3", self.script("render-compose.py")] + list(args),
            self.path,
            env,
        )

    def render_yaml(self, args=(), env=None):
        """Render to stdout and parse the result, asserting a clean exit."""
        proc = self.render(args, env)
        assert proc.returncode == 0, proc.stderr
        return yaml.safe_load(proc.stdout)

    def write_env(self, values):
        """Write a .env file from a dict (values are written verbatim)."""
        body = "".join("{}={}\n".format(k, v) for k, v in values.items())
        (self.path / ".env").write_text(body)

    def read(self, relpath):
        return (self.path / relpath).read_text()


def build_sandbox(root):
    """Populate `root` with the parts of the repository the scripts need."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for tree in SANDBOX_TREES:
        src = REPO_ROOT / tree
        if src.is_dir():
            dst = root / tree
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(src), str(dst))
    for name in SANDBOX_FILES:
        src = REPO_ROOT / name
        if src.is_file():
            shutil.copy2(str(src), str(root / name))
    (root / "certs" / "generated").mkdir(parents=True, exist_ok=True)
    (root / "vendor").mkdir(exist_ok=True)
    return Sandbox(root)


def copy_sandbox(source, destination):
    """Clone an existing sandbox — cheaper than regenerating expensive artefacts."""
    shutil.copytree(str(source.path), str(destination))
    return Sandbox(Path(destination))


def require(binary):
    """Skip the calling test when a host binary is unavailable."""
    if shutil.which(binary) is None:
        pytest.skip("{} is not installed on this host".format(binary))
