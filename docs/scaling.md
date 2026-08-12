# Scaling

The cluster size is driven entirely by `scripts/render-compose.py`, which
assigns unique broker IDs, hostnames, volumes, advertised listeners, host
ports, and certificate mounts. Never use `docker compose up --scale kafka=N` —
that would clone identical broker IDs and listeners.

## Run N brokers

```bash
make certs   BROKERS=5            # generate certs for kafka1..kafka5
make render  BROKERS=5 ZOOKEEPERS=3
make up
```

Or call the generator directly:

```bash
./scripts/render-compose.py --brokers 3  --zookeepers 3 -o docker-compose.generated.yml
./scripts/render-compose.py --brokers 5  --zookeepers 3 -o docker-compose.generated.yml
./scripts/render-compose.py --brokers 7  --zookeepers 3 -o docker-compose.generated.yml
./scripts/render-compose.py --brokers 10 --zookeepers 5 -o docker-compose.generated.yml
```

## Rules (enforced by the generator and `validate-env.sh`)

| Rule | Reason |
|------|--------|
| Brokers ≥ 3 | minimum for RF=3 with `min.insync.replicas=2` |
| ZooKeeper ∈ {3, 5} | quorum needs an **odd** count; 3 or 5 is enough for any lab |
| Default ZooKeeper = 3 | tolerates 1 node failure |
| RF ≤ broker count | a topic cannot have more replicas than brokers |

Invalid inputs fail loudly:

```bash
./scripts/render-compose.py --brokers 2 --zookeepers 3   # error: brokers must be >= 3
./scripts/render-compose.py --brokers 3 --zookeepers 2   # error: zookeepers must be 3 or 5
./scripts/render-compose.py --brokers 3 --zookeepers 4   # error: zookeepers must be 3 or 5
```

## Why ZooKeeper does NOT scale 1:1 with brokers

ZooKeeper is a **metadata quorum**, not a data plane. Its job (broker
registration, controller election, config/ACL storage) does not get heavier as
you add Kafka brokers. A 3-node ensemble comfortably serves dozens of brokers.

- **Correct:** 7 Kafka brokers + 3 ZooKeeper nodes
- **Incorrect:** 7 Kafka brokers + 7 ZooKeeper nodes

More ZooKeeper nodes mean **slower writes** (every write must be acknowledged by
a majority) and more election overhead — without improving Kafka throughput.

### When 5 ZooKeeper nodes make sense

Use 5 only when you need to tolerate **2 simultaneous ZooKeeper failures**
(5-node quorum survives 2 down; 3-node survives 1). That is rare in a lab and
usually only justified for large or highly-available production ensembles.

| Ensemble size | Majority | Failures tolerated |
|---------------|----------|--------------------|
| 3 | 2 | 1 |
| 5 | 3 | 2 |

## Replication factor

`DEFAULT_REPLICATION_FACTOR=3` stays at 3 even as you add brokers — three copies
is the standard durability target. Internal topics
(`__consumer_offsets`, transaction state log) are also RF=3 with
`min.insync.replicas=2`.

To change RF safely:

1. Edit `DEFAULT_REPLICATION_FACTOR` (and the `OFFSETS_*` / `TRANSACTION_*`
   factors) in `.env` **before first start**, ensuring `RF ≤ BROKER_COUNT`.
2. For **existing** topics, do not just change the default — reassign partitions
   with `kafka-reassign-partitions.sh`. Raising RF on a live topic requires an
   explicit reassignment plan; it is not retroactive.

## Host ports beyond broker 9

Host port = `<index><suffix>` (e.g. broker 7 → 79092 / 79093). Brokers with
index > 9 would exceed 65535, so the generator does **not** publish host ports
for them — they remain reachable inside `kafka-net` (and via any broker as a
bootstrap, since clients discover the full cluster from metadata).
