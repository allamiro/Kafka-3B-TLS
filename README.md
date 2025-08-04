# Kafka 3 Broker Test Cluster
Demonstrate how to create a 3 broker zookeeper / kafka cluster with TLS communication.  

Broker Names and Node IDs
###
IP Address: 10.0.0.101
FQDN: KAFKA0001.hq.corp
Broker ID: 1

###
IP Address: 10.0.0.102
FQDN: KAFKA0002.hq.corp
Broker ID: 2

###
IP Address: 10.0.0.103
FQDN: KAFKA0003.hq.corp
Broker ID: 3

---

## Docker-Based Multi-Node Cluster (2025 Update)

This project now ships with **Docker Compose** stacks that spin up a six-node Kafka KRaft cluster (3 controllers + 3 brokers) for quick local testing.

| Stack | Security | Compose file | Status |
|-------|----------|--------------|--------|
| Plaintext | None | `kafka-cluster-docker/plaintext/docker-compose.yml` | ✅ **Ready** |
| SSL/TLS   | Hybrid PLAINTEXT/SSL listeners | `kafka-cluster-docker/ssl/docker-compose.yml` | ✅ **Ready** |

### Quick Start

**Plaintext Cluster:**
```bash
cd kafka-cluster-docker
docker compose -f plaintext/docker-compose.yml up -d
```

**SSL/TLS Cluster:**
```bash
# Generate certificates (one-time setup)
cd kafka-cluster-docker/ssl
./create-certs-simple.sh

# Start cluster
docker compose up -d

# Test SSL connectivity
echo "Hello SSL!" | docker exec -i broker-1 \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server broker-1:9093 \
  --topic test-topic \
  --producer.config /etc/kafka/secrets/client.properties
```

### Features

- **Official Apache Kafka Docker images** (not Confluent/Bitnami)
- **KRaft mode** (no Zookeeper dependency)
- **SSL/TLS encryption** with self-signed certificates
- **Hybrid configuration**: PLAINTEXT for inter-broker, SSL for clients
- **Full end-to-end testing** validated

Full instructions and examples: [`kafka-cluster-docker/ReadMe.md`](kafka-cluster-docker/ReadMe.md)

