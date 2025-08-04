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

| Stack | Security | Compose file |
|-------|----------|--------------|
| Plaintext | none | `kafka-cluster-docker/plaintext/docker-compose.yml` |
| SSL/TLS   | TLS on all broker & client traffic | `kafka-cluster-docker/ssl/docker-compose.yml` |

Getting started:

```bash
# Plaintext
cd kafka-cluster-docker
docker compose -f plaintext/docker-compose.yml up -d

# TLS (run once to make certs, then start)
cd kafka-cluster-docker/ssl
./create-certs.sh
docker compose up -d
```

Full instructions live in [`kafka-cluster-docker/ReadMe.md`](kafka-cluster-docker/ReadMe.md).

