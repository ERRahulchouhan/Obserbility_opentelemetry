# OpenTelemetry Methods: Separate Runnable Guide

This page contains the important OpenTelemetry tracing methods in a simple, runnable form. The example code is in [otel_methods_demo.py](otel_methods_demo.py).

## Run it

```bash
python otel_methods_demo.py
```

Make sure Jaeger is running first:

```bash
docker compose up -d jaeger
```

Then open:

- Jaeger UI: http://localhost:16686
- Search for service: `otel-methods-demo`

## Important methods used

### 1. Resource.create

```python
resource = Resource.create({"service.name": "otel-methods-demo"})
```

Creates service metadata so traces are grouped under one service name.

### 2. TracerProvider

```python
provider = TracerProvider(resource=resource)
```

Creates the provider that manages span lifecycle and processing.

### 3. add_span_processor

```python
provider.add_span_processor(BatchSpanProcessor(exporter))
```

Registers a span processor to handle span export.

### 4. BatchSpanProcessor

```python
BatchSpanProcessor(exporter)
```

Collects spans and exports them in batches for better performance.

### 5. OTLPSpanExporter

```python
exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
```

Sends telemetry to an OTLP-compatible backend such as Jaeger.

### 6. set_tracer_provider

```python
trace.set_tracer_provider(provider)
```

Sets the tracer provider globally for the application.

### 7. get_tracer

```python
tracer = trace.get_tracer(__name__)
```

Gets a tracer instance used to create spans.

### 8. start_as_current_span

```python
with tracer.start_as_current_span("rag_pipeline") as span:
```

Creates a new span and makes it current while the block executes.

### 9. set_attribute

```python
span.set_attribute("db.system", "qdrant")
span.set_attribute("top_k", 5)
```

Adds key-value metadata to the span.

### 10. add_event

```python
span.add_event("retrieval.completed", {"hits": 3})
```

Adds a timestamped event inside the span.

### 11. get_span_context

```python
ctx = span.get_span_context()
trace_id = f"{ctx.trace_id:032x}"
```

Returns trace context like trace ID and span ID.

### 12. record_exception

```python
span.record_exception(error)
```

Records the exception object inside the span.

### 13. set_status

```python
span.set_status(Status(StatusCode.ERROR, str(error)))
```

Marks the span as OK or ERROR.

## Full working example

See the runnable demo in [otel_methods_demo.py](otel_methods_demo.py). It demonstrates:

- trace creation
- span hierarchy
- attributes
- events
- exception recording
- status updates
- OTLP export to Jaeger

## Expected span tree

```text
demo.request
├── rag_pipeline
│   ├── query_validation
│   ├── vector_search
│   ├── reranker
│   └── llm.generate
└── error_demo
```

This shows the parent-child relationship between the request and its internal operations.
