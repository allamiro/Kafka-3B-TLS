# Air-Gapped (Offline) Build

The images build in two modes. The Dockerfiles use a **vendored tarball if it
exists**, otherwise they download from `downloads.apache.org`.

## Mode 1 — Internet build (default)

On a host with internet access:

```bash
make build
```

The Kafka and ZooKeeper Dockerfiles `curl` the release tarballs from Apache
using their build args (`KAFKA_DOWNLOAD_URL`, `ZOOKEEPER_DOWNLOAD_URL`).

## Mode 2 — Air-gapped build

### 1–3. Obtain and stage the tarballs

On a connected machine, download the **binary** distributions:

```bash
curl -fSL -o kafka_2.13-3.9.2.tgz \
  https://downloads.apache.org/kafka/3.9.2/kafka_2.13-3.9.2.tgz

curl -fSL -o apache-zookeeper-3.9.5-bin.tar.gz \
  https://downloads.apache.org/zookeeper/zookeeper-3.9.5/apache-zookeeper-3.9.5-bin.tar.gz
```

Copy both onto the air-gapped host and place them in `vendor/`:

```text
vendor/kafka_2.13-3.9.2.tgz
vendor/apache-zookeeper-3.9.5-bin.tar.gz
```

> ⚠️ **Use the `-bin` ZooKeeper tarball.** `apache-zookeeper-3.9.5.tar.gz`
> (without `-bin`) is the **source** distribution and has no runtime jars — the
> image will not run from it. The binary artifact is
> `apache-zookeeper-3.9.5-bin.tar.gz`.

### 4–5. Build

```bash
make build      # or: docker compose -f docker-compose.generated.yml build
```

The build context is the repo root, so `vendor/` is visible to both Dockerfiles.
Each Dockerfile copies `vendor/` in and prefers the local tarball:

```dockerfile
RUN if [ -f "/tmp/vendor/${KAFKA_TGZ}" ]; then \
        cp "/tmp/vendor/${KAFKA_TGZ}" "/tmp/${KAFKA_TGZ}"; \
    else \
        curl -fSL -o "/tmp/${KAFKA_TGZ}" "${KAFKA_DOWNLOAD_URL}"; \
    fi
```

## Convenience: `make vendor-sync`

If you already have the upstream distributions extracted under `packages/`
(as provided with this repo), copy the tarballs into `vendor/`:

```bash
make vendor-sync
```

This copies `packages/kafka_2.13-3.9.2.tgz` into `vendor/`. For ZooKeeper it
looks for `packages/apache-zookeeper-3.9.5-bin.tar.gz`; if only the **source**
tarball is present it prints a warning, because the source dist cannot run the
broker — fetch the `-bin` artifact as shown above.

## Notes

- `vendor/*.tgz` and `vendor/*.tar.gz` are git-ignored — large binaries are
  never committed.
- The base image `eclipse-temurin:17-jre` must also be available offline. Pre-pull
  it on a connected host (`docker pull eclipse-temurin:17-jre`) and
  `docker save`/`docker load` it onto the air-gapped host, or use a local registry.
