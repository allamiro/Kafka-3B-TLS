###############################################################################
# Kafka broker ${BROKER_ID} — rendered by entrypoint.sh from this template.
# ZooKeeper mode (Kafka 3.9.2). Listener/SSL lines are injected by the
# entrypoint based on KAFKA_SECURITY_MODE.
###############################################################################
broker.id=${BROKER_ID}

zookeeper.connect=${KAFKA_ZOOKEEPER_CONNECT}
zookeeper.connection.timeout.ms=18000

############################# Listeners (mode-driven) #########################
listeners=${KAFKA_LISTENERS}
advertised.listeners=${KAFKA_ADVERTISED_LISTENERS}
listener.security.protocol.map=${KAFKA_LISTENER_SECURITY_PROTOCOL_MAP}
# Kafka rejects a config that sets both inter.broker.listener.name and
# security.inter.broker.protocol. The listener name is the right one here: the
# protocol is resolved through listener.security.protocol.map above.
inter.broker.listener.name=${KAFKA_INTER_BROKER_LISTENER_NAME}

############################# Threads / sockets ##############################
num.network.threads=6
num.io.threads=10
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

############################# Log basics #####################################
log.dirs=/var/lib/kafka/data
num.partitions=${NUM_PARTITIONS}
default.replication.factor=${DEFAULT_REPLICATION_FACTOR}
min.insync.replicas=${MIN_INSYNC_REPLICAS}

offsets.topic.replication.factor=${OFFSETS_TOPIC_REPLICATION_FACTOR}
transaction.state.log.replication.factor=${TRANSACTION_STATE_LOG_REPLICATION_FACTOR}
transaction.state.log.min.isr=${TRANSACTION_STATE_LOG_MIN_ISR}

############################# Retention ######################################
log.retention.hours=${LOG_RETENTION_HOURS}
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000
log.cleanup.policy=delete

############################# Topic management ###############################
auto.create.topics.enable=${AUTO_CREATE_TOPICS_ENABLE}
delete.topic.enable=${DELETE_TOPIC_ENABLE}
auto.leader.rebalance.enable=true

############################# Message sizing #################################
compression.type=producer
message.max.bytes=15728640
replica.fetch.max.bytes=15728640
fetch.max.bytes=15728640

group.initial.rebalance.delay.ms=3000
