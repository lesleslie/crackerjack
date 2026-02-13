______________________________________________________________________

title: Message Queue Integration
owner: Backend Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6HDQR8TGXVN4PW2ZJKM9YH5
  category: development/data
  agents:
- data-engineer
- architecture-council
- redis-specialist
- python-pro
  tags:
- messaging
- kafka
- rabbitmq
- redis-streams
- pub-sub
- async

______________________________________________________________________

## Message Queue Integration

You are a message queue expert specializing in implementing reliable, scalable asynchronous messaging systems. Design comprehensive message queue solutions with proper patterns (pub/sub, work queues, request/reply), error handling, monitoring, and production-ready deployments for Kafka, RabbitMQ, and Redis Streams.

## Context

The user needs to implement a message queue system for asynchronous communication, event-driven architecture, or task processing. Focus on production-ready patterns with proper error handling, retry logic, dead letter queues, monitoring, and scalability.

## Requirements for: $ARGUMENTS

1. **Message Queue Selection**:

   - Apache Kafka for high-throughput event streaming
   - RabbitMQ for flexible routing and traditional messaging
   - Redis Streams for lightweight event streaming
   - Technology comparison and selection criteria

1. **Messaging Patterns**:

   - Pub/Sub (fan-out to multiple consumers)
   - Work Queues (task distribution)
   - Request/Reply (RPC-style)
   - Priority Queues
   - Competing Consumers

1. **Message Design**:

   - Schema evolution (Avro, Protobuf, JSON)
   - Message versioning
   - Idempotency keys
   - Metadata and headers

1. **Reliability**:

   - At-least-once delivery
   - Exactly-once semantics (Kafka)
   - Dead letter queues
   - Retry strategies with exponential backoff
   - Message persistence

1. **Performance**:

   - Batching strategies
   - Compression
   - Partitioning and sharding
   - Consumer group scaling
   - Backpressure handling

1. **Monitoring**:

   - Lag monitoring
   - Throughput metrics
   - Error rates
   - Consumer health

______________________________________________________________________

## Technology Comparison

### When to Use Each Technology

| Feature | Apache Kafka | RabbitMQ | Redis Streams |
|---------|--------------|----------|---------------|
| **Best For** | High-throughput event streaming | Complex routing, traditional messaging | Lightweight event streaming |
| **Throughput** | Very High (millions/sec) | High (tens of thousands/sec) | High (hundreds of thousands/sec) |
| **Persistence** | Excellent (log-based) | Good (disk-backed) | Good (AOF/RDB) |
| **Ordering** | Per-partition | Per-queue | Per-stream |
| **Replay** | Yes (retention-based) | Limited (requires plugins) | Yes (consumer groups) |
| **Complexity** | High | Medium | Low |
| **Message TTL** | Time or size-based | Yes | Yes |
| **Priority Queues** | No (use separate topics) | Yes | No (workaround with multiple streams) |
| **Message Routing** | Topic-based | Exchange types (direct, topic, fanout, headers) | Simple (streams) |

**Choose Kafka for:**

- Event sourcing and event-driven architecture
- High-throughput data pipelines
- Stream processing
- Log aggregation
- Metrics collection

**Choose RabbitMQ for:**

- Complex routing requirements
- Traditional message queuing
- Priority-based processing
- RPC-style request/reply patterns
- Delayed message delivery

**Choose Redis Streams for:**

- Lightweight event streaming
- Already using Redis for caching
- Simple pub/sub with consumer groups
- Real-time analytics
- Activity feeds

______________________________________________________________________

## Apache Kafka Implementation

### 1. Producer Implementation (Python)

```python
# kafka_producer.py
from confluent_kafka import Producer, KafkaException
from confluent_kafka.serialization import (
    StringSerializer,
    SerializationContext,
    MessageField,
)
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KafkaProducer:
    def __init__(self, bootstrap_servers, schema_registry_url=None):
        self.config = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "python-producer",
            "acks": "all",  # Wait for all replicas
            "retries": 3,
            "max.in.flight.requests.per.connection": 5,
            "enable.idempotence": True,  # Exactly-once semantics
            "compression.type": "snappy",
            "linger.ms": 10,  # Batch messages for 10ms
            "batch.size": 16384,
        }

        self.producer = Producer(self.config)

        # Schema Registry for Avro serialization (optional)
        if schema_registry_url:
            self.schema_registry = SchemaRegistryClient({"url": schema_registry_url})
            self.avro_serializer = self._setup_avro()

    def _setup_avro(self):
        user_schema = """
        {
            "type": "record",
            "name": "User",
            "namespace": "com.example",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string"},
                {"name": "created_at", "type": "long"}
            ]
        }
        """
        return AvroSerializer(self.schema_registry, user_schema)

    def delivery_callback(self, err, msg):
        """Callback for message delivery reports"""
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.info(
                f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
            )

    def produce(self, topic, key, value, headers=None):
        """
        Produce a message to Kafka

        Args:
            topic: Topic name
            key: Message key (for partitioning)
            value: Message value (dict)
            headers: Optional message headers
        """
        try:
            # Serialize value to JSON
            serialized_value = json.dumps(value).encode("utf-8")

            # Serialize key
            serialized_key = key.encode("utf-8") if key else None

            # Produce message
            self.producer.produce(
                topic=topic,
                key=serialized_key,
                value=serialized_value,
                headers=headers,
                on_delivery=self.delivery_callback,
            )

            # Trigger callbacks
            self.producer.poll(0)

        except BufferError:
            logger.error("Local queue is full, waiting...")
            self.producer.poll(1)  # Wait for space
            self.produce(topic, key, value, headers)  # Retry

        except KafkaException as e:
            logger.error(f"Kafka error: {e}")
            raise

    def flush(self):
        """Wait for all messages to be delivered"""
        remaining = self.producer.flush(timeout=30)
        if remaining > 0:
            logger.warning(f"{remaining} messages were not delivered")

    def close(self):
        """Close producer and wait for delivery"""
        self.flush()
        self.producer = None


# Example usage
if __name__ == "__main__":
    producer = KafkaProducer("localhost:9092")

    # Produce message with key (ensures same partition)
    user_event = {
        "id": "123",
        "name": "John Doe",
        "email": "john@example.com",
        "event_type": "user_created",
        "timestamp": 1704067200000,
    }

    producer.produce(
        topic="user-events",
        key="user-123",  # Same key goes to same partition
        value=user_event,
        headers=[("correlation_id", b"abc-123")],
    )

    # Produce multiple messages
    for i in range(100):
        producer.produce(
            topic="user-events",
            key=f"user-{i}",
            value={"id": str(i), "action": "login"},
        )

    producer.close()
```

### 2. Consumer Implementation (Python)

```python
# kafka_consumer.py
from confluent_kafka import Consumer, KafkaException, KafkaError
import json
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KafkaConsumer:
    def __init__(self, bootstrap_servers, group_id, topics):
        self.config = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",  # Start from beginning if no offset
            "enable.auto.commit": False,  # Manual commit for exactly-once
            "max.poll.interval.ms": 300000,  # 5 minutes
            "session.timeout.ms": 45000,
            "isolation.level": "read_committed",  # For exactly-once semantics
        }

        self.consumer = Consumer(self.config)
        self.consumer.subscribe(topics)
        self.running = True

    def process_message(self, msg):
        """
        Process a single message (override this method)

        Args:
            msg: Kafka message

        Returns:
            bool: True if processing succeeded
        """
        try:
            # Deserialize message
            value = json.loads(msg.value().decode("utf-8"))
            key = msg.key().decode("utf-8") if msg.key() else None

            logger.info(f"Processing message: key={key}, value={value}")

            # Your business logic here
            # Example: Save to database, call API, etc.

            return True

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False

    def consume(self, batch_size=1):
        """
        Consume messages from Kafka

        Args:
            batch_size: Number of messages to process before committing
        """
        messages_processed = 0

        try:
            while self.running:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.info(f"Reached end of partition {msg.partition()}")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue

                # Process message
                success = self.process_message(msg)

                if success:
                    messages_processed += 1

                    # Commit offset after batch
                    if messages_processed >= batch_size:
                        self.consumer.commit(asynchronous=False)
                        messages_processed = 0
                        logger.info("Committed offsets")
                else:
                    # Handle failure (send to DLQ, retry, etc.)
                    self.handle_failure(msg)

        except KeyboardInterrupt:
            logger.info("Shutting down consumer...")

        finally:
            self.close()

    def handle_failure(self, msg):
        """Handle message processing failure"""
        # Send to dead letter queue
        logger.error(f"Failed to process message, sending to DLQ: {msg.value()}")
        # TODO: Send to DLQ topic

    def close(self):
        """Close consumer"""
        self.running = False
        self.consumer.close()


# Example usage
if __name__ == "__main__":
    consumer = KafkaConsumer(
        bootstrap_servers="localhost:9092",
        group_id="user-event-processor",
        topics=["user-events"],
    )

    consumer.consume(batch_size=10)
```

### 3. Exactly-Once Semantics with Transactions

```python
# kafka_transactions.py
from confluent_kafka import Producer, Consumer


def transactional_processing():
    """
    Consume-Process-Produce pattern with exactly-once semantics
    """
    # Consumer config
    consumer = Consumer(
        {
            "bootstrap.servers": "localhost:9092",
            "group.id": "transaction-processor",
            "enable.auto.commit": False,
            "isolation.level": "read_committed",
        }
    )

    # Producer config with transactions
    producer = Producer(
        {
            "bootstrap.servers": "localhost:9092",
            "transactional.id": "my-transactional-id",
            "enable.idempotence": True,
        }
    )

    # Initialize transactions
    producer.init_transactions()

    consumer.subscribe(["input-topic"])

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                continue

            # Begin transaction
            producer.begin_transaction()

            try:
                # Process message
                processed_value = process_data(msg.value())

                # Produce to output topic
                producer.produce("output-topic", key=msg.key(), value=processed_value)

                # Send offsets to transaction (ensures exactly-once)
                producer.send_offsets_to_transaction(
                    consumer.position(consumer.assignment()),
                    consumer.consumer_group_metadata(),
                )

                # Commit transaction
                producer.commit_transaction()

            except Exception as e:
                # Abort transaction on error
                producer.abort_transaction()
                logger.error(f"Transaction aborted: {e}")

    finally:
        consumer.close()
        producer.flush()
```

______________________________________________________________________

## RabbitMQ Implementation

### 1. Publisher with Exchanges

```python
# rabbitmq_publisher.py
import pika
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    def __init__(self, host="localhost", port=5672, username="guest", password="guest"):
        credentials = pika.PlainCredentials(username, password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=host,
                port=port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
        )
        self.channel = self.connection.channel()

        # Declare exchanges
        self.setup_exchanges()

    def setup_exchanges(self):
        """Declare exchanges with different types"""

        # Direct exchange (point-to-point)
        self.channel.exchange_declare(
            exchange="user_direct", exchange_type="direct", durable=True
        )

        # Topic exchange (pattern matching)
        self.channel.exchange_declare(
            exchange="events", exchange_type="topic", durable=True
        )

        # Fanout exchange (broadcast)
        self.channel.exchange_declare(
            exchange="notifications", exchange_type="fanout", durable=True
        )

    def publish(self, exchange, routing_key, message, priority=0):
        """
        Publish a message to RabbitMQ

        Args:
            exchange: Exchange name
            routing_key: Routing key
            message: Message dict
            priority: Message priority (0-9)
        """
        try:
            # Serialize message
            body = json.dumps(message)

            # Publish with confirmation
            self.channel.confirm_delivery()

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent message
                    priority=priority,
                    content_type="application/json",
                    timestamp=int(datetime.utcnow().timestamp()),
                    headers={
                        "x-correlation-id": message.get("correlation_id"),
                    },
                ),
                mandatory=True,  # Return if no queue bound
            )

            logger.info(f"Published to {exchange}/{routing_key}")

        except pika.exceptions.UnroutableError:
            logger.error("Message was returned (no queue bound)")
        except Exception as e:
            logger.error(f"Failed to publish: {e}")

    def close(self):
        """Close connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()


# Example usage
if __name__ == "__main__":
    publisher = RabbitMQPublisher()

    # Publish to direct exchange
    publisher.publish(
        exchange="user_direct",
        routing_key="user.created",
        message={"user_id": "123", "email": "test@example.com"},
    )

    # Publish to topic exchange (pattern: "logs.level.source")
    publisher.publish(
        exchange="events",
        routing_key="logs.error.api",
        message={"message": "API error", "code": 500},
    )

    # Publish to fanout exchange (broadcast)
    publisher.publish(
        exchange="notifications",
        routing_key="",  # Ignored for fanout
        message={"type": "system_maintenance", "message": "Scheduled downtime"},
    )

    publisher.close()
```

### 2. Consumer with Dead Letter Queue

```python
# rabbitmq_consumer.py
import pika
import json
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    def __init__(self, host="localhost", port=5672, username="guest", password="guest"):
        credentials = pika.PlainCredentials(username, password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=host,
                port=port,
                credentials=credentials,
                heartbeat=600,
            )
        )
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=10)  # Process 10 at a time

    def setup_queue_with_dlq(self, queue_name, exchange, routing_key):
        """
        Setup queue with dead letter queue

        Args:
            queue_name: Main queue name
            exchange: Exchange to bind to
            routing_key: Routing key pattern
        """
        dlq_name = f"{queue_name}.dlq"
        dlx_name = f"{exchange}.dlx"

        # Declare dead letter exchange
        self.channel.exchange_declare(
            exchange=dlx_name, exchange_type="direct", durable=True
        )

        # Declare dead letter queue
        self.channel.queue_declare(
            queue=dlq_name,
            durable=True,
            arguments={
                "x-message-ttl": 86400000,  # 24 hours
            },
        )

        # Bind DLQ to DLX
        self.channel.queue_bind(
            queue=dlq_name, exchange=dlx_name, routing_key=queue_name
        )

        # Declare main queue with DLX
        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": dlx_name,
                "x-dead-letter-routing-key": queue_name,
                "x-max-priority": 10,  # Enable priority queue
            },
        )

        # Bind main queue to exchange
        self.channel.queue_bind(
            queue=queue_name, exchange=exchange, routing_key=routing_key
        )

        logger.info(f"Setup queue: {queue_name} with DLQ: {dlq_name}")

    def process_message(self, ch, method, properties, body):
        """
        Process a message

        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        try:
            # Deserialize message
            message = json.loads(body)
            logger.info(f"Processing message: {message}")

            # Your business logic here
            # Simulate processing
            if message.get("user_id") == "error":
                raise ValueError("Simulated error")

            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            # Reject and send to DLQ (requeue=False)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except Exception as e:
            logger.error(f"Processing error: {e}")
            # Reject and requeue (retry)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def consume(self, queue_name):
        """
        Start consuming messages

        Args:
            queue_name: Queue to consume from
        """
        logger.info(f"Starting consumer for queue: {queue_name}")

        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=self.process_message,
            auto_ack=False,  # Manual acknowledgment
        )

        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            self.channel.stop_consuming()
        finally:
            self.close()

    def close(self):
        """Close connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()


# Example usage
if __name__ == "__main__":
    consumer = RabbitMQConsumer()

    # Setup queue with DLQ
    consumer.setup_queue_with_dlq(
        queue_name="user_events", exchange="user_direct", routing_key="user.*"
    )

    # Start consuming
    consumer.consume("user_events")
```

______________________________________________________________________

## Redis Streams Implementation

### 1. Producer with Redis Streams

```python
# redis_producer.py
import redis
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedisStreamProducer:
    def __init__(self, host="localhost", port=6379, db=0):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    def produce(self, stream_name, data, max_len=10000):
        """
        Produce a message to Redis Stream

        Args:
            stream_name: Stream name
            data: Message data (dict)
            max_len: Maximum stream length (FIFO eviction)

        Returns:
            str: Message ID
        """
        try:
            # Add timestamp
            data["timestamp"] = datetime.utcnow().isoformat()

            # Serialize complex values
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    data[key] = json.dumps(value)

            # Add to stream with auto-generated ID
            message_id = self.redis.xadd(
                stream_name,
                data,
                maxlen=max_len,
                approximate=True,  # Faster eviction
            )

            logger.info(f"Produced message {message_id} to {stream_name}")
            return message_id

        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
            raise

    def get_stream_info(self, stream_name):
        """Get stream information"""
        info = self.redis.xinfo_stream(stream_name)
        return {
            "length": info["length"],
            "first_entry": info["first-entry"],
            "last_entry": info["last-entry"],
            "groups": info["groups"],
        }


# Example usage
if __name__ == "__main__":
    producer = RedisStreamProducer()

    # Produce messages
    for i in range(10):
        message_id = producer.produce(
            stream_name="user_events",
            data={
                "user_id": f"user_{i}",
                "action": "login",
                "metadata": {"ip": "192.168.1.1"},
            },
        )
        logger.info(f"Message ID: {message_id}")

    # Get stream info
    info = producer.get_stream_info("user_events")
    logger.info(f"Stream info: {info}")
```

### 2. Consumer Group Implementation

```python
# redis_consumer.py
import redis
import json
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedisStreamConsumer:
    def __init__(self, host="localhost", port=6379, db=0):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.running = True

    def create_consumer_group(self, stream_name, group_name, start_id="0"):
        """
        Create a consumer group

        Args:
            stream_name: Stream name
            group_name: Consumer group name
            start_id: Starting message ID ('0' for all, '>' for new only)
        """
        try:
            self.redis.xgroup_create(
                stream_name, group_name, id=start_id, mkstream=True
            )
            logger.info(f"Created consumer group: {group_name}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group already exists: {group_name}")
            else:
                raise

    def consume(self, stream_name, group_name, consumer_name, batch_size=10):
        """
        Consume messages from Redis Stream

        Args:
            stream_name: Stream name
            group_name: Consumer group name
            consumer_name: This consumer's name
            batch_size: Messages per batch
        """
        logger.info(f"Starting consumer: {consumer_name} in group: {group_name}")

        try:
            while self.running:
                # Read new messages
                messages = self.redis.xreadgroup(
                    groupname=group_name,
                    consumername=consumer_name,
                    streams={stream_name: ">"},
                    count=batch_size,
                    block=1000,  # Block for 1 second
                )

                if messages:
                    for stream, stream_messages in messages:
                        for message_id, data in stream_messages:
                            self.process_message(
                                stream_name, group_name, message_id, data
                            )

                # Process pending messages (from failed consumers)
                self.process_pending(stream_name, group_name, consumer_name)

        except KeyboardInterrupt:
            logger.info("Shutting down consumer...")
        finally:
            self.running = False

    def process_message(self, stream_name, group_name, message_id, data):
        """
        Process a single message

        Args:
            stream_name: Stream name
            group_name: Consumer group name
            message_id: Message ID
            data: Message data
        """
        try:
            # Deserialize complex fields
            for key, value in data.items():
                try:
                    data[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass

            logger.info(f"Processing message {message_id}: {data}")

            # Your business logic here
            time.sleep(0.1)  # Simulate processing

            # Acknowledge message
            self.redis.xack(stream_name, group_name, message_id)
            logger.info(f"Acknowledged message {message_id}")

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            # Message remains in pending list for retry

    def process_pending(self, stream_name, group_name, consumer_name, idle_time=60000):
        """
        Process pending messages (failed/stale)

        Args:
            stream_name: Stream name
            group_name: Consumer group name
            consumer_name: This consumer's name
            idle_time: Idle time in milliseconds (60 seconds)
        """
        # Get pending messages
        pending = self.redis.xpending_range(
            stream_name,
            group_name,
            min="-",
            max="+",
            count=10,
            consumername=consumer_name,
        )

        for msg in pending:
            message_id = msg["message_id"]

            # Claim message if idle too long
            if msg["time_since_delivered"] > idle_time:
                claimed = self.redis.xclaim(
                    stream_name,
                    group_name,
                    consumer_name,
                    min_idle_time=idle_time,
                    message_ids=[message_id],
                )

                for message_id, data in claimed:
                    logger.info(f"Claimed pending message: {message_id}")
                    self.process_message(stream_name, group_name, message_id, data)

    def get_pending_count(self, stream_name, group_name):
        """Get number of pending messages"""
        pending = self.redis.xpending(stream_name, group_name)
        return pending["pending"]


# Example usage
if __name__ == "__main__":
    consumer = RedisStreamConsumer()

    # Create consumer group
    consumer.create_consumer_group(
        stream_name="user_events",
        group_name="event_processors",
        start_id="0",  # Process all messages
    )

    # Start consuming
    consumer.consume(
        stream_name="user_events",
        group_name="event_processors",
        consumer_name="consumer_1",
        batch_size=10,
    )
```

______________________________________________________________________

## Security Considerations

### Message Encryption

```python
# message_encryption.py
from cryptography.fernet import Fernet
import json


class SecureMessageHandler:
    def __init__(self, encryption_key=None):
        if encryption_key is None:
            encryption_key = Fernet.generate_key()
        self.cipher = Fernet(encryption_key)

    def encrypt_message(self, data):
        """Encrypt message data"""
        json_data = json.dumps(data)
        encrypted = self.cipher.encrypt(json_data.encode())
        return encrypted

    def decrypt_message(self, encrypted_data):
        """Decrypt message data"""
        decrypted = self.cipher.decrypt(encrypted_data)
        return json.loads(decrypted.decode())


# Example usage
handler = SecureMessageHandler()

# Encrypt before sending
data = {"user_id": "123", "password": "secret"}
encrypted = handler.encrypt_message(data)

# Send encrypted to queue
# ...

# Decrypt after receiving
decrypted = handler.decrypt_message(encrypted)
```

### Authentication & Authorization

**Kafka SASL/SCRAM Authentication**:

```python
kafka_config = {
    "bootstrap.servers": "localhost:9092",
    "security.protocol": "SASL_SSL",
    "sasl.mechanism": "SCRAM-SHA-512",
    "sasl.username": "your_username",
    "sasl.password": "your_password",
    "ssl.ca.location": "/path/to/ca-cert",
}
```

**RabbitMQ TLS**:

```python
import ssl

context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.verify_mode = ssl.CERT_REQUIRED
context.load_verify_locations("/path/to/ca.pem")

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host="localhost",
        port=5671,
        credentials=pika.PlainCredentials("username", "password"),
        ssl_options=pika.SSLOptions(context),
    )
)
```

### Security Checklist

- [ ] TLS/SSL enabled for all connections
- [ ] Authentication configured (SASL for Kafka, credentials for RabbitMQ/Redis)
- [ ] Sensitive data encrypted before publishing
- [ ] Access control lists (ACLs) configured
- [ ] Message payload validation implemented
- [ ] No credentials in code (use environment variables)
- [ ] Network isolation (VPC, private subnets)
- [ ] Regular security audits
- [ ] Monitoring for suspicious activity

______________________________________________________________________

## Testing & Validation

### Unit Testing

```python
# test_kafka_producer.py
import unittest
from unittest.mock import Mock, patch
from kafka_producer import KafkaProducer


class TestKafkaProducer(unittest.TestCase):
    @patch("kafka_producer.Producer")
    def test_produce_success(self, mock_producer_class):
        # Setup mock
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer

        # Create producer
        producer = KafkaProducer("localhost:9092")

        # Produce message
        producer.produce("test-topic", "key1", {"data": "value"})

        # Assert
        mock_producer.produce.assert_called_once()
        call_args = mock_producer.produce.call_args
        self.assertEqual(call_args.kwargs["topic"], "test-topic")

    @patch("kafka_producer.Producer")
    def test_produce_with_retry_on_buffer_error(self, mock_producer_class):
        # Setup mock to raise BufferError then succeed
        mock_producer = Mock()
        mock_producer.produce.side_effect = [BufferError(), None]
        mock_producer_class.return_value = mock_producer

        producer = KafkaProducer("localhost:9092")
        producer.produce("test-topic", "key1", {"data": "value"})

        # Assert retried
        self.assertEqual(mock_producer.produce.call_count, 2)


if __name__ == "__main__":
    unittest.main()
```

### Integration Testing

```python
# test_kafka_integration.py
import unittest
import time
from kafka_producer import KafkaProducer
from kafka_consumer import KafkaConsumer


class TestKafkaIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_topic = "integration-test"
        cls.producer = KafkaProducer("localhost:9092")

    @classmethod
    def tearDownClass(cls):
        cls.producer.close()

    def test_produce_and_consume(self):
        # Produce message
        test_message = {"test": "data", "timestamp": int(time.time())}
        self.producer.produce(self.test_topic, "test-key", test_message)
        self.producer.flush()

        # Consume message
        consumer = KafkaConsumer("localhost:9092", "test-group", [self.test_topic])

        # Poll for message
        msg = consumer.consumer.poll(timeout=5.0)
        self.assertIsNotNone(msg)

        consumer.close()
```

### Testing Checklist

- [ ] Producer can send messages successfully
- [ ] Consumer can receive and process messages
- [ ] Message serialization/deserialization works
- [ ] Dead letter queue receives failed messages
- [ ] Consumer group rebalancing works
- [ ] At-least-once delivery guaranteed
- [ ] Exactly-once semantics verified (Kafka)
- [ ] Retry logic with exponential backoff tested
- [ ] Load testing completed (>10k messages/sec)
- [ ] Monitoring and alerting verified

______________________________________________________________________

## Troubleshooting

### Common Issues

#### Issue: Consumer Lag Increasing

**Symptoms:**

- Consumer lag continuously growing
- Messages piling up in queue
- Consumers can't keep up with producers

**Causes:**

- Consumer processing too slow
- Insufficient consumer instances
- Database bottleneck
- Network issues

**Solutions:**

1. **Scale consumers horizontally**:

```python
# Add more consumers to the group
# Kafka automatically rebalances partitions
for i in range(5):
    consumer = KafkaConsumer("localhost:9092", "group-id", ["topic"])
    # Run in separate process/thread
```

2. **Optimize processing**:

```python
# Batch database writes
def process_batch(messages):
    values = [extract_data(msg) for msg in messages]
    db.bulk_insert(values)  # Single query instead of N queries
```

3. **Monitor lag**:

```bash
# Kafka: Check consumer lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
    --group my-group --describe
```

**Prevention:**

- Monitor lag metrics
- Set up alerts for lag > threshold
- Auto-scale consumers based on lag

______________________________________________________________________

#### Issue: Messages Going to Dead Letter Queue

**Symptoms:**

- High DLQ message count
- Messages repeatedly failing
- Processing errors in logs

**Causes:**

- Validation errors
- External service failures
- Data format issues
- Business logic bugs

**Solutions:**

1. **Investigate DLQ messages**:

```python
# RabbitMQ: Consume from DLQ
def inspect_dlq():
    channel.basic_consume(
        queue="my_queue.dlq",
        on_message_callback=lambda ch, method, props, body: print(
            f"DLQ message: {body}"
        ),
        auto_ack=True,
    )
```

2. **Add retry with backoff**:

```python
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def process_with_retry(message):
    # Processing logic
    pass
```

3. **Validate before processing**:

```python
from pydantic import BaseModel, ValidationError


class UserEvent(BaseModel):
    user_id: str
    action: str
    timestamp: int


def process_message(msg):
    try:
        event = UserEvent(**json.loads(msg.value()))
        # Process valid event
    except ValidationError as e:
        logger.error(f"Invalid message: {e}")
        # Send to DLQ immediately (don't retry)
```

______________________________________________________________________

#### Issue: Duplicate Message Processing

**Symptoms:**

- Same message processed multiple times
- Duplicate database entries
- Idempotency issues

**Causes:**

- Consumer crashes before committing offset
- Network issues causing redelivery
- No idempotency key

**Solutions:**

1. **Implement idempotency**:

```python
def process_idempotent(message):
    idempotency_key = message.get("idempotency_key")

    # Check if already processed
    if db.exists("processed_messages", idempotency_key):
        logger.info(f"Skipping duplicate: {idempotency_key}")
        return

    # Process message
    result = process_message(message)

    # Mark as processed
    db.insert(
        "processed_messages",
        {"key": idempotency_key, "processed_at": datetime.utcnow()},
    )
```

2. **Use exactly-once semantics** (Kafka):

```python
# Enable exactly-once with transactions
producer_config = {
    "enable.idempotence": True,
    "transactional.id": "my-app",
}
```

3. **Database constraints**:

```sql
-- Prevent duplicates at database level
CREATE UNIQUE INDEX idx_idempotency_key ON orders(idempotency_key);
```

______________________________________________________________________

### Getting Help

**Check Logs:**

- Producer logs for send failures
- Consumer logs for processing errors
- Broker logs for server issues

**Related Tools:**

- Use `distributed-tracing-setup.md` for end-to-end tracing
- Use `observability-incident-lead` agent for metrics setup
- Use `data-engineer` agent for pipeline optimization

**Agents to Consult:**

- `data-engineer` - Pipeline architecture
- `architecture-council` - System design
- `redis-specialist` - Redis Streams optimization
- `observability-incident-lead` - Throughput optimization

______________________________________________________________________

## Best Practices

1. **Idempotency**: Always include idempotency keys in messages
1. **Dead Letter Queues**: Implement DLQs for all critical queues
1. **Monitoring**: Track lag, throughput, error rates
1. **Batching**: Process messages in batches for efficiency
1. **Backpressure**: Implement backpressure handling to prevent overload
1. **Schema Evolution**: Use schema registry (Avro/Protobuf) for compatibility
1. **Retention**: Configure appropriate message retention policies
1. **Partitioning**: Use message keys for consistent partitioning (Kafka)
1. **Consumer Groups**: Scale with multiple consumers in same group
1. **Testing**: Test failure scenarios (broker down, network issues, etc.)

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `data-engineer` - Message queue architecture and data pipelines
- `architecture-council` - System design and patterns
- `redis-specialist` - Redis Streams optimization

**Supporting Specialists**:

- `python-pro` - Python implementation
- `observability-incident-lead` - Throughput optimization
- `database-operations-specialist` - Database integration

**Quality & Operations**:

- `qa-strategist` - Testing strategies
- `observability-incident-lead` - Metrics and alerting
- `observability-incident-lead` - Distributed tracing
