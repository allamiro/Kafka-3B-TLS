# Kafka SSL/TLS Docker Cluster

This directory contains a multi-node Apache Kafka cluster with SSL/TLS encryption support using Docker Compose.

## Overview

The SSL cluster provides:
- **3 Controllers** (KRaft mode) for cluster coordination
- **3 Brokers** with both PLAINTEXT and SSL listeners
- **Hybrid Configuration**: Inter-broker communication via PLAINTEXT, client SSL connections supported
- **Self-signed certificates** for development and testing

## Quick Start

1. **Generate SSL certificates:**
   ```bash
   ./create-certs-simple.sh
   ```

2. **Start the cluster:**
   ```bash
   docker compose up -d
   ```

3. **Verify cluster status:**
   ```bash
   docker compose ps
   ```

## SSL Configuration

### Listeners
- **PLAINTEXT**: Port 9092 (internal cluster communication)
- **SSL**: Port 9093 (encrypted client connections)

### External Access Ports
- **Broker 1**: localhost:29092 (PLAINTEXT), localhost:29093 (SSL)
- **Broker 2**: localhost:39092 (PLAINTEXT), localhost:39093 (SSL)
- **Broker 3**: localhost:49092 (PLAINTEXT), localhost:49093 (SSL)

### Certificate Files
- **Keystores**: `keystore/kafka-{0,1,2}.server.keystore.jks`
- **Truststore**: `truststore/kafka.truststore.jks`
- **Client Config**: `client.properties`

## Usage Examples

### Create Topic (PLAINTEXT)
```bash
docker exec broker-1 /opt/kafka/bin/kafka-topics.sh \
  --create --topic my-topic \
  --bootstrap-server broker-1:9092 \
  --partitions 3 --replication-factor 3
```

### Create Topic (SSL)
```bash
docker exec broker-1 /opt/kafka/bin/kafka-topics.sh \
  --create --topic secure-topic \
  --bootstrap-server broker-1:9093 \
  --command-config /etc/kafka/secrets/client.properties \
  --partitions 3 --replication-factor 3
```

### Produce Messages (SSL)
```bash
echo "Hello SSL Kafka!" | docker exec -i broker-1 \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server broker-1:9093 \
  --topic secure-topic \
  --producer.config /etc/kafka/secrets/client.properties
```

### Consume Messages (SSL)
```bash
docker exec broker-1 /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server broker-1:9093 \
  --topic secure-topic \
  --consumer.config /etc/kafka/secrets/client.properties \
  --from-beginning
```

## Client Configuration

For external SSL clients, use the following configuration:

```properties
security.protocol=SSL
ssl.truststore.location=./truststore/kafka.truststore.jks
ssl.truststore.password=supersecret
ssl.endpoint.identification.algorithm=
```

## Architecture

```
┌─────────────┬─────────────┬─────────────┐
│ Controller-1│ Controller-2│ Controller-3│
│   (KRaft)   │   (KRaft)   │   (KRaft)   │
└─────────────┴─────────────┴─────────────┘
┌─────────────┬─────────────┬─────────────┐
│   Broker-1  │   Broker-2  │   Broker-3  │
│ :9092/:9093 │ :9092/:9093 │ :9092/:9093 │
│ PLAIN / SSL │ PLAIN / SSL │ PLAIN / SSL │
└─────────────┴─────────────┴─────────────┘
```

## Security Notes

- Uses **self-signed certificates** suitable for development/testing
- **Hostname verification disabled** for self-signed certificates
- **Inter-broker communication** uses PLAINTEXT for stability
- **Client connections** can use SSL for encryption

## Troubleshooting

### Check Broker Logs
```bash
docker compose logs broker-1 --tail 50
```

### Verify SSL Configuration
```bash
docker exec broker-1 ls -la /etc/kafka/secrets/
```

### Test SSL Connection
```bash
openssl s_client -connect localhost:29093 -servername broker-1
```

## Cleanup

```bash
docker compose down
docker volume prune -f
```

## Files Structure

```
ssl/
├── docker-compose.yml          # SSL cluster configuration
├── create-certs-simple.sh      # Certificate generation script
├── client.properties           # SSL client configuration
├── keystore/                   # Broker keystores
│   ├── kafka-0.server.keystore.jks
│   ├── kafka-1.server.keystore.jks
│   ├── kafka-2.server.keystore.jks
│   └── *_creds                 # Password files
├── truststore/                 # Client truststore
│   └── kafka.truststore.jks
└── README.md                   # This file
```
