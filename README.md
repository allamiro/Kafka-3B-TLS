# Kafka 3.9.2 + ZooKeeper 3.9.5 — Docker Compose Lab

[![CI](https://github.com/allamiro/Kafka-3B-TLS/actions/workflows/ci.yml/badge.svg?branch=kafka-distributed)](https://github.com/allamiro/Kafka-3B-TLS/actions/workflows/ci.yml)
[![Security](https://github.com/allamiro/Kafka-3B-TLS/actions/workflows/security.yml/badge.svg?branch=kafka-distributed)](https://github.com/allamiro/Kafka-3B-TLS/actions/workflows/security.yml)
[![Release](https://github.com/allamiro/Kafka-3B-TLS/actions/workflows/release.yml/badge.svg)](https://github.com/allamiro/Kafka-3B-TLS/actions/workflows/release.yml)
![Kafka 3.9.2](https://img.shields.io/badge/Apache%20Kafka-3.9.2-231F20?logo=apachekafka&logoColor=white)
![ZooKeeper 3.9.5](https://img.shields.io/badge/ZooKeeper-3.9.5-D22128)
![Mode: ZooKeeper](https://img.shields.io/badge/mode-ZooKeeper%20(not%20KRaft)-blue)

A reproducible, expandable **ZooKeeper-based** Apache Kafka cluster in Docker
Compose, with PLAINTEXT and SSL listeners and SSL inter-broker traffic. This is
the modern replacement for the legacy bare-metal/Systemd scripts in this repo.

> Branch: `kafka-distributed` · ZooKeeper mode · Kafka **3.9.2** · ZooKeeper **3.9.5**

## Contents

| | |
|---|---|
| [1. Project Overview](#1-project-overview) | [10. Air-Gapped Build](#10-air-gapped-build) |
| [2. Why Kafka 3.9.2 and ZooKeeper 3.9.5](#2-why-kafka-392-and-zookeeper-395) | [11. Certificate Generation](#11-certificate-generation) |
| [3. Why Kafka 4.x is NOT used](#3-why-kafka-4x-is-not-used-in-this-branch) | [12. Client Connection Examples](#12-client-connection-examples) |
| [4. Architecture](#4-architecture) | [13. Migration from Legacy Systemd Scripts](#13-migration-from-legacy-systemd-scripts) |
| [5. Repository Structure](#5-repository-structure) | [14. Troubleshooting](#14-troubleshooting) |
| [6. Quick Start](#6-quick-start) | [15. Environment Configuration](#15-environment-configuration) |
| [7. SSL Quick Start](#7-ssl-quick-start) | [16. Testing](#16-testing) |
| [8. PLAINTEXT Quick Start](#8-plaintext-quick-start) | [17. CI/CD and Releases](#17-cicd-and-releases) |
| [9. Scaling Beyond 3 Brokers](#9-scaling-beyond-3-brokers) | [18. Security](#18-security) |
| | [19. Future KRaft Branch](#19-future-kraft-branch) |

---

## 1. Project Overview

- 3 Kafka brokers + 3 ZooKeeper nodes by default; expandable to 5/7/10+ brokers.
- One generator (`scripts/render-compose.py`) produces the whole Compose file
  with unique broker IDs, volumes, listeners, ports, and per-broker certs.
- Security mode selectable from `.env`: `plaintext`, `ssl`, or `dual`.
- Certificates either **generated** (lab CA) or **imported** (enterprise PKI),
  all PKCS12, all openssl-only (no `keytool`/Java needed on the host).
- Internet **and** air-gapped image builds.

## 2. Why Kafka 3.9.2 and ZooKeeper 3.9.5

- **3.9.x is the last Kafka line that supports ZooKeeper mode.** This branch is
  specifically about ZooKeeper-based Kafka, so 3.9.2 is the right, current choice
  (`kafka_2.13-3.9.2.tgz`).
- **ZooKeeper 3.9.5** is the current 3.9 release (`apache-zookeeper-3.9.5-bin.tar.gz`),
  a large jump from the legacy 3.5.8 with logback-based logging and security fixes.

## 3. Why Kafka 4.x is NOT used in this branch

Kafka **4.0 removed ZooKeeper mode** — 4.x is **KRaft-only**. Putting 4.x here
would contradict the entire point of this branch. KRaft gets its own branch:

```text
kafka-distributed (this branch)        feature/docker-compose-kafka-kraft (future)
  Kafka 3.9.2                            Kafka 4.3.0+
  external ZooKeeper 3.9.5               no ZooKeeper (KRaft controllers)
  PLAINTEXT + SSL, min 3 brokers         PLAINTEXT + SSL
```

## 4. Architecture

See [docs/architecture.md](docs/architecture.md) for the full diagram and startup flow.

```mermaid
flowchart LR
    subgraph Host[Developer Host]
        PC[PLAINTEXT Client]
        SC[SSL Client]
    end
    subgraph Docker[Docker Network: kafka-net]
        subgraph ZK[ZooKeeper Ensemble]
            ZK1[zookeeper1<br/>2181/2888/3888]
            ZK2[zookeeper2<br/>2181/2888/3888]
            ZK3[zookeeper3<br/>2181/2888/3888]
        end
        subgraph Kafka[Kafka Brokers]
            K1[kafka1<br/>PLAINTEXT 9092<br/>SSL 9093]
            K2[kafka2<br/>PLAINTEXT 9092<br/>SSL 9093]
            K3[kafka3<br/>PLAINTEXT 9092<br/>SSL 9093]
        end
    end
    PC -->|localhost:19092| K1
    SC -->|localhost:19093| K1
    K1 -->|ZooKeeper metadata| ZK1
    K2 -->|ZooKeeper metadata| ZK2
    K3 -->|ZooKeeper metadata| ZK3
    ZK1 <-->|quorum| ZK2
    ZK2 <-->|quorum| ZK3
    ZK1 <-->|quorum| ZK3
    K1 <-->|SSL inter-broker| K2
    K2 <-->|SSL inter-broker| K3
    K1 <-->|SSL inter-broker| K3
```

### Ports

| Service | Internal port | Host port |
|---------|---------------|-----------|
| kafka1 | 9092 PLAINTEXT | 19092 |
| kafka2 | 9092 PLAINTEXT | 29092 |
| kafka3 | 9092 PLAINTEXT | 39092 |
| kafka1 | 9093 SSL | 19093 |
| kafka2 | 9093 SSL | 29093 |
| kafka3 | 9093 SSL | 39093 |
| zookeeper1 | 2181 | not exposed by default |
| zookeeper2 | 2181 | not exposed by default |
| zookeeper3 | 2181 | not exposed by default |

ZooKeeper quorum ports `2888`/`3888` stay internal to `kafka-net`.

## 5. Repository Structure

```text
.
├── README.md
├── docker-compose.yml            # pre-rendered default (3+3, dual)
├── docker-compose.plaintext.yml  # pre-rendered plaintext variant
├── docker-compose.ssl.yml        # pre-rendered ssl variant
├── docker-compose.generated.yml  # produced by `make render` (git-ignored)
├── .env.example                  # fully documented config
├── Makefile
├── images/
│   ├── kafka/        Dockerfile, entrypoint.sh, templates/
│   └── zookeeper/    Dockerfile, entrypoint.sh, templates/
├── certs/
│   ├── openssl/      root-ca.cnf, intermediate-ca.cnf, broker-san.cnf.tpl
│   └── generated/    OUTPUT (git-ignored)
├── config/
│   ├── plaintext/client.properties
│   └── ssl/client.properties
├── scripts/          render-compose.py, prepare/generate/import certs, helpers
├── tests/
│   ├── unit/         renderer, .env rules, entrypoints, PKI, repo hygiene
│   └── integration/  real cluster: formation, replication, produce/consume, TLS
├── docs/             architecture, migration, ssl-design, scaling, airgapped, troubleshooting
├── .github/workflows/ ci.yml, security.yml, release.yml
├── SECURITY.md       threat model, hardening checklist, reporting
└── vendor/           air-gapped tarballs (git-ignored)
```

## 6. Quick Start

```bash
cp .env.example .env          # or: make env
make certs                    # SSL material (dual mode default)
make render BROKERS=3 ZOOKEEPERS=3
make build
make up
make ps                       # wait until healthy
make create-topic TOPIC=test-events
make list-topics
make describe
make down
```

`docker` + `docker compose` are the only host prerequisites for running the
lab (the Kafka CLI runs inside the containers). `openssl` and `python3` are
needed on the host for `make certs` and `make render`; `make test` additionally
wants `pytest`.

Sanity-check a change before starting anything:

```bash
make validate                 # .env sizing and security mode
make test-fast                # unit tests, a few seconds
```

## 7. SSL Quick Start

```env
KAFKA_SECURITY_MODE=ssl
KAFKA_CERT_MODE=generate
```

```bash
make certs
make render
make up
make create-topic TOPIC=test-events SECURITY=ssl
make produce-ssl  TOPIC=test-events     # type messages, Ctrl-D
make consume-ssl  TOPIC=test-events     # Ctrl-C to stop
```

## 8. PLAINTEXT Quick Start

```env
KAFKA_SECURITY_MODE=plaintext
```

```bash
make render            # certs not required in plaintext mode
make up
make create-topic TOPIC=test-events
make produce-plaintext TOPIC=test-events
make consume-plaintext TOPIC=test-events
```

## 9. Scaling Beyond 3 Brokers

```bash
make certs  BROKERS=5
make render BROKERS=5 ZOOKEEPERS=3
make up
```

ZooKeeper stays at 3 (or 5) regardless of broker count — it is a metadata
quorum, not a data plane. Full rules and rationale in [docs/scaling.md](docs/scaling.md).

## 10. Air-Gapped Build

Place the **binary** tarballs in `vendor/` and build offline:

```text
vendor/kafka_2.13-3.9.2.tgz
vendor/apache-zookeeper-3.9.5-bin.tar.gz   # the -bin artifact, not source
```

```bash
make vendor-sync   # copies provided packages/ tarballs into vendor/ (if present)
make build
```

Details and caveats: [docs/airgapped-build.md](docs/airgapped-build.md).

## 11. Certificate Generation

```bash
make certs          # generate (lab CA) or import (enterprise PKI), per .env
```

- `KAFKA_CERT_MODE=generate` → Root CA → Intermediate CA → per-broker certs
  (with SANs) → PKCS12 keystores + PEM CA trust material for brokers and clients.
- `KAFKA_CERT_MODE=import` → validates and wraps your existing CA/broker certs.

Design and SAN requirements: [docs/ssl-design.md](docs/ssl-design.md).

## 12. Client Connection Examples

In-network (any broker discovers the whole cluster from metadata):

```bash
# PLAINTEXT
kafka-console-producer.sh --bootstrap-server kafka1:9092 --topic test-events
# SSL (in-container client config written by the entrypoint)
kafka-console-producer.sh --bootstrap-server kafka1:9093 --topic test-events \
  --producer.config /opt/kafka/config/client-ssl.properties
```

From the host (requires a local Kafka CLI):

```bash
kafka-console-consumer.sh --bootstrap-server localhost:19092 --topic test-events --from-beginning
kafka-console-consumer.sh --bootstrap-server localhost:19093 --topic test-events --from-beginning \
  --consumer.config config/ssl/client.properties
```

## 13. Migration from Legacy Systemd Scripts

The old `kafka/Install-Kafka.sh`, `zookeeper/Install-ZooKeeper.sh`, and
`Set-ServerBaselineConfig.sh` (Kafka 2.5.0 / ZooKeeper 3.5.8, JKS, firewalld,
hardcoded passwords) map directly onto this design — see
[docs/migration-from-systemd.md](docs/migration-from-systemd.md).

## 14. Troubleshooting

Common failures (ZK not `imok`, SSL handshake, SANs, RF too high, port in use,
stale volumes) and fixes: [docs/troubleshooting.md](docs/troubleshooting.md).

## 15. Environment Configuration

Every variable is documented in [.env.example](.env.example). Key selectors:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `KAFKA_SECURITY_MODE` | yes | `dual` | `plaintext` \| `ssl` \| `dual` |
| `KAFKA_CERT_MODE` | yes | `generate` | `generate` local CA, or `import` external certs |
| `EXTERNAL_ROOT_CA_CERT` | import | empty | Path to existing Root CA certificate |
| `EXTERNAL_INTERMEDIATE_CA_CERT` | optional | empty | Path to existing Intermediate CA |
| `EXTERNAL_BROKER_CERTS_DIR` | import | empty | Dir with `kafkaN.crt` / `kafkaN.key` |
| `KAFKA_SSL_PASSWORD` | ssl/dual | `changeit` | Password for PKCS12 stores |
| `SSL_CLIENT_AUTH` | optional | `none` | `none` or `required` (mTLS) |
| `BROKER_COUNT` | yes | `3` | Number of Kafka brokers (≥3) |
| `ZOOKEEPER_COUNT` | yes | `3` | Number of ZooKeeper nodes (3 or 5) |

### Example: dual mode (both listeners)

```env
KAFKA_SECURITY_MODE=dual
INTER_BROKER_LISTENER_NAME=SSL
KAFKA_CERT_MODE=generate
BROKER_COUNT=3
ZOOKEEPER_COUNT=3
```

```bash
make certs && make render && make up
make produce-plaintext TOPIC=test-events
make produce-ssl       TOPIC=test-events
```

### Example: import enterprise CA + broker certs

```env
KAFKA_SECURITY_MODE=ssl
KAFKA_CERT_MODE=import
EXTERNAL_ROOT_CA_CERT=/secure/pki/root-ca.crt
EXTERNAL_INTERMEDIATE_CA_CERT=/secure/pki/intermediate-ca.crt
EXTERNAL_BROKER_CERTS_DIR=/secure/pki/kafka-brokers   # kafka1.crt/.key, kafka2.crt/.key, ...
KAFKA_SSL_PASSWORD=change-this
```

```bash
make certs && make render && make up
```

## 16. Testing

The suite is pytest-based and split into unit tests (no Docker, seconds) and
end-to-end tests that build the images and start a real cluster.

```bash
make test-deps          # pip install -r tests/requirements.txt
make test               # unit tests
make test-fast          # unit tests, skipping certificate generation
make test-integration   # real cluster: needs Docker, `make down` first
make lint               # shellcheck / bash -n / yamllint
```

| Layer | Covers |
|-------|--------|
| `tests/unit/test_render_compose.py` | Topology generation: broker/quorum sizing rules, listeners, ports, volumes, cert mounts, determinism |
| `tests/unit/test_env_helpers.py` | `.env` loading and the environment > `.env` > default precedence |
| `tests/unit/test_validate_env.py` | Guard rails: broker count ≥ 3, quorum of 3 or 5, RF ≤ brokers, security and cert modes, imported PKI paths |
| `tests/unit/test_entrypoints.py` | `server.properties` / `zoo.cfg` rendering, and fail-fast when SSL material or identity variables are missing |
| `tests/unit/test_committed_compose.py` | The three pre-rendered Compose files still match the renderer |
| `tests/unit/test_certs.py` | The lab PKI, re-verified with openssl: chain, SANs, key agreement, PKCS12 stores, permissions, mutual TLS |
| `tests/unit/test_repo_hygiene.py` | Shell syntax, strict mode, secret hygiene, README/Makefile drift |
| `tests/integration/test_plaintext_cluster.py` | Ensemble election, broker registration in ZooKeeper, replicated topics, produce/consume, survival of a broker restart |
| `tests/integration/test_ssl_cluster.py` | TLS handshake against the lab CA, cleartext port closed, encrypted inter-broker replication, produce/consume over TLS |

Unit tests run against a temporary copy of the repository, so they never write
into your working tree. Details and caveats: [tests/README.md](tests/README.md).

## 17. CI/CD and Releases

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| [ci.yml](.github/workflows/ci.yml) | push, PR | Lint (ShellCheck, `bash -n`, hadolint, yamllint, actionlint) · unit tests on Python 3.9 and 3.12 · render + `docker compose config` across five topologies · build both images · plaintext and SSL end-to-end suites |
| [security.yml](.github/workflows/security.yml) | push, PR, weekly | gitleaks over tree and history · Trivy filesystem and image scans · assertions on the shipped security defaults |
| [release.yml](.github/workflows/release.yml) | tag `v*` | Re-verify, publish multi-arch images to GHCR, and attach a checksummed offline lab bundle to a GitHub release |

Cutting a release:

```bash
git tag -a v1.0.0 -m "Kafka 3.9.2 + ZooKeeper 3.9.5 lab"
git push origin v1.0.0
```

That publishes `ghcr.io/allamiro/kafka-3b-tls/kafka:1.0.0` and
`.../zookeeper:1.0.0` for `linux/amd64` and `linux/arm64`, plus
`kafka-zookeeper-lab-v1.0.0.tar.gz` with the Compose files, image definitions,
certificate tooling, scripts and docs. Tags containing a hyphen
(`v1.0.0-rc1`) are published as pre-releases and do not move `latest`.

## 18. Security

This is a **lab** cluster. The full threat model, what the defaults do and do
not protect, the hardening checklist and how to report a vulnerability are in
[SECURITY.md](SECURITY.md). The short version:

- **Do not** use the default passwords (`changeit`) anywhere you care about.
- **Do not** commit `.env`, generated private keys, or certificates — all are
  git-ignored, and CI fails the build if they appear.
- TLS encrypts traffic and verifies the *broker's* identity; it does not
  authenticate clients. Use `SSL_CLIENT_AUTH=required` for mutual TLS.
- There is **no SASL and no ACL** configuration — any client that trusts the CA
  has full access. Add both before exposing this beyond a lab.
- ZooKeeper is unauthenticated and deliberately not published to the host.

## 19. Future KRaft Branch

When this branch is stable, the KRaft variant goes in
`feature/docker-compose-kafka-kraft`: Kafka 4.3.0+, no ZooKeeper, KRaft
controllers + brokers, PLAINTEXT + SSL. Keep the two cleanly separated — do not
mix KRaft and ZooKeeper concerns in one branch.
