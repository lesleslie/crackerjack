______________________________________________________________________

title: Distributed Tracing Setup
owner: Observability Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: low
  status: active
  id: 01K6HDRW9VMXPQ3K7N8YJHZ2T6
  category: monitoring
  agents:
- observability-incident-lead
- architecture-council
  tags:
- tracing
- opentelemetry
- jaeger
- zipkin
- observability
- distributed-systems

______________________________________________________________________

## Distributed Tracing Setup

You are a distributed tracing expert specializing in implementing comprehensive observability for distributed systems. Design end-to-end tracing solutions using OpenTelemetry with automatic and manual instrumentation, context propagation, sampling strategies, and integration with Jaeger, Zipkin, or Grafana Tempo backends.

## Context

The user needs to implement distributed tracing to understand request flows across microservices, identify performance bottlenecks, debug errors, and monitor system health. Focus on production-ready implementations with proper sampling, context propagation, and minimal performance overhead.

## Requirements for: $ARGUMENTS

1. **OpenTelemetry Instrumentation**:

   - Automatic instrumentation for common frameworks
   - Manual instrumentation for custom code
   - Span creation and attributes
   - Context propagation across services
   - Baggage for cross-cutting concerns

1. **Backend Integration**:

   - Jaeger setup and configuration
   - Zipkin deployment
   - Grafana Tempo integration
   - Cloud provider tracing (AWS X-Ray, GCP Cloud Trace)

1. **Instrumentation Patterns**:

   - HTTP/REST API tracing
   - gRPC service tracing
   - Database query tracing
   - Message queue tracing (Kafka, RabbitMQ)
   - Custom business logic spans

1. **Sampling Strategies**:

   - Head-based sampling (at trace start)
   - Tail-based sampling (after trace complete)
   - Adaptive sampling
   - Error-aware sampling

1. **Performance**:

   - Minimal overhead (\<5%)
   - Asynchronous export
   - Batch processing
   - Resource detection

______________________________________________________________________

## OpenTelemetry Fundamentals

### Tracing Concepts

**Trace**: End-to-end journey of a request through the system
**Span**: Single operation within a trace (e.g., database query, HTTP request)
**Context**: Propagation information (trace ID, span ID, baggage)

```
Trace: User Login Request
├── Span: API Gateway [200ms]
│   ├── Span: Authentication Service [50ms]
│   │   └── Span: PostgreSQL Query [20ms]
│   └── Span: User Service [100ms]
│       ├── Span: Redis Get [5ms]
│       └── Span: PostgreSQL Query [30ms]
└── Span: Response Formatting [10ms]
```

### W3C Trace Context

Standard for context propagation across services:

```
traceparent: 00-{trace-id}-{parent-span-id}-{trace-flags}
tracestate: vendor1=value1,vendor2=value2
```

______________________________________________________________________

## Python Implementation (FastAPI)

### 1. Automatic Instrumentation

```python
# main.py
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

# Configure resource
resource = Resource(
    attributes={
        SERVICE_NAME: "user-service",
        "service.version": "1.0.0",
        "deployment.environment": "production",
    }
)

# Configure tracer provider
provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)

# Configure OTLP exporter (sends to Jaeger/Tempo/etc)
otlp_exporter = OTLPSpanExporter(
    endpoint="http://localhost:4317",  # Jaeger OTLP receiver
    insecure=True,
)

# Add batch span processor (efficient export)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Create FastAPI app
app = FastAPI()

# Auto-instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

# Auto-instrument HTTP client
HTTPXClientInstrumentor().instrument()

# Auto-instrument SQLAlchemy
SQLAlchemyInstrumentor().instrument()

# Auto-instrument Redis
RedisInstrumentor().instrument()


# Your routes
@app.get("/users/{user_id}")
async def get_user(user_id: str):
    # Automatically traced!
    user = await db.get_user(user_id)
    return user
```

### 2. Manual Instrumentation

```python
# services/user_service.py
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import httpx

tracer = trace.get_tracer(__name__)


class UserService:
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache

    async def get_user(self, user_id: str):
        # Create custom span
        with tracer.start_as_current_span("get_user") as span:
            # Add attributes to span
            span.set_attribute("user.id", user_id)
            span.set_attribute("cache.enabled", True)

            # Check cache
            with tracer.start_as_current_span("cache.get") as cache_span:
                cache_span.set_attribute("cache.key", f"user:{user_id}")
                cached_user = await self.cache.get(f"user:{user_id}")

                if cached_user:
                    cache_span.set_attribute("cache.hit", True)
                    span.add_event("Cache hit")
                    return cached_user

                cache_span.set_attribute("cache.hit", False)

            # Cache miss - query database
            with tracer.start_as_current_span("db.query.user") as db_span:
                db_span.set_attribute("db.system", "postgresql")
                db_span.set_attribute(
                    "db.statement", "SELECT * FROM users WHERE id = $1"
                )
                db_span.set_attribute("db.user.id", user_id)

                try:
                    user = await self.db.fetch_one(
                        "SELECT * FROM users WHERE id = $1", user_id
                    )

                    if not user:
                        span.set_status(Status(StatusCode.ERROR, "User not found"))
                        raise ValueError(f"User {user_id} not found")

                    # Cache for next time
                    await self.cache.set(f"user:{user_id}", user, ttl=300)

                    span.set_attribute("user.found", True)
                    span.add_event("User retrieved from database")

                    return user

                except Exception as e:
                    db_span.record_exception(e)
                    db_span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

    async def enrich_user_data(self, user_id: str):
        """Example: Multiple external service calls"""
        with tracer.start_as_current_span("enrich_user_data") as span:
            span.set_attribute("user.id", user_id)

            # Parallel external calls
            async with httpx.AsyncClient() as client:
                # Call 1: Get preferences
                with tracer.start_as_current_span("http.get.preferences"):
                    prefs_resp = await client.get(
                        f"http://preferences-service/users/{user_id}/preferences"
                    )
                    preferences = prefs_resp.json()

                # Call 2: Get subscriptions
                with tracer.start_as_current_span("http.get.subscriptions"):
                    subs_resp = await client.get(
                        f"http://subscription-service/users/{user_id}/subscriptions"
                    )
                    subscriptions = subs_resp.json()

            span.add_event(
                "User data enriched",
                {
                    "preferences_count": len(preferences),
                    "subscriptions_count": len(subscriptions),
                },
            )

            return {"preferences": preferences, "subscriptions": subscriptions}
```

### 3. Context Propagation

```python
# middleware/tracing_middleware.py
from opentelemetry import trace, baggage
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

propagator = TraceContextTextMapPropagator()


async def tracing_middleware(request, call_next):
    """Extract trace context from incoming requests"""

    # Extract context from headers
    context = propagator.extract(carrier=request.headers)

    # Extract baggage (cross-cutting concerns)
    user_id = baggage.get_baggage("user.id", context)
    tenant_id = baggage.get_baggage("tenant.id", context)

    # Continue with extracted context
    with trace.use_context(context):
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("http.request") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))

            if user_id:
                span.set_attribute("user.id", user_id)
            if tenant_id:
                span.set_attribute("tenant.id", tenant_id)

            response = await call_next(request)

            span.set_attribute("http.status_code", response.status_code)

            return response


# Making outbound requests with context
async def call_external_service(url: str, data: dict):
    """Propagate trace context to downstream services"""
    async with httpx.AsyncClient() as client:
        # Inject trace context into headers
        headers = {}
        propagator.inject(headers)

        # Also inject baggage
        current_baggage = baggage.get_all()
        for key, value in current_baggage.items():
            headers[f"baggage-{key}"] = value

        response = await client.post(url, json=data, headers=headers)
        return response
```

______________________________________________________________________

## Node.js/TypeScript Implementation (Express)

### 1. Automatic Instrumentation

```typescript
// tracing.ts
import { NodeSDK } from '@opentelemetry/sdk-node';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';
import { ExpressInstrumentation } from '@opentelemetry/instrumentation-express';
import { PgInstrumentation } from '@opentelemetry/instrumentation-pg';
import { RedisInstrumentation } from '@opentelemetry/instrumentation-redis-4';

const sdk = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: 'order-service',
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: 'production',
  }),
  traceExporter: new OTLPTraceExporter({
    url: 'http://localhost:4317',
  }),
  instrumentations: [
    new HttpInstrumentation(),
    new ExpressInstrumentation(),
    new PgInstrumentation(),
    new RedisInstrumentation(),
  ],
});

sdk.start();

// Graceful shutdown
process.on('SIGTERM', () => {
  sdk.shutdown()
    .then(() => console.log('Tracing terminated'))
    .catch((error) => console.error('Error terminating tracing', error))
    .finally(() => process.exit(0));
});

export default sdk;
```

```typescript
// server.ts
import './tracing'; // Must be first!
import express from 'express';
import { trace, context, SpanStatusCode } from '@opentelemetry/api';

const app = express();
const tracer = trace.getTracer('order-service');

app.get('/orders/:id', async (req, res) => {
  // Create custom span
  const span = tracer.startSpan('getOrder');
  span.setAttribute('order.id', req.params.id);

  try {
    const order = await getOrderById(req.params.id);
    span.setStatus({ code: SpanStatusCode.OK });
    res.json(order);
  } catch (error) {
    span.recordException(error as Error);
    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: (error as Error).message,
    });
    res.status(500).json({ error: 'Failed to get order' });
  } finally {
    span.end();
  }
});

app.listen(3000);
```

### 2. Manual Instrumentation

```typescript
// services/orderService.ts
import { trace, context, SpanStatusCode } from '@opentelemetry/api';
import axios from 'axios';

const tracer = trace.getTracer('order-service');

export class OrderService {
  async createOrder(userId: string, items: OrderItem[]): Promise<Order> {
    return tracer.startActiveSpan('createOrder', async (span) => {
      span.setAttribute('user.id', userId);
      span.setAttribute('items.count', items.length);

      try {
        // Validate inventory
        const inventoryValid = await tracer.startActiveSpan(
          'validateInventory',
          async (inventorySpan) => {
            inventorySpan.setAttribute('service', 'inventory-service');

            try {
              const response = await axios.post(
                'http://inventory-service/validate',
                { items }
              );
              return response.data.valid;
            } finally {
              inventorySpan.end();
            }
          }
        );

        if (!inventoryValid) {
          throw new Error('Insufficient inventory');
        }

        // Calculate total
        const total = await tracer.startActiveSpan('calculateTotal', async (calcSpan) => {
          const amount = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
          calcSpan.setAttribute('order.total', amount);
          calcSpan.end();
          return amount;
        });

        // Save order
        const order = await tracer.startActiveSpan('db.saveOrder', async (dbSpan) => {
          dbSpan.setAttribute('db.system', 'postgresql');
          dbSpan.setAttribute('db.operation', 'INSERT');

          try {
            const savedOrder = await db.orders.create({
              userId,
              items,
              total,
              status: 'pending',
            });

            dbSpan.setAttribute('order.id', savedOrder.id);
            return savedOrder;
          } finally {
            dbSpan.end();
          }
        });

        // Emit event
        span.addEvent('order.created', {
          'order.id': order.id,
          'order.total': total,
        });

        span.setStatus({ code: SpanStatusCode.OK });
        return order;

      } catch (error) {
        span.recordException(error as Error);
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: (error as Error).message,
        });
        throw error;
      } finally {
        span.end();
      }
    });
  }
}
```

______________________________________________________________________

## Go Implementation

### 1. Automatic Instrumentation

```go
// tracing/setup.go
package tracing

import (
    "context"
    "log"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/propagation"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
)

func InitTracer(serviceName, environment string) (*sdktrace.TracerProvider, error) {
    ctx := context.Background()

    // Create OTLP exporter
    conn, err := grpc.DialContext(
        ctx,
        "localhost:4317",
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
    if err != nil {
        return nil, err
    }

    exporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
    if err != nil {
        return nil, err
    }

    // Create resource
    res, err := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName(serviceName),
            semconv.ServiceVersion("1.0.0"),
            semconv.DeploymentEnvironment(environment),
        ),
    )
    if err != nil {
        return nil, err
    }

    // Create tracer provider
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.AlwaysSample()),
    )

    // Set global tracer provider
    otel.SetTracerProvider(tp)

    // Set global propagator (for context propagation)
    otel.SetTextMapPropagator(
        propagation.NewCompositeTextMapPropagator(
            propagation.TraceContext{},
            propagation.Baggage{},
        ),
    )

    log.Println("Tracing initialized")
    return tp, nil
}
```

### 2. HTTP Server Instrumentation

```go
// main.go
package main

import (
    "context"
    "log"
    "net/http"

    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/trace"
)

var tracer = otel.Tracer("payment-service")

func main() {
    // Initialize tracing
    tp, err := InitTracer("payment-service", "production")
    if err != nil {
        log.Fatal(err)
    }
    defer tp.Shutdown(context.Background())

    // Wrap handler with auto-instrumentation
    http.Handle("/payment", otelhttp.NewHandler(
        http.HandlerFunc(handlePayment),
        "handlePayment",
    ))

    log.Fatal(http.ListenAndServe(":8080", nil))
}

func handlePayment(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()

    // Extract trace context from request
    // (automatically done by otelhttp middleware)

    // Create custom span
    ctx, span := tracer.Start(ctx, "processPayment")
    defer span.End()

    // Add attributes
    span.SetAttributes(
        attribute.String("payment.method", "credit_card"),
        attribute.Float64("payment.amount", 99.99),
    )

    // Validate payment
    if err := validatePayment(ctx); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        http.Error(w, "Payment validation failed", http.StatusBadRequest)
        return
    }

    // Process payment
    if err := processPayment(ctx); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        http.Error(w, "Payment processing failed", http.StatusInternalServerError)
        return
    }

    span.AddEvent("payment.completed")
    span.SetStatus(codes.Ok, "Payment successful")

    w.WriteHeader(http.StatusOK)
    w.Write([]byte("Payment processed"))
}

func validatePayment(ctx context.Context) error {
    _, span := tracer.Start(ctx, "validatePayment")
    defer span.End()

    // Validation logic
    span.SetAttributes(
        attribute.Bool("validation.passed", true),
    )

    return nil
}

func processPayment(ctx context.Context) error {
    _, span := tracer.Start(ctx, "chargeCard")
    defer span.End()

    // Payment processing logic
    span.AddEvent("card.charged", trace.WithAttributes(
        attribute.String("transaction.id", "txn_123456"),
    ))

    return nil
}
```

### 3. gRPC Instrumentation

```go
// grpc_server.go
package main

import (
    "context"

    "go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
    "google.golang.org/grpc"
)

func newGRPCServer() *grpc.Server {
    return grpc.NewServer(
        grpc.UnaryInterceptor(otelgrpc.UnaryServerInterceptor()),
        grpc.StreamInterceptor(otelgrpc.StreamServerInterceptor()),
    )
}

// gRPC client
func newGRPCClient(target string) (*grpc.ClientConn, error) {
    return grpc.Dial(
        target,
        grpc.WithUnaryInterceptor(otelgrpc.UnaryClientInterceptor()),
        grpc.WithStreamInterceptor(otelgrpc.StreamClientInterceptor()),
    )
}
```

______________________________________________________________________

## Backend Deployment

### 1. Jaeger with Docker Compose

```yaml
# docker-compose.yml
version: '3'

services:
  jaeger:
    image: jaegertracing/all-in-one:1.51
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC receiver
      - "4318:4318"    # OTLP HTTP receiver
      - "14250:14250"  # Jaeger gRPC
    networks:
      - tracing

  # Optional: Elasticsearch for storage
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    networks:
      - tracing

networks:
  tracing:
    driver: bridge
```

### 2. Grafana Tempo

```yaml
# tempo.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

ingester:
  max_block_duration: 5m

compactor:
  compaction:
    block_retention: 48h

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/blocks
    wal:
      path: /tmp/tempo/wal

query_frontend:
  search:
    max_duration: 12h
```

```yaml
# docker-compose-tempo.yml
version: '3'

services:
  tempo:
    image: grafana/tempo:2.3.0
    command: [ "-config.file=/etc/tempo.yaml" ]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml
      - tempo-data:/tmp/tempo
    ports:
      - "3200:3200"   # Tempo
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP

  grafana:
    image: grafana/grafana:10.2.0
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    volumes:
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"

volumes:
  tempo-data:
  grafana-data:
```

### 3. Zipkin

```yaml
# docker-compose-zipkin.yml
version: '3'

services:
  zipkin:
    image: openzipkin/zipkin:2.24
    ports:
      - "9411:9411"  # Zipkin UI and API

  # Storage backend (optional)
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: zipkin
      MYSQL_DATABASE: zipkin
    volumes:
      - mysql-data:/var/lib/mysql

volumes:
  mysql-data:
```

______________________________________________________________________

## Sampling Strategies

### 1. Probability Sampling

```python
# sampling/probability.py
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

# Sample 10% of traces
sampler = TraceIdRatioBased(0.1)

provider = TracerProvider(resource=resource, sampler=sampler)
```

### 2. Parent-Based Sampling

```python
from opentelemetry.sdk.trace.sampling import ParentBased, ALWAYS_ON, ALWAYS_OFF

# Always sample if parent was sampled, otherwise never sample
sampler = ParentBased(
    root=TraceIdRatioBased(0.1),  # Sample 10% of root spans
    remote_parent_sampled=ALWAYS_ON,  # Always sample if remote parent sampled
    remote_parent_not_sampled=ALWAYS_OFF,
    local_parent_sampled=ALWAYS_ON,
    local_parent_not_sampled=ALWAYS_OFF,
)
```

### 3. Custom Sampling (Error-Aware)

```python
# sampling/custom.py
from opentelemetry.sdk.trace.sampling import Sampler, Decision, SamplingResult


class ErrorAwareSampler(Sampler):
    """Always sample errors, probabilistic sampling for success"""

    def __init__(self, error_sample_rate=1.0, success_sample_rate=0.01):
        self.error_sample_rate = error_sample_rate
        self.success_sample_rate = success_sample_rate

    def should_sample(
        self, parent_context, trace_id, name, kind, attributes, links, trace_state
    ):
        # Check if span has error attribute
        if attributes and attributes.get("error", False):
            # Always sample errors
            return SamplingResult(
                Decision.RECORD_AND_SAMPLE,
                attributes=attributes,
                trace_state=trace_state,
            )

        # Probabilistic sampling for non-errors
        if self._should_sample_trace_id(trace_id, self.success_sample_rate):
            return SamplingResult(
                Decision.RECORD_AND_SAMPLE,
                attributes=attributes,
                trace_state=trace_state,
            )

        return SamplingResult(Decision.DROP)

    def _should_sample_trace_id(self, trace_id, rate):
        # Simple modulo-based sampling
        return (trace_id % 100) < (rate * 100)

    def get_description(self):
        return "ErrorAwareSampler"
```

### 4. Adaptive Sampling

```python
# sampling/adaptive.py
import time
from collections import deque


class AdaptiveSampler(Sampler):
    """
    Adjust sampling rate based on throughput
    """

    def __init__(self, target_spans_per_second=100):
        self.target_sps = target_spans_per_second
        self.recent_samples = deque(maxlen=1000)
        self.current_rate = 0.1
        self.last_adjustment = time.time()

    def should_sample(
        self, parent_context, trace_id, name, kind, attributes, links, trace_state
    ):
        self._adjust_rate()

        if self._should_sample_trace_id(trace_id, self.current_rate):
            self.recent_samples.append(time.time())
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        return SamplingResult(Decision.DROP)

    def _adjust_rate(self):
        now = time.time()

        # Adjust every 10 seconds
        if now - self.last_adjustment < 10:
            return

        # Calculate current spans per second
        recent_time = [t for t in self.recent_samples if now - t < 60]
        current_sps = len(recent_time) / 60

        # Adjust rate
        if current_sps > self.target_sps:
            self.current_rate *= 0.9  # Decrease sampling
        elif current_sps < self.target_sps * 0.8:
            self.current_rate = min(1.0, self.current_rate * 1.1)  # Increase sampling

        self.last_adjustment = now
```

______________________________________________________________________

## Security Considerations

### Sensitive Data Scrubbing

```python
# processors/scrubbing.py
from opentelemetry.sdk.trace import SpanProcessor


class SensitiveDataProcessor(SpanProcessor):
    """Remove sensitive data from spans"""

    SENSITIVE_KEYS = {"password", "api_key", "secret", "token", "credit_card"}

    def on_start(self, span, parent_context):
        pass

    def on_end(self, span):
        # Scrub attributes
        attributes = span.attributes
        if attributes:
            for key in list(attributes.keys()):
                if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                    span.set_attribute(key, "[REDACTED]")

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass


# Add to provider
provider.add_span_processor(SensitiveDataProcessor())
```

### Security Checklist

- [ ] Sensitive data scrubbed from spans (passwords, API keys, PII)
- [ ] TLS enabled for exporter connections
- [ ] Authentication configured for trace backend
- [ ] Sampling prevents data exfiltration attacks
- [ ] Resource limits prevent memory exhaustion
- [ ] Trace data retention policy defined
- [ ] Access controls on trace backend
- [ ] Compliance requirements met (GDPR, HIPAA)

______________________________________________________________________

## Testing & Validation

### Unit Testing

```python
# tests/test_tracing.py
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def tracer():
    """Setup tracer with in-memory exporter for testing"""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    yield trace.get_tracer(__name__), exporter

    exporter.clear()


def test_span_creation(tracer):
    tracer_instance, exporter = tracer

    with tracer_instance.start_as_current_span("test-span") as span:
        span.set_attribute("test.key", "test.value")

    # Get exported spans
    spans = exporter.get_finished_spans()

    assert len(spans) == 1
    assert spans[0].name == "test-span"
    assert spans[0].attributes["test.key"] == "test.value"


def test_span_hierarchy(tracer):
    tracer_instance, exporter = tracer

    with tracer_instance.start_as_current_span("parent") as parent:
        parent.set_attribute("level", "parent")

        with tracer_instance.start_as_current_span("child") as child:
            child.set_attribute("level", "child")

    spans = exporter.get_finished_spans()

    assert len(spans) == 2
    # Find parent and child
    parent_span = next(s for s in spans if s.attributes.get("level") == "parent")
    child_span = next(s for s in spans if s.attributes.get("level") == "child")

    # Verify hierarchy
    assert child_span.parent.span_id == parent_span.context.span_id


def test_error_recording(tracer):
    tracer_instance, exporter = tracer

    with tracer_instance.start_as_current_span("error-span") as span:
        try:
            raise ValueError("Test error")
        except ValueError as e:
            span.record_exception(e)

    spans = exporter.get_finished_spans()
    events = spans[0].events

    assert len(events) == 1
    assert events[0].name == "exception"
    assert "ValueError" in str(events[0].attributes)
```

### Integration Testing

```python
# tests/test_trace_propagation.py
import httpx
from opentelemetry import trace
from opentelemetry.propagate import inject


async def test_context_propagation():
    """Test that trace context is propagated across services"""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("test-request") as span:
        headers = {}
        inject(headers)  # Inject trace context

        # Make HTTP request with context
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/test", headers=headers)

        assert response.status_code == 200

        # Verify trace ID was propagated
        # (This would require checking backend/logs)
```

### Testing Checklist

- [ ] Spans are created correctly
- [ ] Parent-child relationships maintained
- [ ] Attributes set properly
- [ ] Exceptions recorded
- [ ] Context propagated across services
- [ ] Sampling works as expected
- [ ] Exporters send data successfully
- [ ] Performance overhead \<5%
- [ ] No memory leaks in long-running processes

______________________________________________________________________

## Troubleshooting

### Common Issues

#### Issue: No Traces Appearing in Backend

**Symptoms:**

- Application instrumented but no traces visible
- Exporter showing errors
- Silent failures

**Causes:**

- Backend not running or unreachable
- Incorrect exporter endpoint
- Firewall blocking connections
- Sampling rate too low

**Solutions:**

1. **Verify backend is running**:

```bash
# Check Jaeger
curl http://localhost:16686

# Check Tempo
curl http://localhost:3200/ready

# Check Zipkin
curl http://localhost:9411/health
```

2. **Enable debug logging**:

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# OpenTelemetry logs
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
```

3. **Test exporter connection**:

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
try:
    # Try to export a test span
    print("Exporter configured successfully")
except Exception as e:
    print(f"Exporter error: {e}")
```

______________________________________________________________________

#### Issue: High Performance Overhead

**Symptoms:**

- Increased latency after adding tracing
- High CPU usage
- Memory consumption growing

**Causes:**

- Synchronous export blocking requests
- Too many spans created
- Sampling rate too high
- Large span attributes

**Solutions:**

1. **Use batch processor**:

```python
# WRONG: Synchronous export
provider.add_span_processor(SimpleSpanProcessor(exporter))

# RIGHT: Batch export
provider.add_span_processor(BatchSpanProcessor(exporter))
```

2. **Reduce sampling**:

```python
# Sample only 1% of requests
sampler = TraceIdRatioBased(0.01)
```

3. **Limit attribute sizes**:

```python
# Truncate large values
def safe_set_attribute(span, key, value):
    if isinstance(value, str) and len(value) > 1000:
        value = value[:1000] + "...[truncated]"
    span.set_attribute(key, value)
```

______________________________________________________________________

#### Issue: Missing Spans in Distributed Trace

**Symptoms:**

- Incomplete trace with gaps
- Services not connected in visualization
- Broken parent-child relationships

**Causes:**

- Context not propagated
- Different trace IDs in services
- Headers not forwarded
- Async operations not linked

**Solutions:**

1. **Verify header propagation**:

```python
# Check headers are being set
from opentelemetry.propagate import inject

headers = {}
inject(headers)
print(f"Headers: {headers}")
# Should show traceparent header
```

2. **Debug context in middleware**:

```python
from opentelemetry.propagate import extract


def middleware(request):
    ctx = extract(request.headers)
    print(f"Extracted context: {ctx}")
    # Should show trace context
```

3. **Link async operations**:

```python
import asyncio
from opentelemetry import trace


async def background_task():
    # Get current span context
    ctx = trace.get_current_span().get_span_context()

    # Use in background task
    tracer = trace.get_tracer(__name__)
    with tracer.start_span("background", context=ctx):
        await do_work()
```

______________________________________________________________________

### Getting Help

**Check Logs:**

- Application logs for instrumentation errors
- Backend logs for ingestion issues
- Network logs for connectivity problems

**Related Tools:**

- Use `observability-incident-lead` agent for metrics integration
- Use `observability-incident-lead` agent for overhead optimization
- Use `observability-incident-lead` agent for troubleshooting

**Agents to Consult:**

- `observability-incident-lead` - Tracing architecture
- `observability-incident-lead` - Backend setup
- `observability-incident-lead` - Performance optimization
- `architecture-council` - Service architecture

______________________________________________________________________

## Best Practices

1. **Instrumentation**: Start with auto-instrumentation, add manual spans for business logic
1. **Sampling**: Use adaptive sampling in production (1-10% typical)
1. **Context Propagation**: Always propagate trace context to downstream services
1. **Span Naming**: Use meaningful names (verb + noun: "GET /users", "db.query.users")
1. **Attributes**: Add relevant attributes (user ID, tenant ID, request ID)
1. **Errors**: Always record exceptions with `span.record_exception()`
1. **Events**: Use events for important milestones, not debugging logs
1. **Performance**: Batch exports, async processing, limit span sizes
1. **Security**: Scrub sensitive data, use TLS for exporters
1. **Testing**: Test in development with 100% sampling, reduce in production

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `observability-incident-lead` - Distributed tracing strategy
- `observability-incident-lead` - Backend deployment and monitoring
- `architecture-council` - Microservices architecture

**Supporting Specialists**:

- `python-pro` - Python implementation
- `javascript-pro` - Node.js/TypeScript implementation
- `golang-pro` - Go implementation
- `observability-incident-lead` - Performance optimization

**Quality & Operations**:

- `qa-strategist` - Testing strategies
- `security-auditor` - Security review
- `devops-troubleshooter` - Deployment troubleshooting
