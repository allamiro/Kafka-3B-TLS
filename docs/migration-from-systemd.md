# Migration: Legacy Systemd / Bare-Metal → Docker Compose

The original repository installed Kafka and ZooKeeper directly on CentOS VMs
using shell scripts, Systemd unit files, manual OpenSSL/keytool steps, and
firewalld rules. This branch replaces all of that with a reproducible Docker
Compose lab.

## Version changes

| Component | Legacy | This branch |
|-----------|--------|-------------|
| Kafka | 2.5.0 (`kafka_2.12-2.5.0.tgz`) | **3.9.2** (`kafka_2.13-3.9.2.tgz`) |
| ZooKeeper | 3.5.8 | **3.9.5** |
| Java | `yum install java` (8/11) | **17** (eclipse-temurin) |
| Keystore format | JKS | **PKCS12** |
| Logging | log4j 1.x (both) | Kafka log4j 1.x · ZooKeeper **logback** (3.9.x changed) |

> Kafka **4.x is intentionally NOT used** here: ZooKeeper mode was removed in
> Kafka 4.0, so 4.x is KRaft-only. KRaft belongs in a separate
> `feature/docker-compose-kafka-kraft` branch.

## Concept mapping

| Old Systemd / bare metal | New Docker Compose design |
|--------------------------|---------------------------|
| `/opt/kafka` | Kafka image (`images/kafka/`) |
| `/opt/kafka/data` | `kafkaN-data` named volume → `/var/lib/kafka/data` |
| `/opt/kafka/ssl` | `certs/generated/kafkaN` mounted read-only at `/etc/kafka/secrets` |
| `/etc/kafka/ssl`, `/etc/kafka/ca` | `certs/generated/` (CA + per-broker material) |
| `/opt/zookeeper` | ZooKeeper image (`images/zookeeper/`) |
| `/opt/zookeeper/dataDir` | `zookeeperN-data` named volume → `/var/lib/zookeeper/data` |
| `/opt/zookeeper/logs` | `zookeeperN-log` named volume → `/var/lib/zookeeper/log` |
| `/etc/systemd/system/kafka.service` | compose service `kafkaN` (`restart: unless-stopped`) |
| `/etc/systemd/system/zookeeper.service` | compose service `zookeeperN` |
| `systemctl start kafka` / `zookeeper` | `docker compose up` / `make up` |
| `useradd kafka` / `useradd zookeeper` | non-root users baked into the images (uid 996 / 994) |
| firewalld rich rules (9093/2181/2888/3888) | documented host port mappings; quorum ports stay in-network |
| `KAFKA0001.hq.corp` | `kafka1` container DNS + optional SAN alias `KAFKA0001.hq.corp` |
| `KAFKA0002.hq.corp` | `kafka2` + alias `KAFKA0002.hq.corp` |
| `KAFKA0003.hq.corp` | `kafka3` + alias `KAFKA0003.hq.corp` |
| `broker.id=1` | `BROKER_ID=1` env var (per service) |
| `zookeeper.connect=KAFKA0001:2181,...` | `zookeeper1:2181,zookeeper2:2181,zookeeper3:2181` |
| manual `openssl` + `keytool` per host, `scp` CSRs between brokers | `make certs` → `scripts/generate-certs.sh` (openssl-only, all brokers at once) |
| hardcoded `KAFKA_PASS=kafka123`, `ca123` | `.env` (`KAFKA_SSL_PASSWORD`, `KAFKA_CA_PASSWORD`), never committed |
| `Set-ServerBaselineConfig.sh` (IPs, DNS, yum, kernel) | not needed — containers are the baseline |

## What was deliberately dropped

- **Hardcoded passwords** in scripts → moved to `.env` (git-ignored).
- **Committed private keys / certificates** → `certs/generated/` is git-ignored.
- **Manual copy/paste CSR signing** across hosts → one script signs every broker.
- **Per-host Systemd units** → declarative compose services.
- **Broad firewalld rules** → only the host ports you choose to publish.
- **Static `/etc/hosts` + DNS A records** → Docker network DNS.

## Behavioural parity

- Still a **3-broker** cluster by default, still **SSL inter-broker**, still a
  Root CA → Intermediate CA → broker-cert chain — but reproducible and expandable.
- The legacy `ssl.client.auth=none` default is preserved (`SSL_CLIENT_AUTH=none`),
  with `required` available for mutual TLS.
