# SSL / TLS Design

## Trust chain

```text
Root CA  (self-signed, 4096-bit, keyCertSign)
  └── Intermediate CA  (signed by Root, pathlen:0)
        ├── kafka1 cert  (SAN: kafka1, KAFKA0001.hq.corp, localhost, 127.0.0.1)
        ├── kafka2 cert  (SAN: kafka2, KAFKA0002.hq.corp, localhost, 127.0.0.1)
        ├── kafka3 cert  (SAN: kafka3, KAFKA0003.hq.corp, localhost, 127.0.0.1)
        └── (optional) kafka-client cert  (for mutual TLS)
```

Brokers trust the **CA chain** (intermediate + root), so any broker or client
certificate issued by the intermediate is trusted. This mirrors the legacy
Root-CA → Intermediate-CA design, but generated in one pass with no manual
`scp` of CSRs between hosts.

## Stores: PKCS12 keystore, PEM trust material

Per broker, under `certs/generated/kafkaN/`:

| File | Contents | Used as | Mode |
|------|----------|---------|------|
| `kafka.server.keystore.p12` | broker private key + full cert chain | `ssl.keystore.location` | `0644` |
| `ca-chain.crt` | intermediate + root CA, PEM | `ssl.truststore.location` | `0644` |
| `kafkaN.key` | bare private key (not read by the broker) | — | `0600` |

Client trust material: `certs/generated/client/ca-chain.crt`.

The **keystore** is PKCS12: the modern Java default, interoperable with
OpenSSL, and buildable with **openssl alone** — no `keytool` (hence no Java)
required on the host.

The **truststore is PEM, not PKCS12**, and this is deliberate. A PKCS12 file
produced by `openssl pkcs12 -export -nokeys` contains plain certificate bags;
the JDK only treats PKCS12 entries as trust anchors when `keytool` marked them
as `trustedCertEntry`. Feeding such a file to Kafka fails at startup with:

```text
java.security.InvalidAlgorithmParameterException: the trustAnchors parameter must be non-empty
```

Kafka 2.7+ reads PEM trust material directly (KIP-651), so the brokers use
`ssl.truststore.type=PEM` pointing at `ca-chain.crt`. That keeps the tool-chain
openssl-only and needs no truststore password.

The stores are `0644` because the broker runs as an unprivileged non-root user
and bind-mounts `certs/generated/kafkaN` read-only; their contents are
protected by `KAFKA_SSL_PASSWORD`. Bare private keys stay `0600`.

## Why SANs are required

Kafka sets `ssl.endpoint.identification.algorithm=https`, so clients verify
that the hostname they connect to appears in the certificate's
**Subject Alternative Names**. The CN alone is ignored by modern TLS stacks.
Each broker certificate therefore carries:

| SAN | Why |
|-----|-----|
| `DNS:kafkaN` | in-network connections and inter-broker traffic use the container DNS name |
| `DNS:KAFKA000N.hq.corp` | parity with the legacy FQDN; works if you alias it |
| `DNS:localhost` | host-side clients connecting via `localhost:N9093` |
| `IP:127.0.0.1` | host-side clients that resolve to the loopback IP |

If a required SAN is missing the connection fails with
`No subject alternative names matching … found` — `scripts/validate-certs.sh`
checks for `DNS:kafkaN` (hard fail) and warns on the recommended extras.

## Client authentication

`SSL_CLIENT_AUTH` controls broker-side enforcement:

- `none` (default) — one-way TLS: the client verifies the broker; the broker
  does not require a client certificate.
- `required` — **mutual TLS**: clients must present a certificate signed by the
  trusted CA. `make certs` then also generates a client keystore and adds the
  `ssl.keystore.*` lines to the client config.
- `requested` — broker asks for a client cert but does not require it.

## Inter-broker protocol

Default `INTER_BROKER_LISTENER_NAME=SSL` ⇒ `inter.broker.listener.name=SSL`, so
replication and controller traffic between brokers is encrypted. In `plaintext`
mode this drops to PLAINTEXT automatically.

The protocol itself is resolved through `listener.security.protocol.map`;
`security.inter.broker.protocol` is deliberately **not** set, because Kafka
refuses to start when both it and `inter.broker.listener.name` are present.

## Validity & rotation

Lab certificates default to `CERT_VALIDITY_DAYS=3650` (10 years). To rotate,
delete `certs/generated/`, run `make certs`, then restart the brokers
(`make down && make up`) so the new stores are mounted.

## Production notes

This is a **lab** PKI. In production: use your enterprise CA via
`KAFKA_CERT_MODE=import`, store passwords in a secrets manager (not `.env`),
enable `SSL_CLIENT_AUTH=required` (mTLS), and layer SASL/authorization on top.
