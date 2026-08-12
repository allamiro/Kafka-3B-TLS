"""Repository-level invariants: shell correctness, secret hygiene, doc drift.

Cheap checks that would otherwise only fail at `docker build` time, in a
reviewer's terminal, or — for the secret checks — never.
"""
import re

import pytest

from helpers import run

PEM_MARKER = re.compile(r"-----BEGIN (RSA |EC |DSA )?(PRIVATE KEY|CERTIFICATE)")

BINARY_SUFFIXES = {".p12", ".jks", ".png", ".jpg", ".gz", ".tgz", ".zip", ".jar"}


def tracked_files(repo_root):
    proc = run(["git", "ls-files"], cwd=repo_root)
    if proc.returncode != 0:
        pytest.skip("not a git checkout")
    return [line for line in proc.stdout.splitlines() if line]


# The Docker lab owns scripts/ and images/. kafka/, zookeeper/ and
# Set-ServerBaselineConfig.sh are the superseded bare-metal installers kept for
# reference (see docs/migration-from-systemd.md) — they are not held to the
# lab's conventions, only to "must parse".
LAB_DIRS = ("scripts", "images")


@pytest.fixture(scope="session")
def shell_scripts(repo_root):
    """Every shell script in the repository, excluding vendored trees."""
    return sorted(
        str(p.relative_to(repo_root))
        for p in repo_root.glob("**/*.sh")
        if not {".git", "packages", "vendor"}.intersection(p.parts)
    )


@pytest.fixture(scope="session")
def lab_shell_scripts(shell_scripts):
    """Shell scripts that are part of the Compose lab itself."""
    return [p for p in shell_scripts if p.split("/")[0] in LAB_DIRS]


# ---------------------------------------------------------------------------
# Shell scripts
# ---------------------------------------------------------------------------


def test_there_are_shell_scripts_to_check(shell_scripts, lab_shell_scripts):
    assert len(shell_scripts) > 10
    assert len(lab_shell_scripts) > 10


def test_every_shell_script_parses(repo_root, shell_scripts):
    """`bash -n` on every script — a syntax error here is a crash-looping container."""
    broken = []
    for path in shell_scripts:
        proc = run(["bash", "-n", path], cwd=repo_root)
        if proc.returncode != 0:
            broken.append("{}: {}".format(path, proc.stderr.strip()))
    assert not broken, "\n".join(broken)


def test_every_lab_script_declares_a_bash_shebang(repo_root, lab_shell_scripts):
    for path in lab_shell_scripts:
        first = (repo_root / path).read_text().splitlines()[0]
        assert first == "#!/usr/bin/env bash", "{} starts with {!r}".format(path, first)


def test_helper_scripts_are_executable(repo_root):
    """`./scripts/foo.sh` is documented in the README, so the bit must be set."""
    not_executable = [
        p.name for p in sorted((repo_root / "scripts").iterdir())
        if p.is_file() and not p.stat().st_mode & 0o111
    ]
    assert not_executable == []


def test_entrypoints_are_executable(repo_root):
    for image in ("kafka", "zookeeper"):
        entrypoint = repo_root / "images" / image / "entrypoint.sh"
        assert entrypoint.stat().st_mode & 0o111, entrypoint


def test_operational_scripts_use_strict_mode(repo_root, lab_shell_scripts):
    """set -euo pipefail everywhere except the files meant to be sourced."""
    sourced_only = {"scripts/_env.sh", "scripts/_compose.sh", "scripts/create-stores.sh"}
    for path in lab_shell_scripts:
        if path in sourced_only:
            continue
        assert "set -euo pipefail" in (repo_root / path).read_text(), path


# ---------------------------------------------------------------------------
# Secret hygiene
# ---------------------------------------------------------------------------


def test_no_key_or_certificate_material_is_tracked(repo_root):
    tracked = tracked_files(repo_root)
    forbidden = (".key", ".crt", ".csr", ".pem", ".p12", ".jks", ".keystore", ".truststore", ".srl")
    offenders = [f for f in tracked if f.endswith(forbidden)]
    assert offenders == []


def test_no_tracked_file_contains_a_pem_block(repo_root):
    offenders = []
    for name in tracked_files(repo_root):
        path = repo_root / name
        if path.suffix in BINARY_SUFFIXES or not path.is_file():
            continue
        try:
            body = path.read_text()
        except UnicodeDecodeError:
            continue
        if PEM_MARKER.search(body):
            offenders.append(name)
    assert offenders == []


def test_the_real_dotenv_is_never_tracked(repo_root):
    assert ".env" not in tracked_files(repo_root)
    assert ".env.example" in tracked_files(repo_root)


@pytest.mark.parametrize(
    "pattern",
    [".env", "certs/generated/*", "*.key", "*.p12", "*.jks", "*.pem", "packages/",
     "docker-compose.generated.yml", "vendor/*.tgz"],
)
def test_gitignore_covers_generated_and_secret_material(repo_root, pattern):
    assert pattern in (repo_root / ".gitignore").read_text().splitlines()


def test_generated_certificate_directory_ships_empty(repo_root):
    tracked = [f for f in tracked_files(repo_root) if f.startswith("certs/generated/")]
    assert tracked == ["certs/generated/.gitkeep"]


def test_example_env_ships_only_placeholder_passwords(repo_root):
    """`changeit` is the documented throwaway default; anything else is a leak."""
    body = (repo_root / ".env.example").read_text()
    for line in body.splitlines():
        if line.startswith(("KAFKA_SSL_PASSWORD=", "KAFKA_CA_PASSWORD=")):
            assert line.endswith("=changeit"), line


# ---------------------------------------------------------------------------
# Documentation drift
# ---------------------------------------------------------------------------


def make_targets(repo_root):
    body = (repo_root / "Makefile").read_text()
    return set(re.findall(r"^([a-zA-Z0-9_-]+):.*?##", body, re.M))


def test_every_make_target_is_self_documented(repo_root):
    body = (repo_root / "Makefile").read_text()
    declared = set()
    for line in body.splitlines():
        if line.startswith(".PHONY:") or line.startswith("        ") and declared:
            declared.update(line.replace(".PHONY:", "").replace("\\", "").split())
    assert declared, "no .PHONY block found"
    assert declared - make_targets(repo_root) == set(), "undocumented .PHONY targets"


def test_makefile_only_calls_scripts_that_exist(repo_root):
    body = (repo_root / "Makefile").read_text()
    for ref in sorted(set(re.findall(r"scripts/[A-Za-z0-9_.-]+", body))):
        assert (repo_root / ref).is_file(), "Makefile references missing {}".format(ref)


def test_readme_only_documents_real_make_targets(repo_root):
    targets = make_targets(repo_root)
    body = (repo_root / "README.md").read_text()
    for used in sorted(set(re.findall(r"^\s*make ([a-z][a-z0-9-]*)", body, re.M))):
        assert used in targets, "README documents `make {}`, which does not exist".format(used)


def test_readme_and_env_example_agree_on_versions(repo_root):
    env_example = (repo_root / ".env.example").read_text()
    readme = (repo_root / "README.md").read_text()
    assert "KAFKA_VERSION=3.9.2" in env_example
    assert "ZOOKEEPER_VERSION=3.9.5" in env_example
    assert "3.9.2" in readme and "3.9.5" in readme


def test_documentation_links_in_the_readme_resolve(repo_root):
    readme = (repo_root / "README.md").read_text()
    for target in re.findall(r"\]\((?!https?:)([^)#]+)", readme):
        assert (repo_root / target).exists(), "README links to missing {}".format(target)
