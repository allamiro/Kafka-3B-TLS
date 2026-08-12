# vendor/ — Air-Gapped Build Tarballs

This directory holds Apache release tarballs for **air-gapped / offline image
builds**. When these files are present, the Dockerfiles use them instead of
downloading from `downloads.apache.org`.

## Expected files

```text
vendor/kafka_2.13-3.9.2.tgz
vendor/apache-zookeeper-3.9.5-bin.tar.gz
```

## How to populate (from a machine with internet access)

```bash
curl -fSL -o vendor/kafka_2.13-3.9.2.tgz \
  https://downloads.apache.org/kafka/3.9.2/kafka_2.13-3.9.2.tgz

curl -fSL -o vendor/apache-zookeeper-3.9.5-bin.tar.gz \
  https://downloads.apache.org/zookeeper/zookeeper-3.9.5/apache-zookeeper-3.9.5-bin.tar.gz
```

Copy them onto the air-gapped host, then run `make build`.

The Dockerfiles fall back to downloading from Apache when these files are
absent (Internet build mode). See [docs/airgapped-build.md](../docs/airgapped-build.md).

> The `*.tgz` / `*.tar.gz` files are git-ignored. Only this README and
> `.gitkeep` are committed.
