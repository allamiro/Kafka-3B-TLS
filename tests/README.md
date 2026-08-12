# Test Suite

Tests for the Kafka 3.9.2 + ZooKeeper 3.9.5 Compose lab. One runner (pytest)
covers both the Python renderer and the shell tooling — the shell scripts are
driven as CLI black boxes, which is the level at which they are used.

## Layout

```text
tests/
├── helpers.py                     # sandbox construction, subprocess wrapper
├── conftest.py                    # repo_root / sandbox fixtures
├── requirements.txt
├── unit/                          # no Docker, no network, seconds
│   ├── test_render_compose.py     # topology generation and its validation rules
│   ├── test_env_helpers.py        # .env loading and precedence
│   ├── test_validate_env.py       # sizing / security-mode guard rails
│   ├── test_entrypoints.py        # container config rendering and fail-fast
│   ├── test_committed_compose.py  # pre-rendered files vs the renderer
│   ├── test_certs.py              # lab PKI, verified with openssl  [slow]
│   └── test_repo_hygiene.py       # shell syntax, secret hygiene, doc drift
└── integration/                   # builds images, starts a real cluster
    ├── cluster.py                 # Compose plumbing
    ├── test_plaintext_cluster.py
    └── test_ssl_cluster.py
```

## Running

```bash
python3 -m pip install -r tests/requirements.txt

make test               # unit tests (default: integration deselected)
make test-fast          # unit tests without the certificate suite
make test-integration   # end-to-end, needs Docker (~10 min on a cold cache)
make test-all           # everything
```

Or with pytest directly:

```bash
pytest                          # unit only — this is the default marker filter
pytest -m "not slow"            # skip certificate generation
pytest -m integration           # end-to-end only
pytest tests/unit/test_certs.py -v
```

## Markers

| Marker | Meaning |
|--------|---------|
| *(none)* | Unit test: no Docker, no network, isolated from the working tree |
| `slow` | Generates a real PKI with openssl (~15 s for the module) |
| `integration` | Builds images and starts a cluster; deselected by default |
| `ssl` | Exercises the TLS listeners |

## How unit tests stay isolated

`sandbox` copies `scripts/`, `certs/openssl/`, `config/`, `images/` and
`.env.example` into a temporary directory. The shell scripts derive their
repository root from `dirname $0/..`, so the copy becomes a self-contained
repository and `generate-certs.sh` writes its keys there — never into your
working tree.

## What integration tests touch

They must run from the repository root, because the Dockerfiles use it as their
build context. They therefore write:

* `docker-compose.itest.yml` — rendered per run, git-ignored, removed on teardown
* `certs/generated/` — populated for the SSL suite, exactly as `make certs` does
* `config/ssl/client.properties` — rewritten by `generate-certs.sh` (it is tracked,
  so `git checkout -- config/ssl/client.properties` restores the documented template)

The Compose project is named `kafka-lab-itest`, but container names
(`kafka1`, `zookeeper1`, …) are fixed by the renderer, so **stop a lab started
with `make up` first**. Host ports 19092–39093 must be free.

Teardown runs `docker compose down -v` at the end of each module. If a run is
interrupted, clean up with:

```bash
docker compose -p kafka-lab-itest -f docker-compose.itest.yml down -v
```

## Requirements

| Tool | Needed for |
|------|-----------|
| python3 ≥ 3.9, pytest, PyYAML | everything |
| bash, envsubst | shell script tests |
| openssl | `slow` certificate tests |
| docker + docker compose | `integration` tests |

Tests skip rather than fail when an optional tool is missing.
