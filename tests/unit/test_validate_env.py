"""scripts/validate-env.sh and scripts/validate-security-mode.sh.

These two scripts are the guard rail in front of `make certs`, `make render`
and `make up`: a bad .env must fail loudly here rather than half-way through a
cluster start.
"""
import pytest

VALID = {
    "BROKER_COUNT": "3",
    "ZOOKEEPER_COUNT": "3",
    "KAFKA_SECURITY_MODE": "dual",
    "KAFKA_CERT_MODE": "generate",
    "SSL_CLIENT_AUTH": "none",
    "DEFAULT_REPLICATION_FACTOR": "3",
}


def validate(sandbox, **overrides):
    values = dict(VALID)
    values.update(overrides)
    sandbox.write_env(values)
    return sandbox.run_script("validate-env.sh")


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------


def test_the_shipped_defaults_validate(sandbox):
    proc = validate(sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "Environment is valid" in proc.stdout


@pytest.mark.parametrize("count", ["0", "1", "2"])
def test_rejects_fewer_than_three_brokers(sandbox, count):
    proc = validate(sandbox, BROKER_COUNT=count)
    assert proc.returncode == 1
    assert "BROKER_COUNT must be an integer >= 3" in proc.stderr


@pytest.mark.parametrize("count", ["three", "3.5", "-3"])
def test_rejects_non_integer_broker_counts(sandbox, count):
    proc = validate(sandbox, BROKER_COUNT=count)
    assert proc.returncode == 1
    assert "BROKER_COUNT" in proc.stderr


@pytest.mark.parametrize("count", ["1", "2", "4", "6", "7"])
def test_rejects_quorum_sizes_other_than_three_or_five(sandbox, count):
    proc = validate(sandbox, ZOOKEEPER_COUNT=count)
    assert proc.returncode == 1
    assert "ZOOKEEPER_COUNT must be 3 or 5" in proc.stderr


@pytest.mark.parametrize("count", ["3", "5"])
def test_accepts_supported_quorum_sizes(sandbox, count):
    assert validate(sandbox, ZOOKEEPER_COUNT=count).returncode == 0


def test_replication_factor_may_not_exceed_the_broker_count(sandbox):
    proc = validate(sandbox, BROKER_COUNT="3", DEFAULT_REPLICATION_FACTOR="5")
    assert proc.returncode == 1
    assert "cannot exceed BROKER_COUNT" in proc.stderr


def test_replication_factor_equal_to_the_broker_count_is_allowed(sandbox):
    assert validate(sandbox, BROKER_COUNT="3", DEFAULT_REPLICATION_FACTOR="3").returncode == 0


def test_larger_clusters_keep_a_three_node_quorum(sandbox):
    proc = validate(sandbox, BROKER_COUNT="7", ZOOKEEPER_COUNT="3")
    assert proc.returncode == 0
    assert "7 brokers, 3 zookeepers" in proc.stdout


# ---------------------------------------------------------------------------
# Security mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["plaintext", "ssl", "dual"])
def test_accepts_every_supported_security_mode(sandbox, mode):
    inter = "PLAINTEXT" if mode == "plaintext" else "SSL"
    proc = validate(sandbox, KAFKA_SECURITY_MODE=mode, INTER_BROKER_LISTENER_NAME=inter)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("mode", ["sasl", "SSL_PLAINTEXT", "tls"])
def test_rejects_unknown_security_modes(sandbox, mode):
    proc = validate(sandbox, KAFKA_SECURITY_MODE=mode)
    assert proc.returncode == 1
    assert "KAFKA_SECURITY_MODE must be plaintext|ssl|dual" in proc.stderr


@pytest.mark.parametrize("mode", ["auto", "keytool"])
def test_rejects_unknown_certificate_modes(sandbox, mode):
    proc = validate(sandbox, KAFKA_CERT_MODE=mode)
    assert proc.returncode == 1
    assert "KAFKA_CERT_MODE must be generate|import" in proc.stderr


@pytest.mark.parametrize("value", ["yes", "true", "mutual"])
def test_rejects_unknown_client_auth_values(sandbox, value):
    proc = validate(sandbox, SSL_CLIENT_AUTH=value)
    assert proc.returncode == 1
    assert "SSL_CLIENT_AUTH must be none|requested|required" in proc.stderr


@pytest.mark.parametrize("value", ["none", "requested", "required"])
def test_accepts_documented_client_auth_values(sandbox, value):
    assert validate(sandbox, SSL_CLIENT_AUTH=value).returncode == 0


def test_empty_values_fall_back_to_the_builtin_defaults(sandbox):
    """`KEY=` in .env means "unset" — _env.sh substitutes the documented default."""
    proc = validate(sandbox, BROKER_COUNT="", KAFKA_SECURITY_MODE="", KAFKA_CERT_MODE="")
    assert proc.returncode == 0
    assert "3 brokers, 3 zookeepers, mode=dual" in proc.stdout


def test_conflicting_inter_broker_listener_only_warns(sandbox):
    """The entrypoint overrides it; a warning is enough to keep `make up` working."""
    proc = validate(sandbox, KAFKA_SECURITY_MODE="plaintext", INTER_BROKER_LISTENER_NAME="SSL")
    assert proc.returncode == 0
    assert "forces inter-broker to PLAINTEXT" in proc.stderr


# ---------------------------------------------------------------------------
# Imported PKI
# ---------------------------------------------------------------------------


def test_import_mode_requires_the_external_root_ca(sandbox):
    proc = validate(sandbox, KAFKA_SECURITY_MODE="ssl", KAFKA_CERT_MODE="import")
    assert proc.returncode == 1
    assert "EXTERNAL_ROOT_CA_CERT missing/not found" in proc.stderr


def test_import_mode_rejects_paths_that_do_not_exist(sandbox):
    proc = validate(
        sandbox,
        KAFKA_SECURITY_MODE="ssl",
        KAFKA_CERT_MODE="import",
        EXTERNAL_ROOT_CA_CERT="/nonexistent/root-ca.crt",
        EXTERNAL_BROKER_CERTS_DIR="/nonexistent/brokers",
    )
    assert proc.returncode == 1
    assert "EXTERNAL_ROOT_CA_CERT missing/not found" in proc.stderr
    assert "EXTERNAL_BROKER_CERTS_DIR missing/not found" in proc.stderr


def test_import_mode_passes_when_the_external_material_exists(sandbox):
    # Only existence is checked at this stage; the content is irrelevant.
    ca = sandbox.path / "root-ca.crt"
    ca.write_text("placeholder\n")
    brokers = sandbox.path / "broker-pki"
    brokers.mkdir()
    proc = validate(
        sandbox,
        KAFKA_SECURITY_MODE="ssl",
        KAFKA_CERT_MODE="import",
        EXTERNAL_ROOT_CA_CERT=str(ca),
        EXTERNAL_BROKER_CERTS_DIR=str(brokers),
    )
    assert proc.returncode == 0, proc.stderr


def test_plaintext_mode_needs_no_external_pki(sandbox):
    proc = validate(sandbox, KAFKA_SECURITY_MODE="plaintext", KAFKA_CERT_MODE="import")
    assert proc.returncode == 0, proc.stderr


def test_plaintext_mode_skips_certificate_generation(sandbox):
    proc = sandbox.run_script("prepare-certs.sh", env={"KAFKA_SECURITY_MODE": "plaintext"})
    assert proc.returncode == 0
    assert "certificates are not required" in proc.stdout
    assert not list((sandbox.path / "certs" / "generated").glob("kafka*"))
