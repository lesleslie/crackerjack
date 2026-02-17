______________________________________________________________________

title: Data Pipeline
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXC5G16B82V03H85FC5HG
  category: development/data

______________________________________________________________________

## Data Pipeline Architecture

Design and implement a scalable data pipeline for: $ARGUMENTS

Create a production-ready data pipeline including:

1. **Data Ingestion**:

   - Multiple source connectors (APIs, databases, files, streams)
   - Schema evolution handling
   - Incremental/batch loading
   - Data quality checks at ingestion
   - Dead letter queue for failures

1. **Transformation Layer**:

   - ETL/ELT architecture decision
   - Apache Beam/Spark transformations
   - Data cleansing and normalization
   - Feature engineering pipeline
   - Business logic implementation

1. **Orchestration**:

   - Airflow/Prefect DAGs
   - Dependency management
   - Retry and failure handling
   - SLA monitoring
   - Dynamic pipeline generation

1. **Storage Strategy**:

   - Data lake architecture
   - Partitioning strategy
   - Compression choices
   - Retention policies
   - Hot/cold storage tiers

1. **Streaming Pipeline**:

   - Kafka/Kinesis integration
   - Real-time processing
   - Windowing strategies
   - Late data handling
   - Exactly-once semantics

1. **Data Quality**:

   - Automated testing
   - Data profiling
   - Anomaly detection
   - Lineage tracking
   - Quality metrics and dashboards

1. **Performance & Scale**:

   - Horizontal scaling
   - Resource optimization
   - Caching strategies
   - Query optimization
   - Cost management

Include monitoring, alerting, and data governance considerations. Make it cloud-agnostic with specific implementation examples for AWS/GCP/Azure.

______________________________________________________________________

## Implementation Patterns

### 1. Async ETL Pipeline with Python

```python
import asyncio
import asyncpg
import structlog
from dataclasses import dataclass
from typing import AsyncIterator, Any
from datetime import datetime

logger = structlog.get_logger()


@dataclass
class PipelineConfig:
    """Pipeline configuration"""

    source_connection: str
    dest_connection: str
    batch_size: int = 1000
    max_workers: int = 4
    retry_limit: int = 3


class AsyncETLPipeline:
    """Production-ready async ETL pipeline"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.db_pool = None
        self.metrics = {"extracted": 0, "transformed": 0, "loaded": 0, "failed": 0}

    async def __aenter__(self):
        """Async context manager entry"""
        self.db_pool = await asyncpg.create_pool(
            self.config.source_connection,
            min_size=2,
            max_size=self.config.max_workers,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.db_pool:
            await self.db_pool.close()

    async def extract(self, query: str) -> AsyncIterator[list[dict]]:
        """Extract data in batches from source"""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                cursor = await conn.cursor(query)
                while True:
                    batch = await cursor.fetch(self.config.batch_size)
                    if not batch:
                        break

                    records = [dict(row) for row in batch]
                    self.metrics["extracted"] += len(records)
                    logger.info("extracted_batch", count=len(records))
                    yield records

    async def transform(self, records: list[dict]) -> list[dict]:
        """Transform records with business logic"""
        transformed = []

        for record in records:
            try:
                # Example transformations
                transformed_record = {
                    "id": record["id"],
                    "name": record["name"].strip().title(),
                    "email": record["email"].lower(),
                    "created_at": datetime.fromisoformat(record["created_at"]),
                    # Add computed fields
                    "full_name": f"{record['first_name']} {record['last_name']}",
                    "email_domain": record["email"].split("@")[1],
                    # Enrichment
                    "processed_at": datetime.utcnow(),
                }
                transformed.append(transformed_record)
                self.metrics["transformed"] += 1

            except Exception as e:
                logger.error(
                    "transform_failed", record_id=record.get("id"), error=str(e)
                )
                self.metrics["failed"] += 1
                # Send to dead letter queue
                await self.send_to_dlq(record, error=str(e))

        return transformed

    async def load(self, records: list[dict], dest_table: str):
        """Load records to destination"""
        if not records:
            return

        async with asyncpg.create_pool(self.config.dest_connection) as dest_pool:
            async with dest_pool.acquire() as conn:
                # Upsert with conflict resolution
                await conn.executemany(
                    f"""
                    INSERT INTO {dest_table} (id, name, email, created_at, full_name, email_domain, processed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        full_name = EXCLUDED.full_name,
                        email_domain = EXCLUDED.email_domain,
                        processed_at = EXCLUDED.processed_at
                    """,
                    [
                        (
                            r["id"],
                            r["name"],
                            r["email"],
                            r["created_at"],
                            r["full_name"],
                            r["email_domain"],
                            r["processed_at"],
                        )
                        for r in records
                    ],
                )
                self.metrics["loaded"] += len(records)
                logger.info("loaded_batch", count=len(records))

    async def send_to_dlq(self, record: dict, error: str):
        """Send failed records to dead letter queue"""
        # Implementation depends on your DLQ (Kafka, SQS, database table)
        logger.warning("record_to_dlq", record_id=record.get("id"), error=error)

    async def run(self, source_query: str, dest_table: str):
        """Run the complete ETL pipeline"""
        logger.info("pipeline_started")
        start_time = datetime.utcnow()

        try:
            async for batch in self.extract(source_query):
                # Transform
                transformed = await self.transform(batch)

                # Load
                await self.load(transformed, dest_table)

        except Exception as e:
            logger.error("pipeline_failed", error=str(e))
            raise

        finally:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info("pipeline_completed", metrics=self.metrics, duration_s=duration)


# Usage
async def main():
    config = PipelineConfig(
        source_connection="postgresql://source/db",
        dest_connection="postgresql://dest/db",
        batch_size=1000,
        max_workers=4,
    )

    async with AsyncETLPipeline(config) as pipeline:
        await pipeline.run(
            source_query="SELECT * FROM users WHERE updated_at > NOW() - INTERVAL '1 day'",
            dest_table="users_processed",
        )


if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Apache Airflow 2.x DAG with TaskFlow API

```python
from airflow import DAG
from airflow.decorators import task, task_group
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.dates import days_ago
from datetime import timedelta
import pandas as pd


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email": ["alerts@company.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}


@task_group
def extract_sources():
    """Extract from multiple sources in parallel"""

    @task
    def extract_from_postgres():
        hook = PostgresHook(postgres_conn_id="source_postgres")
        df = hook.get_pandas_df("SELECT * FROM users WHERE updated_at > %(checkpoint)s")
        return df.to_dict("records")

    @task
    def extract_from_api():
        import requests

        response = requests.get("https://api.example.com/data")
        response.raise_for_status()
        return response.json()

    @task
    def extract_from_s3():
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook

        s3 = S3Hook(aws_conn_id="aws_default")
        content = s3.read_key("s3://bucket/data.csv")
        df = pd.read_csv(content)
        return df.to_dict("records")

    return [extract_from_postgres(), extract_from_api(), extract_from_s3()]


@task
def combine_sources(postgres_data, api_data, s3_data):
    """Combine data from multiple sources"""
    all_data = postgres_data + api_data + s3_data
    return all_data


@task
def transform_and_validate(data):
    """Apply transformations and validation"""
    from pydantic import BaseModel, EmailStr, validator

    class UserRecord(BaseModel):
        id: int
        email: EmailStr
        name: str
        age: int

        @validator("age")
        def validate_age(cls, v):
            if not 0 <= v <= 120:
                raise ValueError(f"Invalid age: {v}")
            return v

    validated_data = []
    failed_records = []

    for record in data:
        try:
            validated = UserRecord(**record)
            validated_data.append(validated.dict())
        except Exception as e:
            failed_records.append({"record": record, "error": str(e)})

    # Log failed records
    if failed_records:
        print(f"Failed to validate {len(failed_records)} records")

    return validated_data


@task
def load_to_warehouse(data):
    """Load transformed data to warehouse"""
    hook = PostgresHook(postgres_conn_id="warehouse_postgres")
    hook.insert_rows(
        table="analytics.users",
        rows=[tuple(r.values()) for r in data],
        target_fields=list(data[0].keys()),
        replace=True,
        replace_index=["id"],
    )
    return len(data)


@task
def update_checkpoint(record_count):
    """Update pipeline checkpoint"""
    from airflow.models import Variable
    from datetime import datetime

    Variable.set("last_pipeline_run", datetime.utcnow().isoformat())
    return {"records_processed": record_count, "status": "success"}


with DAG(
    "user_etl_pipeline",
    default_args=default_args,
    description="ETL pipeline for user data",
    schedule_interval="0 */6 * * *",  # Every 6 hours
    start_date=days_ago(1),
    catchup=False,
    tags=["etl", "users", "production"],
    max_active_runs=1,
) as dag:
    # Extract from multiple sources in parallel
    sources = extract_sources()

    # Combine sources
    combined = combine_sources(*sources)

    # Transform and validate
    validated = transform_and_validate(combined)

    # Load to warehouse
    loaded_count = load_to_warehouse(validated)

    # Update checkpoint
    checkpoint = update_checkpoint(loaded_count)
```

### 3. Streaming Pipeline with Apache Kafka

```python
from kafka import KafkaConsumer, KafkaProducer
from typing import Callable
import json
import structlog

logger = structlog.get_logger()


class StreamProcessor:
    """Real-time stream processing with Kafka"""

    def __init__(
        self,
        bootstrap_servers: list[str],
        input_topic: str,
        output_topic: str,
        consumer_group: str,
    ):
        self.consumer = KafkaConsumer(
            input_topic,
            bootstrap_servers=bootstrap_servers,
            group_id=consumer_group,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
            max_poll_records=500,
        )

        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            compression_type="gzip",
        )

        self.output_topic = output_topic

    def process_message(self, message: dict) -> dict:
        """Process a single message"""
        # Apply transformations
        processed = {
            "id": message["id"],
            "timestamp": message["timestamp"],
            "value": message["value"] * 1.1,  # Example transformation
            "processed_at": datetime.utcnow().isoformat(),
        }
        return processed

    def run(self, window_size_ms: int = 5000):
        """Run the stream processor with windowing"""
        window_buffer = []
        window_start = time.time()

        try:
            for msg in self.consumer:
                try:
                    # Process message
                    processed = self.process_message(msg.value)

                    # Add to window
                    window_buffer.append(processed)

                    # Check if window is complete
                    if (time.time() - window_start) * 1000 >= window_size_ms:
                        # Aggregate window
                        aggregated = self.aggregate_window(window_buffer)

                        # Send to output topic
                        self.producer.send(self.output_topic, value=aggregated)

                        # Commit offsets (exactly-once semantics)
                        self.consumer.commit()

                        # Reset window
                        window_buffer = []
                        window_start = time.time()

                        logger.info("window_processed", count=len(window_buffer))

                except Exception as e:
                    logger.error("message_processing_failed", error=str(e))

        finally:
            self.consumer.close()
            self.producer.close()

    def aggregate_window(self, messages: list[dict]) -> dict:
        """Aggregate messages in window"""
        return {
            "window_start": time.time(),
            "count": len(messages),
            "avg_value": sum(m["value"] for m in messages) / len(messages),
            "messages": messages,
        }
```

______________________________________________________________________

## Architecture Patterns

### Pattern 1: Lambda Architecture (Batch + Stream)

- **Batch Layer**: Historical data processing with Spark/Airflow
- **Speed Layer**: Real-time processing with Kafka/Flink
- **Serving Layer**: Unified views in data warehouse

### Pattern 2: Kappa Architecture (Stream-Only)

- **Stream Processing**: All data as streams (Kafka + Flink)
- **Storage**: Stream-optimized storage (Kafka + S3)
- **Query**: Stream-native queries (KSQL, Flink SQL)

### Pattern 3: Medallion Architecture (Bronze/Silver/Gold)

- **Bronze**: Raw data (minimal processing)
- **Silver**: Cleaned/validated data
- **Gold**: Business-aggregated data

______________________________________________________________________

## Data Quality Framework

```python
from pydantic import BaseModel, validator
from typing import Optional
import great_expectations as ge


class DataQualityChecker:
    """Automated data quality validation"""

    def __init__(self, context: ge.DataContext):
        self.context = context

    def validate_batch(self, df, expectation_suite_name: str):
        """Validate a batch of data"""
        batch = self.context.get_batch(
            batch_kwargs={"dataset": df, "datasource": "pandas"},
            expectation_suite_name=expectation_suite_name,
        )

        results = batch.validate()

        if not results.success:
            failures = [exp for exp in results.results if not exp.success]
            logger.error("data_quality_failed", failures=failures)
            raise DataQualityException(failures)

        return results


# Example expectations
def create_expectation_suite():
    """Create data quality expectations"""
    suite = ge.core.ExpectationSuite(expectation_suite_name="user_data_suite")

    # Add expectations
    suite.add_expectation(
        ge.core.ExpectationConfiguration(
            expectation_type="expect_column_values_to_not_be_null",
            kwargs={"column": "id"},
        )
    )

    suite.add_expectation(
        ge.core.ExpectationConfiguration(
            expectation_type="expect_column_values_to_match_regex",
            kwargs={
                "column": "email",
                "regex": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            },
        )
    )

    suite.add_expectation(
        ge.core.ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "age", "min_value": 0, "max_value": 120},
        )
    )

    return suite
```

______________________________________________________________________

## Monitoring and Observability

### Key Metrics to Track

1. **Pipeline Health**:

   - Success rate (%)
   - Processing latency (p50, p95, p99)
   - Records processed per minute
   - Error rate by type

1. **Data Quality**:

   - Schema validation failures
   - Null/missing value percentage
   - Duplicate record rate
   - Business rule violations

1. **Resource Usage**:

   - CPU/memory utilization
   - Disk I/O
   - Network throughput
   - Cost per million records

### Alerting Example

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
pipeline_records_total = Counter("pipeline_records_total", "Total records processed")
pipeline_errors_total = Counter("pipeline_errors_total", "Total processing errors")
pipeline_duration_seconds = Histogram(
    "pipeline_duration_seconds", "Pipeline execution time"
)
pipeline_backlog = Gauge("pipeline_backlog", "Number of records waiting")


# Use in pipeline
with pipeline_duration_seconds.time():
    for record in records:
        try:
            process(record)
            pipeline_records_total.inc()
        except Exception:
            pipeline_errors_total.inc()
```

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `data-engineer` - End-to-end pipeline design and implementation
- `architecture-council` - System architecture and scalability patterns

**Supporting Specialists**:

- `python-pro` - Python code optimization and async patterns
- `postgresql-specialist` - Database optimization and query tuning
- `redis-specialist` - Caching strategies
- `docker-specialist` - Containerization and deployment

**Quality & Operations**:

- `qa-strategist` - Pipeline testing strategies
- `observability-incident-lead` - Performance optimization
- `observability-incident-lead` - Monitoring and alerting setup

______________________________________________________________________

## Best Practices

1. **Idempotency**: Ensure pipeline can be safely re-run
1. **Incremental Processing**: Use watermarks and checkpoints
1. **Data Lineage**: Track data origin and transformations
1. **Error Handling**: Implement dead letter queues
1. **Schema Evolution**: Handle schema changes gracefully
1. **Resource Optimization**: Right-size compute and storage
1. **Security**: Encrypt data at rest and in transit
1. **Testing**: Unit test transformations, integration test pipelines
1. **Documentation**: Document data models and business logic
1. **Cost Management**: Monitor and optimize cloud costs

______________________________________________________________________

## Security Considerations

### Data Access Control

- **Principle of Least Privilege**: Grant minimal necessary permissions
- **Row-Level Security**: Implement tenant isolation in multi-tenant systems
- **Audit Logging**: Track all data access and modifications

```python
# Example: Row-level security in PostgreSQL
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::int);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
```

### Data Encryption

- **Encryption at Rest**: Enable database encryption (TDE)
- **Encryption in Transit**: Enforce TLS for all connections
- **Column-Level Encryption**: Encrypt sensitive fields (SSN, credit cards)

```python
# Example: Column-level encryption
from cryptography.fernet import Fernet


class EncryptedField:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)

    def encrypt(self, value: str) -> bytes:
        return self.cipher.encrypt(value.encode())

    def decrypt(self, encrypted: bytes) -> str:
        return self.cipher.decrypt(encrypted).decode()


# Usage in models
ssn_cipher = EncryptedField(ENCRYPTION_KEY)
encrypted_ssn = ssn_cipher.encrypt(user.ssn)
```

### SQL Injection Prevention

- **Parameterized Queries**: Never concatenate user input into SQL
- **ORM Usage**: Use SQLAlchemy, Django ORM, Sequelize properly
- **Input Validation**: Validate and sanitize all user inputs

```python
# ❌ VULNERABLE - SQL Injection
query = f"SELECT * FROM users WHERE email = '{user_input}'"

# ✅ SAFE - Parameterized query
query = "SELECT * FROM users WHERE email = %s"
cursor.execute(query, (user_input,))
```

### Data Retention & Privacy

- **Data Retention Policies**: Define and enforce retention periods
- **Right to Deletion**: Implement GDPR/CCPA deletion capabilities
- **Data Anonymization**: Anonymize data for analytics/testing

### Backup Security

- **Encrypted Backups**: Encrypt all backup files
- **Secure Storage**: Store backups in separate, access-controlled locations
- **Backup Access Auditing**: Log all backup access and restorations

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Data Pipeline Testing

```python
# Test data transformations
import pytest
from pipeline import transform_user_data


def test_data_transformation():
    input_data = {"email": "USER@EXAMPLE.COM", "name": "  John Doe  ", "age": "30"}

    result = transform_user_data(input_data)

    assert result["email"] == "user@example.com"  # Lowercased
    assert result["name"] == "John Doe"  # Trimmed
    assert result["age"] == 30  # Converted to int


def test_handles_missing_fields():
    input_data = {"email": "user@example.com"}

    result = transform_user_data(input_data)

    assert "name" in result
    assert result["name"] is None  # Graceful handling
```

### Data Quality Validation

```python
# Great Expectations example
import great_expectations as ge


def test_data_quality():
    df = ge.read_csv("users.csv")

    # Expectations as tests
    assert df.expect_column_to_exist("email").success
    assert df.expect_column_values_to_not_be_null("email").success
    assert df.expect_column_values_to_match_regex(
        "email", r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    ).success
    assert df.expect_column_values_to_be_between("age", 0, 150).success
```

### Database Migration Testing

```python
# Test migrations are reversible
def test_migration_up_down():
    # Apply migration
    run_migration("001_add_users_table")

    # Verify schema changes
    assert table_exists("users")
    assert column_exists("users", "email")

    # Rollback migration
    run_migration_down("001_add_users_table")

    # Verify rollback
    assert not table_exists("users")


# Test data preservation during migration
def test_migration_preserves_data():
    # Insert test data
    insert_user(email="test@example.com", name="Test User")

    # Run migration
    run_migration("002_add_user_age_column")

    # Verify data still exists
    user = get_user("test@example.com")
    assert user["name"] == "Test User"
    assert "age" in user  # New column exists
```

### ETL Integration Testing

```python
# Test full ETL pipeline
def test_etl_pipeline_end_to_end():
    # Setup: Create source data
    source_db.insert(
        [
            {"id": 1, "name": "User 1"},
            {"id": 2, "name": "User 2"},
        ]
    )

    # Execute: Run ETL
    pipeline.extract()
    pipeline.transform()
    pipeline.load()

    # Verify: Check destination
    dest_data = dest_db.query("SELECT * FROM users")
    assert len(dest_data) == 2
    assert dest_data[0]["name"] == "User 1"
```

______________________________________________________________________

______________________________________________________________________

## Troubleshooting

### Common Issues

**Issue 1: Configuration Errors**

**Symptoms:**

- Tool fails to start or execute
- Missing required parameters
- Invalid configuration values

**Solutions:**

1. Verify all required environment variables are set
1. Check configuration file syntax (YAML, JSON)
1. Review logs for specific error messages
1. Validate file paths and permissions

______________________________________________________________________

**Issue 2: Permission Denied Errors**

**Symptoms:**

- Cannot access files or directories
- Operations fail with permission errors
- Insufficient privileges

**Solutions:**

1. Check file/directory permissions: `ls -la`
1. Run with appropriate user privileges
1. Verify user is in required groups: `groups`
1. Use `sudo` for privileged operations when necessary

______________________________________________________________________

**Issue 3: Resource Not Found**

**Symptoms:**

- "File not found" or "Resource not found" errors
- Missing dependencies
- Broken references

**Solutions:**

1. Verify resource paths are correct (use absolute paths)
1. Check that required files exist before execution
1. Ensure dependencies are installed
1. Review environment-specific configurations

______________________________________________________________________

**Issue 4: Timeout or Performance Issues**

**Symptoms:**

- Operations taking longer than expected
- Timeout errors
- Resource exhaustion (CPU, memory, disk)

**Solutions:**

1. Increase timeout values in configuration
1. Optimize queries or operations
1. Add pagination for large datasets
1. Monitor resource usage: `top`, `htop`, `docker stats`
1. Implement caching where appropriate

______________________________________________________________________

### Getting Help

If issues persist after trying these solutions:

1. **Check Logs**: Review application and system logs for detailed error messages
1. **Enable Debug Mode**: Set `LOG_LEVEL=DEBUG` for verbose output
1. **Consult Documentation**: Review related tool documentation in this directory
1. **Contact Support**: Reach out with:
   - Error messages and stack traces
   - Steps to reproduce
   - Environment details (OS, versions, configuration)
   - Relevant log excerpts

______________________________________________________________________
