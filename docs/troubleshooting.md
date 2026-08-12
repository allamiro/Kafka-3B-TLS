# Troubleshooting

Use `make ps`, `make logs SVC=kafka1`, and `make logs SVC=zookeeper1` first.

## ZooKeeper does not return `imok`
- **Check:** `docker compose exec zookeeper1 bash -c 'echo ruok | nc -w 2 localhost 2181'`
- Quorum not formed yet — wait ~20s after start; a 3-node ensemble needs a
  majority up before it answers. Confirm all `myid` files differ
  (`ZOO_MY_ID` is unique per service).
- `4lw.commands.whitelist` must include `ruok` (it does, in `zoo.cfg.tpl`).

## Kafka cannot connect to ZooKeeper
- Logs show `Timed out waiting for connection to Zookeeper`.
- Verify `KAFKA_ZOOKEEPER_CONNECT=zookeeper1:2181,zookeeper2:2181,zookeeper3:2181`
  matches the ZooKeeper service names and that those containers are healthy
  (`make ps`). Brokers only start after ZK is `service_healthy`.

## Broker ID conflict
- `kafka.common.InconsistentClusterIdException` or duplicate `broker.id`.
- Each service must have a unique `BROKER_ID`. If you reused a data volume from
  a different cluster, clear it: `make clean` (removes volumes) then `make up`.

## Topic replication factor too high
- `Replication factor: 3 larger than available brokers: N`.
- You asked for more replicas than brokers. Lower RF or add brokers; keep
  `RF ≤ BROKER_COUNT`. See [scaling.md](scaling.md).

## SSL handshake failure
- `SSLHandshakeException` / `unable to find valid certification path`.
- The client does not trust the broker's CA. Regenerate the material
  (`make certs`) and point the client at the matching
  `certs/generated/client/ca-chain.crt` (`ssl.truststore.type=PEM`).
- Confirm the broker is actually listening on SSL (`KAFKA_SECURITY_MODE=ssl|dual`).

## Hostname verification failure
- `No subject alternative names matching IP address / DNS name found`.
- You connected via a name not in the cert SANs. Connect via `kafka1` (in-network)
  or `localhost` (host). Inspect SANs:
  `openssl x509 -in certs/generated/kafka1/kafka1.crt -noout -ext subjectAltName`.

## Wrong SANs
- Run `./scripts/validate-certs.sh`. It hard-fails if `DNS:kafkaN` is missing and
  warns on the recommended extras. Regenerate with `make certs` after fixing
  `KAFKA_DOMAIN` / SAN template in `certs/openssl/broker-san.cnf.tpl`.

## Keystore password mismatch
- `keystore password was incorrect`.
- `KAFKA_SSL_PASSWORD` in `.env` must match the password used when the stores
  were generated. If you changed it, regenerate: `make clean --certs` then `make certs`.

## trustAnchors parameter must be non-empty
- `InvalidAlgorithmParameterException: the trustAnchors parameter must be non-empty`.
- The truststore holds no entry the JDK recognises as a trust anchor — this is
  what happens with a PKCS12 built by `openssl -nokeys`. The lab therefore uses
  PEM trust material: `ssl.truststore.type=PEM` with `ca-chain.crt`, and no
  truststore password. Check that `certs/generated/kafkaN/ca-chain.crt` exists
  and is non-empty; regenerate with `make certs`.

## Permission denied reading /etc/kafka/secrets
- The broker container runs as an unprivileged user and mounts the certificate
  directory read-only, so the directory needs `0755` and the keystore `0644`.
  `make certs` sets these; if you copied material in by hand, fix the modes.

## Port already in use
- `Bind for 0.0.0.0:19092 failed: port is already allocated`.
- Another process (or a previous run) holds the host port. Stop it, or change
  the published ports by re-rendering with fewer brokers, or `make down` the old stack.

## Generated Compose file invalid
- `docker compose -f docker-compose.generated.yml config` reports an error.
- Re-render: `make render`. Do not hand-edit the generated file. Ensure your
  `.env` values are valid (`./scripts/validate-env.sh`).

## Docker volume stale data
- Old topics/offsets reappear, or cluster ID mismatches after re-creating.
- Named volumes persist across `down`. To start fresh: `make clean` (adds `-v`),
  or `./scripts/clean.sh --all` to also drop certs and the generated compose file.

## SSL material is missing
- `make up` prints `SSL material is missing. Run: make certs`.
- In `ssl`/`dual` mode the broker entrypoint refuses to start without
  `certs/generated/kafkaN/kafka.server.keystore.p12`. Run `make certs`.

## Air-gapped build can't find ZooKeeper
- Build fails downloading ZooKeeper, or the container exits immediately.
- Ensure `vendor/apache-zookeeper-3.9.5-bin.tar.gz` (the **-bin** artifact) is
  present. The source tarball will not run. See [airgapped-build.md](airgapped-build.md).
