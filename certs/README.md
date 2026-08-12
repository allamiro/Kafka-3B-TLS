# certs/

PKI material for the lab. **Nothing secret is committed** — `certs/generated/`
is git-ignored except for `.gitkeep`.

```text
certs/
├── openssl/                 # OpenSSL configs (committed)
│   ├── root-ca.cnf          # Root CA (self-signed) extensions
│   ├── intermediate-ca.cnf  # Intermediate CA extensions
│   └── broker-san.cnf.tpl   # per-broker cert template (SANs via envsubst)
└── generated/               # OUTPUT — git-ignored
    ├── ca/                  # root-ca, intermediate-ca, chain.crt
    ├── kafka1/ … kafkaN/    # key, csr, crt, chain, keystore.p12, truststore.p12
    └── client/              # client truststore (+ keystore for mTLS), client-ssl.properties
```

## Generate (lab CA)

```bash
make certs                    # uses KAFKA_CERT_MODE from .env (default: generate)
# or
BROKER_COUNT=5 ./scripts/generate-certs.sh
```

Produces, per broker `kafkaN/`:

```text
kafkaN.key  kafkaN.csr  kafkaN.crt  kafkaN.chain.crt
kafka.server.keystore.p12   kafka.server.truststore.p12
```

## Import (enterprise PKI)

Set `KAFKA_CERT_MODE=import` and the `EXTERNAL_*` paths in `.env`, then
`make certs`. The script validates cert/key matching, required SANs, and the
chain, then builds the same PKCS12 stores. See
[../docs/ssl-design.md](../docs/ssl-design.md).

## Tooling

Generation/import is **openssl-only** — no Java `keytool` is required on the
host. PKCS12 stores are read natively by Kafka on Java 17.

## Validate

```bash
./scripts/validate-certs.sh
```

Checks every broker: cert/key modulus match, required `DNS:kafkaN` SAN, and
chain validity against `certs/generated/ca/chain.crt`.
