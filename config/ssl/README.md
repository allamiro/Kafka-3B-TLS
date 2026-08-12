# config/ssl

Client configuration for talking to the SSL listener (`:9093`).

## Two ways to run Kafka CLI tools

### 1. Inside a broker container (recommended — no host tooling needed)

The helper scripts (`scripts/produce-ssl.sh`, `scripts/consume-ssl.sh`, …) do
this for you. They exec the CLI inside `kafka1` and use the in-container client
config that the broker entrypoint writes at
`/etc/kafka/secrets/healthcheck.properties`.

### 2. From the host (requires a local Kafka CLI + Java)

Use [client.properties](client.properties) in this directory and a host SSL
port such as `localhost:19093`:

```bash
kafka-console-producer.sh \
  --bootstrap-server localhost:19093 \
  --topic test-events \
  --producer.config config/ssl/client.properties
```

`make certs` (generate mode) rewrites `client.properties` with the password
from your `.env`. The `ssl.truststore.location` is **relative to the repo
root**, so run host-side commands from the repository root.

## Mutual TLS

When `SSL_CLIENT_AUTH=required`, `make certs` also adds the client keystore
(`ssl.keystore.*`) lines and generates `certs/generated/client/kafka.client.keystore.p12`.
