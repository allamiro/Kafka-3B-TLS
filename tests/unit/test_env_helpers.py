"""scripts/_env.sh — .env loading, precedence and shared helpers.

Every operational script sources this file, so its precedence rules
(real environment > .env > built-in default) decide the behaviour of the
whole tool-chain.
"""
SOURCE = 'source "$PWD/scripts/_env.sh"; load_env; '


def probe(sandbox, variable, env=None):
    proc = sandbox.bash(SOURCE + 'printf "%s" "${' + variable + '}"', env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_builtin_defaults_apply_without_a_dotenv(sandbox):
    assert probe(sandbox, "KAFKA_SECURITY_MODE") == "dual"
    assert probe(sandbox, "KAFKA_CERT_MODE") == "generate"
    assert probe(sandbox, "BROKER_COUNT") == "3"
    assert probe(sandbox, "ZOOKEEPER_COUNT") == "3"
    assert probe(sandbox, "INTER_BROKER_LISTENER_NAME") == "SSL"
    assert probe(sandbox, "CERT_OUTPUT_DIR") == "certs/generated"
    assert probe(sandbox, "KAFKA_STORE_TYPE") == "PKCS12"


def test_dotenv_values_override_builtin_defaults(sandbox):
    sandbox.write_env({"BROKER_COUNT": "7", "KAFKA_SECURITY_MODE": "ssl"})
    assert probe(sandbox, "BROKER_COUNT") == "7"
    assert probe(sandbox, "KAFKA_SECURITY_MODE") == "ssl"


def test_real_environment_overrides_dotenv(sandbox):
    sandbox.write_env({"BROKER_COUNT": "7"})
    assert probe(sandbox, "BROKER_COUNT", env={"BROKER_COUNT": "5"}) == "5"


def test_comments_and_blank_lines_are_ignored(sandbox):
    (sandbox.path / ".env").write_text(
        "# a comment\n\n   \nBROKER_COUNT=5\n# BROKER_COUNT=99\n"
    )
    assert probe(sandbox, "BROKER_COUNT") == "5"


def test_values_containing_equals_signs_survive_intact(sandbox):
    sandbox.write_env({"KAFKA_HEAP_OPTS": "-Xms512m -Xmx1g", "SSL_ENABLED_PROTOCOLS": "TLSv1.2,TLSv1.3"})
    assert probe(sandbox, "KAFKA_HEAP_OPTS") == "-Xms512m -Xmx1g"
    assert probe(sandbox, "SSL_ENABLED_PROTOCOLS") == "TLSv1.2,TLSv1.3"


def test_the_shipped_example_is_a_usable_dotenv(sandbox):
    """.env.example must load cleanly — `make env` just copies it."""
    (sandbox.path / ".env").write_text(sandbox.read(".env.example"))
    assert probe(sandbox, "KAFKA_SECURITY_MODE") == "dual"
    assert probe(sandbox, "BROKER_COUNT") == "3"
    assert probe(sandbox, "ZOOKEEPER_COUNT") == "3"
    assert probe(sandbox, "KAFKA_VERSION") == "3.9.2"
    assert probe(sandbox, "ZOOKEEPER_VERSION") == "3.9.5"


def test_repo_root_resolves_to_the_parent_of_scripts(sandbox):
    proc = sandbox.bash(SOURCE + 'printf "%s" "${REPO_ROOT}"')
    assert proc.stdout == str(sandbox.path.resolve())


def test_broker_fqdn_uses_the_legacy_four_digit_form(sandbox):
    proc = sandbox.bash(SOURCE + 'broker_fqdn 1; echo; broker_fqdn 12; echo; broker_fqdn 123')
    assert proc.stdout.split() == ["KAFKA0001.hq.corp", "KAFKA0012.hq.corp", "KAFKA0123.hq.corp"]


def test_broker_fqdn_follows_the_configured_domain(sandbox):
    sandbox.write_env({"KAFKA_DOMAIN": "lab.example.net"})
    proc = sandbox.bash(SOURCE + 'broker_fqdn 2')
    assert proc.stdout.strip() == "KAFKA0002.lab.example.net"


def test_log_helpers_write_diagnostics_to_stderr(sandbox):
    """warn/err must not pollute stdout — callers pipe stdout into other tools."""
    proc = sandbox.bash(SOURCE + 'log ok-line; ok ok-line; warn bad-line; err bad-line')
    assert "bad-line" not in proc.stdout
    assert proc.stderr.count("bad-line") == 2
