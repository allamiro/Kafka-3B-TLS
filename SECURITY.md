# Security Policy

This repository ships a **laboratory** Kafka cluster: a reproducible
ZooKeeper-based Apache Kafka 3.9.2 deployment for development, testing and
migration rehearsal. It is not a hardened production distribution. This
document states exactly what that means, what the defaults do and do not
protect, and how to report a problem.

---

## 1. Supported versions

| Component | Version | Support |
|-----------|---------|---------|
| Apache Kafka | 3.9.2 (ZooKeeper mode) | Supported — 3.9.x is the **last** Kafka line with ZooKeeper mode |
| Apache ZooKeeper | 3.9.5 | Supported |
| Base image | `eclipse-temurin:17-jre` | Rebuilt and CVE-scanned weekly in CI |
| Legacy systemd installers (`kafka/`, `zookeeper/`, `Set-ServerBaselineConfig.sh`) | Kafka 2.5.0 / ZooKeeper 3.5.8 | **Unsupported**, retained for migration reference only — do not deploy |

Only the tip of the `kafka-distributed` branch receives fixes. Kafka 4.x is
KRaft-only and out of scope here; it will get its own branch.

Upstream security advisories:
[Kafka](https://kafka.apache.org/cve-list),
[ZooKeeper](https://zookeeper.apache.org/security.html).

---

## 2. Reporting a vulnerability

**Do not open a public issue for a security problem.**

1. Preferred: open a private advisory via **Security → Report a vulnerability**
   on the GitHub repository.
2. Alternative: email the maintainer at <allamiro@gmail.com> with `SECURITY`
   in the subject.

Please include the affected file or component, the version or commit, a
description of the impact, and reproduction steps. You will get an
acknowledgement within **5 working days** and a assessment within **15 working
days**. Fixes are released as a new tag; the advisory is published once a fix
is available.

Vulnerabilities in Apache Kafka or ZooKeeper themselves belong to the Apache
Security Team (<security@apache.org>) — report upstream first, then tell us so
the pinned versions can be moved.

---

## 3. What the defaults actually give you

| Control | Default | Notes |
|---------|---------|-------|
| Encryption in transit | **On** in `ssl` and `dual` modes | TLS 1.2/1.3 only |
| Inter-broker encryption | **On** (`INTER_BROKER_LISTENER_NAME=SSL`) | Brokers authenticate each other with the lab CA |
| Hostname verification | **On** (`ssl.endpoint.identification.algorithm=https`) | Broker certificates carry SANs for the service name, FQDN, `localhost` and `127.0.0.1` |
| Certificate authority | Two-tier (root → intermediate) | Generated locally, or import your own with `KAFKA_CERT_MODE=import` |
| Key store format | PKCS12 | Generated with openssl only; no `keytool` on the host |
| Client authentication | **Off** (`SSL_CLIENT_AUTH=none`) | Set to `required` for mutual TLS |
| Authentication (SASL) | **Not configured** | Any client that trusts the CA may connect |
| Authorization (ACLs) | **Not configured** | Every connected client has full access |
| Container user | Non-root (`kafka` uid 996, `zookeeper` uid 994) | Enforced in CI |
| Certificate mounts | Read-only (`:ro`) | Enforced in CI |
| ZooKeeper client port | Not published to the host | Quorum ports stay inside `kafka-net` |
| ZooKeeper authentication | **None** | Anyone who reaches port 2181 controls cluster metadata |
| Private key files | `0600` | CA keys and broker keys are owner-only |
| PKCS12 store files | `0644` | The broker runs as an unprivileged non-root user and bind-mounts them read-only, so it must be able to read them; the contents are protected by `KAFKA_SSL_PASSWORD` |
| Store passwords | `changeit` | Placeholder — see below |
| Data at rest | **Not encrypted** | Kafka log segments live on plain Docker volumes |

### The gaps that matter most

* **No authentication and no authorization.** In `ssl` mode TLS proves the
  *broker's* identity to clients, not the reverse. Anyone who can reach a
  listener and trusts the CA can read and write every topic. Enable
  `SSL_CLIENT_AUTH=required`, and add SASL plus ACLs, before this is exposed
  to anything untrusted.
* **ZooKeeper is unauthenticated.** It is reachable only inside the Compose
  network by default. Do not publish port 2181.
* **`changeit` is a placeholder, not a password.** It is in `.env.example`, in
  this repository, and therefore public. Change it before generating anything
  you intend to keep.
* **The generated CA is a lab CA.** Its private keys sit on the developer's
  disk under `certs/generated/ca/`, encrypted with `KAFKA_CA_PASSWORD` — which
  also defaults to `changeit`. Never distribute this CA beyond the lab.

---

## 4. Handling secrets

Never committed, and enforced by both `.gitignore` and CI:

```text
.env                     real configuration, including passwords
certs/generated/**       CA keys, broker keys, PKCS12 stores
*.key *.crt *.csr *.pem *.p12 *.jks *.keystore *.truststore
```

CI fails the build if any of those become tracked, if a PEM block appears in a
tracked file, or if `gitleaks` finds a credential in the working tree or in
history. `tests/unit/test_repo_hygiene.py` runs the same checks locally.

If a key is ever committed: rotate it first (regenerate the CA and every
broker certificate with `make clean && make certs`), then purge the history —
rotation matters more than rewriting git, because anything pushed must be
assumed captured.

For anything beyond a lab, keep passwords in a secrets manager (Vault,
SOPS-encrypted files, Kubernetes secrets) rather than in `.env`, and mount the
key stores from that source.

---

## 5. Hardening checklist

Before any deployment that is not a throwaway lab:

- [ ] `KAFKA_SECURITY_MODE=ssl` — remove the PLAINTEXT listener entirely
- [ ] `SSL_CLIENT_AUTH=required` — mutual TLS, so clients prove who they are
- [ ] Replace `KAFKA_SSL_PASSWORD` and `KAFKA_CA_PASSWORD` with generated secrets
- [ ] `KAFKA_CERT_MODE=import` — use the organisation's PKI instead of the lab CA
- [ ] Shorten `CERT_VALIDITY_DAYS` (the 3650-day default is a lab convenience) and plan rotation
- [ ] Add SASL (SCRAM or GSSAPI) and enable the authorizer with ACLs
- [ ] Authenticate ZooKeeper and restrict it to the broker network
- [ ] Keep `AUTO_CREATE_TOPICS_ENABLE=false`
- [ ] Do not publish broker ports to `0.0.0.0` on a shared host
- [ ] Set resource limits on the containers and monitor them
- [ ] Encrypt the underlying volumes if messages are sensitive at rest
- [ ] Track upstream Kafka/ZooKeeper advisories and rebuild the images

---

## 6. Security controls in CI

| Workflow | Check |
|----------|-------|
| `security.yml` → `secrets` | `gitleaks` over the working tree and full history; tracked-key-material check |
| `security.yml` → `filesystem` | Trivy filesystem scan (vulnerabilities, secrets, misconfiguration), HIGH/CRITICAL fails the build |
| `security.yml` → `images` | Trivy image scan of both images, SARIF uploaded to code scanning; base-image CVEs are reported, not gated |
| `security.yml` → `configuration` | Asserts hostname verification is on, no obsolete TLS versions, images drop root, certificate mounts are `:ro` |
| `ci.yml` → `lint` | ShellCheck, `bash -n`, hadolint, yamllint, actionlint |
| `ci.yml` → `integration` | Proves TLS is enforced: cleartext port closed, handshake verifies against the CA, a client without the truststore is refused |
| `dependabot.yml` | Weekly base-image and action updates, monthly test dependencies |

---

## 7. Scope

In scope: the Compose topology, the image definitions and entrypoints, the
certificate tooling under `scripts/` and `certs/`, the helper scripts, the
Makefile, and the CI workflows.

Out of scope: vulnerabilities in Apache Kafka, Apache ZooKeeper, Docker or the
base image (report upstream); the legacy systemd installers; and findings that
amount to "the documented lab defaults are insecure" — those are stated above
and are deliberate. A report showing that a *documented* control does not
actually hold is very much in scope.
