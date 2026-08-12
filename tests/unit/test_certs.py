"""scripts/generate-certs.sh, create-stores.sh and validate-certs.sh.

The lab PKI is openssl-only (no Java keytool), so these tests re-verify the
output with openssl itself: chain of trust, SANs, key/cert agreement and
PKCS12 stores that actually open with the configured password.

Marked slow — a full run issues a 4096-bit CA pair plus per-broker leaves.
Two brokers are enough to prove the loop; the count is a parameter, not logic.
"""
import os
import subprocess

import pytest

from helpers import build_sandbox, copy_sandbox, require

pytestmark = pytest.mark.slow

BROKERS = 2
BASE_ENV = {"BROKER_COUNT": str(BROKERS), "KAFKA_SSL_PASSWORD": "test-store-pw",
            "KAFKA_CA_PASSWORD": "test-ca-pw", "CERT_VALIDITY_DAYS": "30"}


def openssl(args, stdin=None):
    return subprocess.run(
        ["openssl"] + args, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True,
    )


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    """A lab PKI generated once for the whole module — read-only for tests."""
    require("openssl")
    sandbox = build_sandbox(tmp_path_factory.mktemp("pki") / "repo")
    sandbox.write_env(BASE_ENV)
    proc = sandbox.run_script("generate-certs.sh")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return sandbox


@pytest.fixture
def mutable_pki(pki, tmp_path):
    """A private copy of the generated PKI for tests that tamper with it."""
    return copy_sandbox(pki, tmp_path / "repo")


def out(sandbox, *parts):
    return sandbox.path.joinpath("certs", "generated", *parts)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_generates_a_two_tier_certificate_authority(pki):
    for name in ("root-ca.crt", "root-ca.key", "intermediate-ca.crt", "intermediate-ca.key", "chain.crt"):
        assert out(pki, "ca", name).is_file(), name


def test_chain_bundle_is_intermediate_then_root(pki):
    chain = out(pki, "ca", "chain.crt").read_text()
    assert chain.count("BEGIN CERTIFICATE") == 2
    assert chain.startswith(out(pki, "ca", "intermediate-ca.crt").read_text())


def test_generates_a_complete_bundle_per_broker(pki):
    for i in range(1, BROKERS + 1):
        for name in ("kafka{}.crt", "kafka{}.key", "kafka{}.chain.crt"):
            assert out(pki, "kafka{}".format(i), name.format(i)).is_file()
        assert out(pki, "kafka{}".format(i), "kafka.server.keystore.p12").is_file()
        assert out(pki, "kafka{}".format(i), "ca-chain.crt").is_file()


def test_generates_client_material(pki):
    assert out(pki, "client", "ca-chain.crt").is_file()
    assert out(pki, "client", "client-ssl.properties").is_file()


def test_publishes_the_client_config_for_host_side_tools(pki):
    body = (pki.path / "config" / "ssl" / "client.properties").read_text()
    assert "security.protocol=SSL" in body
    assert "ssl.truststore.type=PEM" in body
    assert "ssl.endpoint.identification.algorithm=https" in body


# ---------------------------------------------------------------------------
# Cryptographic correctness
# ---------------------------------------------------------------------------


def test_each_certificate_matches_its_private_key(pki):
    for i in range(1, BROKERS + 1):
        cert = openssl(["x509", "-noout", "-modulus", "-in", str(out(pki, "kafka{}".format(i), "kafka{}.crt".format(i)))])
        key = openssl(["rsa", "-noout", "-modulus", "-in", str(out(pki, "kafka{}".format(i), "kafka{}.key".format(i)))])
        assert cert.stdout.strip() == key.stdout.strip() != ""


def test_each_broker_certificate_chains_to_the_root(pki):
    ca = str(out(pki, "ca", "chain.crt"))
    for i in range(1, BROKERS + 1):
        leaf = str(out(pki, "kafka{}".format(i), "kafka{}.crt".format(i)))
        proc = openssl(["verify", "-CAfile", ca, leaf])
        assert proc.returncode == 0, proc.stdout


def test_certificates_carry_every_name_a_client_may_use(pki):
    """kafka1 in-network, the legacy FQDN, localhost and 127.0.0.1 from the host."""
    san = openssl(["x509", "-noout", "-ext", "subjectAltName", "-in",
                   str(out(pki, "kafka1", "kafka1.crt"))]).stdout
    assert "DNS:kafka1" in san
    assert "DNS:KAFKA0001.hq.corp" in san
    assert "DNS:localhost" in san
    assert "127.0.0.1" in san


def test_broker_certificates_are_usable_for_inter_broker_traffic(pki):
    """Inter-broker SSL means a broker is both server and client."""
    text = openssl(["x509", "-noout", "-text", "-in", str(out(pki, "kafka1", "kafka1.crt"))]).stdout
    assert "TLS Web Server Authentication" in text
    assert "TLS Web Client Authentication" in text
    assert "CA:FALSE" in text


def test_leaf_certificates_are_not_certificate_authorities(pki):
    text = openssl(["x509", "-noout", "-text", "-in", str(out(pki, "kafka2", "kafka2.crt"))]).stdout
    assert "CA:TRUE" not in text


def test_certificate_validity_follows_the_configuration(pki):
    proc = openssl(["x509", "-noout", "-checkend", str(29 * 24 * 3600), "-in",
                    str(out(pki, "kafka1", "kafka1.crt"))])
    assert proc.returncode == 0, "cert should still be valid in 29 days"
    proc = openssl(["x509", "-noout", "-checkend", str(31 * 24 * 3600), "-in",
                    str(out(pki, "kafka1", "kafka1.crt"))])
    assert proc.returncode != 0, "cert should be expired in 31 days (CERT_VALIDITY_DAYS=30)"


# ---------------------------------------------------------------------------
# PKCS12 stores
# ---------------------------------------------------------------------------


def test_keystore_opens_with_the_configured_password(pki):
    store = str(out(pki, "kafka1", "kafka.server.keystore.p12"))
    proc = openssl(["pkcs12", "-info", "-in", store, "-nodes", "-passin", "pass:test-store-pw"])
    assert proc.returncode == 0, proc.stdout
    assert "friendlyName: kafka1" in proc.stdout
    assert "PRIVATE KEY" in proc.stdout


def test_keystore_rejects_a_wrong_password(pki):
    store = str(out(pki, "kafka1", "kafka.server.keystore.p12"))
    proc = openssl(["pkcs12", "-info", "-in", store, "-nodes", "-passin", "pass:wrong"])
    assert proc.returncode != 0


def test_trust_material_is_pem_with_the_ca_chain_and_no_private_key(pki):
    """PKCS12 written by `openssl -nokeys` is not a valid Java truststore; the
    brokers consume PEM trust material instead (ssl.truststore.type=PEM)."""
    body = out(pki, "kafka1", "ca-chain.crt").read_text()
    assert body.count("BEGIN CERTIFICATE") == 2
    assert "PRIVATE KEY" not in body
    assert body == out(pki, "ca", "chain.crt").read_text()


def test_trust_material_is_readable_by_the_container_user(pki):
    mode = os.stat(str(out(pki, "kafka1", "ca-chain.crt"))).st_mode & 0o777
    assert mode == 0o644, "{:o}".format(mode)


# ---------------------------------------------------------------------------
# File permissions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relpath", [
    ("ca", "root-ca.key"), ("ca", "intermediate-ca.key"), ("kafka1", "kafka1.key"),
])
def test_private_keys_are_not_world_readable(pki, relpath):
    mode = os.stat(str(out(pki, *relpath))).st_mode & 0o777
    assert mode == 0o600, "{} is {:o}".format("/".join(relpath), mode)


@pytest.mark.parametrize("relpath", [("kafka1", "kafka.server.keystore.p12")])
def test_pkcs12_stores_are_readable_by_the_container_user(pki, relpath):
    """The broker runs as uid 996 and mounts these read-only, so it must be able
    to read them. Their contents are protected by KAFKA_SSL_PASSWORD."""
    mode = os.stat(str(out(pki, *relpath))).st_mode & 0o777
    assert mode == 0o644, "{} is {:o}".format("/".join(relpath), mode)


def test_broker_directories_are_traversable_by_the_container_user(pki):
    for i in range(1, BROKERS + 1):
        mode = os.stat(str(out(pki, "kafka{}".format(i)))).st_mode & 0o777
        assert mode & 0o055 == 0o055, "kafka{} is {:o}".format(i, mode)


def test_certificate_authority_keys_are_encrypted_at_rest(pki):
    body = out(pki, "ca", "root-ca.key").read_text()
    assert "ENCRYPTED PRIVATE KEY" in body or "Proc-Type: 4,ENCRYPTED" in body


# ---------------------------------------------------------------------------
# Re-runs and mutual TLS
# ---------------------------------------------------------------------------


def test_rerunning_reuses_the_existing_certificate_authority(mutable_pki):
    """Re-issuing broker certs must not orphan the trust already distributed."""
    before = out(mutable_pki, "ca", "root-ca.crt").read_bytes()
    proc = mutable_pki.run_script("generate-certs.sh")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "already exists" in proc.stderr
    assert out(mutable_pki, "ca", "root-ca.crt").read_bytes() == before


def test_scaling_up_issues_certificates_for_the_new_brokers(mutable_pki):
    env = dict(BASE_ENV, BROKER_COUNT="3")
    mutable_pki.write_env(env)
    proc = mutable_pki.run_script("generate-certs.sh")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out(mutable_pki, "kafka3", "kafka.server.keystore.p12").is_file()
    ca = str(out(mutable_pki, "ca", "chain.crt"))
    assert openssl(["verify", "-CAfile", ca, str(out(mutable_pki, "kafka3", "kafka3.crt"))]).returncode == 0


def test_mutual_tls_adds_a_client_keystore(sandbox):
    require("openssl")
    sandbox.write_env(dict(BASE_ENV, SSL_CLIENT_AUTH="required"))
    proc = sandbox.run_script("generate-certs.sh")
    assert proc.returncode == 0, proc.stdout + proc.stderr

    keystore = out(sandbox, "client", "kafka.client.keystore.p12")
    assert keystore.is_file()
    info = openssl(["pkcs12", "-info", "-in", str(keystore), "-nodes", "-passin", "pass:test-store-pw"])
    assert "friendlyName: kafka-client" in info.stdout

    text = openssl(["x509", "-noout", "-text", "-in", str(out(sandbox, "client", "kafka-client.crt"))]).stdout
    assert "TLS Web Client Authentication" in text

    props = out(sandbox, "client", "client-ssl.properties").read_text()
    assert "ssl.keystore.location=" in props
    assert "ssl.key.password=test-store-pw" in props


def test_client_keystore_is_absent_without_mutual_tls(pki):
    assert not out(pki, "client", "kafka.client.keystore.p12").exists()


def test_scaled_brokers_also_get_trust_material(mutable_pki):
    mutable_pki.write_env(dict(BASE_ENV, BROKER_COUNT="3"))
    assert mutable_pki.run_script("generate-certs.sh").returncode == 0
    assert out(mutable_pki, "kafka3", "ca-chain.crt").is_file()


# ---------------------------------------------------------------------------
# make certs dispatch and validation
# ---------------------------------------------------------------------------


def test_prepare_certs_dispatches_to_generation(sandbox):
    require("openssl")
    sandbox.write_env(dict(BASE_ENV, KAFKA_CERT_MODE="generate"))
    proc = sandbox.run_script("prepare-certs.sh")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "generating local CA" in proc.stdout
    assert out(sandbox, "kafka1", "kafka.server.keystore.p12").is_file()


def test_validation_passes_on_freshly_generated_material(pki):
    proc = pki.run_script("validate-certs.sh")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "All 2 broker certificates validated" in proc.stdout


def test_validation_detects_a_key_that_belongs_to_another_broker(mutable_pki):
    """The classic copy/paste mistake when wiring an enterprise PKI by hand."""
    out(mutable_pki, "kafka1", "kafka1.key").write_bytes(out(mutable_pki, "kafka2", "kafka2.key").read_bytes())
    proc = mutable_pki.run_script("validate-certs.sh")
    assert proc.returncode == 1
    assert "certificate and private key do NOT match" in proc.stderr


def test_validation_detects_missing_material(mutable_pki):
    out(mutable_pki, "kafka2", "kafka2.crt").unlink()
    proc = mutable_pki.run_script("validate-certs.sh")
    assert proc.returncode == 1
    assert "missing certificate" in proc.stderr


def test_validation_detects_a_certificate_from_a_foreign_authority(mutable_pki, tmp_path):
    """A broker cert signed by some other CA must not pass the chain check."""
    rogue_key = tmp_path / "rogue.key"
    rogue_crt = tmp_path / "rogue.crt"
    proc = openssl(["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=kafka1", "-addext", "subjectAltName=DNS:kafka1",
                    "-keyout", str(rogue_key), "-out", str(rogue_crt)])
    assert proc.returncode == 0, proc.stdout
    out(mutable_pki, "kafka1", "kafka1.crt").write_bytes(rogue_crt.read_bytes())
    out(mutable_pki, "kafka1", "kafka1.key").write_bytes(rogue_key.read_bytes())

    proc = mutable_pki.run_script("validate-certs.sh")
    assert proc.returncode == 1
    assert "does NOT validate against CA bundle" in proc.stderr
