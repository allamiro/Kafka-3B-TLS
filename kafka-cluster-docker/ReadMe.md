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

**Note:** This stack provides both PLAINTEXT and SSL listeners for maximum flexibility.

### 2.1 Generate SSL certificates

```bash
cd kafka-cluster-docker/ssl

# Generate self-signed certificates
./create-certs-simple.sh
```

This script creates:
* **Keystores**: `keystore/kafka-{0,1,2}.server.keystore.jks`
* **Truststore**: `truststore/kafka.truststore.jks`
* **Client config**: `client.properties`

### 2.2 Start the SSL cluster

```bash
# Start in detached mode
docker compose up -d

# Check containers (should show 6 containers: 3 controllers + 3 brokers)
docker compose ps
```

### 2.3 SSL Configuration

The SSL cluster provides hybrid connectivity:
- **PLAINTEXT listeners**: Port 9092 (inter-broker communication)
- **SSL listeners**: Port 9093 (encrypted client connections)
- **External access**: 
  - Broker 1: localhost:29092 (PLAINTEXT), localhost:29093 (SSL)
  - Broker 2: localhost:39092 (PLAINTEXT), localhost:39093 (SSL)
  - Broker 3: localhost:49092 (PLAINTEXT), localhost:49093 (SSL)

### 2.4 Verify SSL functionality

```bash
# Create topic using PLAINTEXT (basic connectivity test)
docker exec broker-1 /opt/kafka/bin/kafka-topics.sh \
  --create --topic demo-topic \
  --bootstrap-server broker-1:9092 \
  --partitions 3 --replication-factor 3

# Create topic using SSL (encrypted connection)
docker exec broker-1 /opt/kafka/bin/kafka-topics.sh \
  --create --topic secure-topic \
  --bootstrap-server broker-1:9093 \
  --command-config /etc/kafka/secrets/client.properties \
  --partitions 3 --replication-factor 3

# Test SSL message production
echo "Hello SSL Kafka!" | docker exec -i broker-1 \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server broker-1:9093 \
  --topic secure-topic \
  --producer.config /etc/kafka/secrets/client.properties

# Test SSL message consumption
docker exec broker-1 /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server broker-1:9093 \
  --topic secure-topic \
  --consumer.config /etc/kafka/secrets/client.properties \
  --from-beginning
```

### 2.5 External SSL client configuration

For external SSL clients, use the provided `client.properties` or create your own:

```properties
security.protocol=SSL
ssl.truststore.location=./truststore/kafka.truststore.jks
ssl.truststore.password=supersecret
ssl.endpoint.identification.algorithm=
```

Stop the SSL stack:

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
