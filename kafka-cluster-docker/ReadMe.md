# Kafka Multi-Node Docker Cluster

This folder contains **two** Docker Compose stacks for experimenting with a six-node Apache Kafka KRaft cluster (3 controllers + 3 brokers).

| Stack | Security | Location |
|-------|----------|----------|
| Plaintext | No encryption | `plaintext/docker-compose.yml` |
| SSL/TLS   | Encrypted inter-broker & client traffic | `ssl/docker-compose.yml` |

You can run either stack on its own, or both in parallel if you map the SSL stack to different host ports (see below).

---
## Prerequisites

* Docker 20.10+ and **docker compose v2** (`docker compose version`)
* ~4 GB of free RAM
* Ports 29092, 39092, 49092 free on localhost (or your own choice of ports)

Optional for TLS:
* `openssl` and the JDK’s `keytool` (used by the included `create-certs.sh` helper)

---
## 1.  Run the Plaintext stack

```bash
cd kafka-cluster-docker

# Start in detached mode
docker compose -f plaintext/docker-compose.yml up -d

# Check containers
docker compose -f plaintext/docker-compose.yml ps
```

### Verify

```bash
# Create a topic from inside any broker container
docker exec -it broker-1 kafka-topics.sh \
  --bootstrap-server broker-1:19092 \
  --create --topic demo --partitions 3 --replication-factor 3

# From host (client-side port)
/usr/bin/kafka-topics --bootstrap-server localhost:29092 --list
```

Stop the stack:

```bash
docker compose -f plaintext/docker-compose.yml down -v
```

---
## 2.  Run the SSL/TLS stack

### 2.1 Generate certificates (one-time)

```bash
cd kafka-cluster-docker/ssl
./create-certs.sh
```

This script will create:
* `broker-1.keystore.p12`, `broker-2.keystore.p12`, `broker-3.keystore.p12`
* Shared `broker.truststore.p12`
* CA files `ca.crt/ca.key`

### 2.2 Start the cluster

```bash
docker compose up -d          # in kafka-cluster-docker/ssl
```

### 2.3 Client connection examples

```bash
# Using the Kafka CLI from host
/usr/bin/kafka-topics \
  --bootstrap-server localhost:29092 \
  --command-config <(cat <<EOF
ssl.truststore.location=ssl/certs/broker.truststore.p12
ssl.truststore.password=password
ssl.keystore.location=ssl/certs/broker-1.keystore.p12
ssl.keystore.password=password
ssl.key.password=password
security.protocol=SSL
EOF
) --list
```

> ⚠️  The CLI needs to run with matching truststore/keystore paths. In production you would distribute client certificates differently.

Stop the TLS stack:

```bash
docker compose down -v
```

---
## 3.  Running **both** stacks simultaneously (optional)

To avoid port clashes, change the host mappings in `ssl/docker-compose.yml`, e.g.:

* broker-1 → `29192:9092`
* broker-2 → `39192:9092`
* broker-3 → `49192:9092`

Also update the `SSL_HOST://localhost:<port>` part in each broker’s `KAFKA_ADVERTISED_LISTENERS`.

---
## 4.  Cleaning up all resources

```bash
docker compose -f plaintext/docker-compose.yml down -v --remove-orphans
cd ssl && docker compose down -v --remove-orphans && cd ..
```

---
## 5.  Troubleshooting

* **Brokers won’t start** – ensure the controllers are up and healthy (`docker logs controller-1`).
* **SSL handshake errors** – regenerate certs, check that passwords match the ones in `KAFKA_SSL_*_CREDENTIALS`.
* **Port already in use** – adjust host-side ports or stop the other stack.

<hr>
Happy streaming!  🚀
