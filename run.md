# Run Guide and OpenTelemetry Methods Used

This project demonstrates OpenTelemetry tracing for a simple Flask chat app. The implementation lives in [app.py](app.py).

## Run the app

```bash
docker compose up --build
```

Then open:

- App: http://localhost:8000
- OpenTelemetry methods demo UI: http://localhost:8000/methods
- Jaeger UI: http://localhost:16686

To stop the stack:

```bash
docker compose down
```

## OpenTelemetry terminology you should know

OpenTelemetry ka core idea ye hai ki ek request ka full lifecycle visible rahe. Har step ko span ke roop me capture kiya jata hai, aur in spans ko ek trace ke andar group kiya jata hai.

| Concept | Simple meaning | RAG example |
| --- | --- | --- |
| Trace | Ek complete request ka end-to-end journey | User query → vector search → re-ranking → final answer |
| Span | Trace ka ek individual operation | `vector_search`, `retrieval`, `llm.generate` |
| Parent Span | Main orchestration span | `rag_pipeline` |
| Child Span | Parent ke andar execution step | `retrieval`, `reranker`, `answer_generation` |
| Attributes | Span ki metadata | `top_k=5`, `model=gpt-4o-mini`, `db=qdrant` |
| Events | Span ke andar timestamped event | `search.started`, `retry`, `error` |
| Status | Operation ka final state | `OK` or `ERROR` |
| Context | Parent-child relationship aur trace propagation maintain karta hai | `Trace ID` and `Parent Span ID` travel across calls |
| Exporter | Telemetry ko external backend tak bhejta hai | OTLP exporter |
| Collector | Data receive, process, and forward karta hai | OTel Collector |
| Resource | Service ke basic metadata | `service.name=simple-llm-demo` |

### Why this matters in RAG

A Retrieval-Augmented Generation pipeline usually looks like this:

```text
rag_pipeline
├── query_validation
├── retrieval
│   ├── vector_search
│   └── document_filtering
├── reranker
├── llm.generate
└── response_formatting
```

Yahan `rag_pipeline` ek parent span hai, aur `retrieval`, `reranker`, `llm.generate` child spans hain. Is tarah aap dekh sakte ho ki request kitne time me kaise process hui, kis step par delay aya, aur kis operation me error hua.

### Attributes, events, status, and context in real usage

- Attributes are key-value metadata attached to a span.
  - Example: `db.system=qdrant`, `top_k=5`, `model_name=mock-llm`
- Events are timestamped milestones inside a span.
  - Example: `retrieval.started`, `retry.attempt=2`, `answer.generated`
- Status tells whether the operation succeeded or failed.
  - Example: `StatusCode.OK` or `StatusCode.ERROR`
- Context is what links parent and child spans and propagates trace information across function boundaries.

### Example: RAG-style tracing code

```python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("rag-demo")


def rag_pipeline(question: str):
    with tracer.start_as_current_span("rag_pipeline") as root:
        root.set_attribute("rag.question.length", len(question))
        root.add_event("query.received", {"question": question})

        with tracer.start_as_current_span("retrieval") as retrieval:
            retrieval.set_attribute("vector_db", "qdrant")
            retrieval.set_attribute("top_k", 5)
            retrieval.add_event("search.started")

            documents = ["Document A", "Document B", "Document C"]
            retrieval.add_event("search.completed", {"hits": len(documents)})

        with tracer.start_as_current_span("reranker") as reranker:
            reranker.set_attribute("reranker.model", "cross-encoder-mini")
            reranker.add_event("ranking.completed", {"ranked_docs": 3})

        with tracer.start_as_current_span("llm.generate") as llm_span:
            llm_span.set_attribute("gen_ai.request.model", "gpt-4o-mini")
            try:
                answer = f"Answer for: {question}"
                llm_span.set_attribute("gen_ai.response.length", len(answer))
            except Exception as exc:
                llm_span.record_exception(exc)
                llm_span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

        return "Final answer"
```

Is example me:

- `rag_pipeline` parent span hai
- `retrieval`, `reranker`, `llm.generate` child spans hain
- `set_attribute(...)` metadata add karta hai
- `add_event(...)` timestamped events record karta hai
- `record_exception(...)` aur `set_status(...)` error ko clearly trace karte hain
- `trace` ka context parent-child relationship maintain karta hai

## OpenTelemetry methods and usage in this app

### 1. Resource configuration

```python
resource = Resource.create({"service.name": "simple-llm-demo"})
```

- `Resource.create(...)` creates metadata for the service.
- This attaches a service name so traces are grouped under `simple-llm-demo` in Jaeger.

### 2. Tracer provider setup

```python
provider = TracerProvider(resource=resource)
```

- `TracerProvider(...)` creates the tracing provider for the application.
- It owns active span processing and span context state.

### 3. Span processor registration

```python
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "http://localhost:4318/v1/traces",
            )
        )
    )
)
```

- `add_span_processor(...)` registers a processor with the tracer provider.
- `BatchSpanProcessor(...)` batches spans before export for efficiency.
- `OTLPSpanExporter(...)` sends telemetry to the OTLP HTTP endpoint.
- `endpoint=...` tells the exporter where to send the trace data.

### 4. Global tracer registration

```python
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
```

- `trace.set_tracer_provider(provider)` installs the provider as the global default.
- `trace.get_tracer(__name__)` returns a tracer instance for creating spans in this module.

### 5. Creating child spans for the simulated LLM call

```python
with tracer.start_as_current_span("llm.invoke") as span:
```

- `start_as_current_span(...)` creates a new span and makes it the current active span.
- The `with` block ensures the span is closed automatically when leaving the block.

### 6. Setting span attributes

```python
span.set_attribute("gen_ai.operation.name", "chat")
span.set_attribute("gen_ai.request.model", "mock-llm")
```

- `set_attribute(...)` adds metadata to the span.
- These attributes record the model and operation associated with the request.

### 7. Nested spans

```python
with tracer.start_as_current_span("prompt.prepare"):
    prepared_prompt = f"Answer helpfully and briefly: {prompt}"
```

```python
with tracer.start_as_current_span("llm.generate") as generation_span:
```

- Nested spans represent internal steps in a request.
- Parent-child relationships are visible in Jaeger as a span tree.

### 8. Recording token usage on a span

```python
generation_span.set_attribute("gen_ai.usage.input_tokens", len(prepared_prompt.split()))
generation_span.set_attribute("gen_ai.usage.output_tokens", len(answer.split()))
```

- `set_attribute(...)` is used again to write telemetry metrics on the span itself.
- This captures input/output token counts for the simulated model call.

### 9. Getting trace context

```python
trace_id = f"{span.get_span_context().trace_id:032x}"
```

- `get_span_context()` returns the active span context.
- `trace_id` is used in the API response so the user can correlate the response with the trace in Jaeger.

### 10. Request span for the HTTP endpoint

```python
with tracer.start_as_current_span("chat.request") as span:
```

- This creates a top-level span for the `/chat` request.
- It captures the overall request lifecycle and all nested child spans beneath it.

### 11. Recording exceptions and status

```python
span.record_exception(error)
span.set_status(Status(StatusCode.ERROR, str(error)))
```

- `record_exception(...)` captures exception details in the span.
- `set_status(...)` marks the span with an error status and a message.
- `Status` and `StatusCode.ERROR` are part of the OpenTelemetry tracing API.

## Trace structure produced by the app

The app creates this nested span tree:

```text
chat.request
└── llm.invoke
    ├── prompt.prepare
    └── llm.generate
```

This demonstrates a realistic parent-child relationship between the request, the LLM orchestration, and internal steps.

## Full method-based OpenTelemetry code example

```python
import os
from time import sleep

from flask import Flask, jsonify, request, render_template
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode


resource = Resource.create({"service.name": "simple-llm-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "http://localhost:4318/v1/traces",
            )
        )
    )
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
app = Flask(__name__)


def mock_llm(prompt: str) -> str:
    with tracer.start_as_current_span("llm.invoke") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "mock-llm")
        span.set_attribute("gen_ai.prompt", prompt)

        with tracer.start_as_current_span("prompt.prepare") as prepare_span:
            prepared_prompt = f"Answer helpfully and briefly: {prompt}"
            prepare_span.set_attribute("gen_ai.prompt.template", prepared_prompt)

        with tracer.start_as_current_span("llm.generate") as generation_span:
            generation_span.set_attribute("gen_ai.usage.input_tokens", len(prepared_prompt.split()))
            generation_span.add_event("gen_ai.input", {"prompt": prepared_prompt})
            sleep(0.1)
            answer = f"This is a simulated answer to: {prompt}"
            generation_span.set_attribute("gen_ai.usage.output_tokens", len(answer.split()))
            generation_span.add_event("gen_ai.output", {"response": answer})
            generation_span.set_attribute("gen_ai.response", answer)

        span.set_attribute("gen_ai.response", answer)
        return answer


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/methods")
def methods_page():
    return render_template("methods.html")


@app.post("/methods/demo")
def methods_demo():
    payload = request.get_json(silent=True) or {}
    method_name = payload.get("method", "all") or "all"
    custom_input = payload.get("input") or "OpenTelemetry tracing demo"
    return jsonify(run_otel_method_demo(method_name, custom_input))


@app.post("/chat")
def chat():
    with tracer.start_as_current_span("chat.request") as span:
        try:
            body = request.get_json(force=True)
            prompt = body.get("prompt", "")
            if not isinstance(prompt, str) or not prompt.strip():
                return jsonify(error="Provide a non-empty 'prompt' string."), 400

            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.request.model", "mock-llm")
            span.set_attribute("user.input", prompt)
            answer = mock_llm(prompt)
            span.set_attribute("llm.output", answer)
            trace_id = f"{span.get_span_context().trace_id:032x}"
            return jsonify(answer=answer, model="mock-llm (simulated)", trace_id=trace_id)
        except Exception as error:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            raise


def run_otel_method_demo(method_name: str, custom_input: str = "OpenTelemetry tracing demo"):
    method_key = (method_name or "all").lower()
    local_tracer = trace.get_tracer("otel.ui.methods")

    with local_tracer.start_as_current_span("otel.methods.demo") as root:
        root.set_attribute("otel.test.method", method_key)
        root.set_attribute("service.name", "simple-llm-demo")
        root.set_attribute("user.input", custom_input)
        root.add_event("otel.demo.started", {"method": method_key, "input": custom_input})

        with local_tracer.start_as_current_span("resource.create") as resource_span:
            resource_span.set_attribute("service.name", "simple-llm-demo")
            resource_span.set_attribute("resource.type", "service")
            resource_span.set_attribute("user.input", custom_input)
            resource_span.add_event("resource.created", {"service": "simple-llm-demo", "input": custom_input})

        with local_tracer.start_as_current_span("tracer_provider.create") as provider_span:
            provider_span.set_attribute("tracer.provider", "TracerProvider")
            provider_span.set_attribute("user.input", custom_input)
            provider_span.add_event("provider.created", {"input": custom_input})

        with local_tracer.start_as_current_span("span.processor") as processor_span:
            processor_span.set_attribute("processor.type", "BatchSpanProcessor")
            processor_span.set_attribute("exporter.type", "OTLPSpanExporter")
            processor_span.set_attribute("user.input", custom_input)
            processor_span.add_event("processor.registered", {"input": custom_input})

        with local_tracer.start_as_current_span("span.lifecycle") as span_span:
            span_span.set_attribute("span.kind", "internal")
            span_span.set_attribute("user.input", custom_input)
            span_span.add_event("start_as_current_span", {"input": custom_input})
            span_span.set_attribute("demo.phase", "active")
            span_span.add_event("demo.payload", {"method": method_key, "input": custom_input})
            span_context = span_span.get_span_context()
            span_span.set_attribute("trace.id", format(span_context.trace_id, "032x"))

        with local_tracer.start_as_current_span("attribute.demo") as attribute_span:
            attribute_span.set_attribute("db.system", "qdrant")
            attribute_span.set_attribute("top_k", 5)
            attribute_span.set_attribute("retries", 2)
            attribute_span.set_attribute("user.input", custom_input)
            attribute_span.add_event("attributes.set", {"input": custom_input})

        with local_tracer.start_as_current_span("event.demo") as event_span:
            event_span.set_attribute("user.input", custom_input)
            event_span.add_event("retrieval.started", {"query": custom_input})
            event_span.add_event("retrieval.completed", {"hits": 3, "query": custom_input})

        with local_tracer.start_as_current_span("status.demo") as status_span:
            status_span.set_attribute("user.input", custom_input)
            status_span.set_status(Status(StatusCode.OK, "method demo successful"))

        if method_key in {"error", "exception", "record_exception"}:
            with local_tracer.start_as_current_span("exception.demo") as error_span:
                error_span.set_attribute("user.input", custom_input)
                try:
                    raise ValueError(f"Simulated OpenTelemetry exception for: {custom_input}")
                except Exception as exc:
                    error_span.record_exception(exc)
                    error_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    error_span.add_event("error.recorded", {"input": custom_input})

        root.add_event("otel.demo.completed", {"method": method_key, "input": custom_input})
        root.set_status(Status(StatusCode.OK, "demo completed"))

        trace_id = f"{root.get_span_context().trace_id:032x}"
        return {
            "status": "ok",
            "method": method_key,
            "input": custom_input,
            "trace_id": trace_id,
            "message": f"OpenTelemetry method demo for '{method_key}' was executed successfully.",
            "methods": [
                "all",
                "resource",
                "tracerprovider",
                "spanprocessor",
                "start_as_current_span",
                "set_attribute",
                "add_event",
                "get_span_context",
                "record_exception",
                "set_status",
            ],
        }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
```

## How to test the full method flow

1. Open `http://localhost:8000/methods`
2. Type any custom input, for example:
   - `What is OpenTelemetry?`
   - `Explain tracing in RAG`
3. Click any method button
4. Open Jaeger at `http://localhost:16686`
5. Search for the `simple-llm-demo` service and inspect the returned trace

This trace will contain:

- user input in attributes
- method name in span metadata
- events such as `retrieval.started` and `otel.demo.completed`
- status as `OK` or `ERROR`
- root trace ID for correlation

## Notes

- The app exports OTLP traces over HTTP to Jaeger on port `4318`.
- Jaeger UI is served on port `16686`.
- This demo intentionally uses a simulated LLM to keep the example simple and self-contained.
