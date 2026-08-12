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

## Stores (PKCS12, not JKS)

Per broker, under `certs/generated/kafkaN/`:

| File | Contents | Used as |
|------|----------|---------|
| `kafka.server.keystore.p12` | broker private key + full cert chain | `ssl.keystore.location` |
| `kafka.server.truststore.p12` | CA chain only (no key) | `ssl.truststore.location` |

Client truststore: `certs/generated/client/kafka.client.truststore.p12`.

PKCS12 is preferred over JKS: it is the modern Java default, interoperable with
OpenSSL, and lets us build every store with **openssl alone** — no `keytool`
(hence no Java) required on the host. Java 17 reads certificate-only PKCS12
entries as trusted entries, so the truststores work without modification.

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

Default `INTER_BROKER_LISTENER_NAME=SSL` ⇒ `security.inter.broker.protocol=SSL`,
so replication and controller traffic between brokers is encrypted. In
`plaintext` mode this drops to PLAINTEXT automatically.

## Validity & rotation

Lab certificates default to `CERT_VALIDITY_DAYS=3650` (10 years). To rotate,
delete `certs/generated/`, run `make certs`, then restart the brokers
(`make down && make up`) so the new stores are mounted.

## Production notes

This is a **lab** PKI. In production: use your enterprise CA via
`KAFKA_CERT_MODE=import`, store passwords in a secrets manager (not `.env`),
enable `SSL_CLIENT_AUTH=required` (mTLS), and layer SASL/authorization on top.
