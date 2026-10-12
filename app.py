import os
from time import sleep

from flask import Flask, jsonify, render_template, request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode


exporter_mode = os.getenv("OTEL_EXPORTER_MODE", "otlp").lower()
resource = Resource.create({"service.name": "simple-llm-demo"})
provider = TracerProvider(resource=resource)

if exporter_mode == "console":
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
else:
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

METHOD_DETAILS = {
    "all": {
        "trigger": "POST /methods/demo -> run_otel_method_demo(method_name, custom_input)",
        "backend_code": "with local_tracer.start_as_current_span('otel.methods.demo') as root:",
        "otel_calls": [
            "tracer.start_as_current_span('otel.methods.demo')",
            "tracer.start_as_current_span('resource.create')",
            "tracer.start_as_current_span('tracer_provider.create')",
            "tracer.start_as_current_span('span.processor')",
            "tracer.start_as_current_span('span.lifecycle')",
            "tracer.start_as_current_span('attribute.demo')",
            "tracer.start_as_current_span('event.demo')",
            "tracer.start_as_current_span('status.demo')",
            "span.set_attribute(...)",
            "span.add_event(...)",
            "span.set_status(...)",
        ],
    },
    "resource": {
        "trigger": "run_otel_method_demo('resource', custom_input)",
        "backend_code": "with local_tracer.start_as_current_span('resource.create') as resource_span:",
        "otel_calls": [
            "resource_span.set_attribute('service.name', 'simple-llm-demo')",
            "resource_span.set_attribute('resource.type', 'service')",
            "resource_span.add_event('resource.created', {...})",
        ],
    },
    "tracerprovider": {
        "trigger": "run_otel_method_demo('tracerprovider', custom_input)",
        "backend_code": "with local_tracer.start_as_current_span('tracer_provider.create') as provider_span:",
        "otel_calls": [
            "provider_span.set_attribute('tracer.provider', 'TracerProvider')",
            "provider_span.add_event('provider.created', {...})",
        ],
    },
    "spanprocessor": {
        "trigger": "run_otel_method_demo('spanprocessor', custom_input)",
        "backend_code": "with local_tracer.start_as_current_span('span.processor') as processor_span:",
        "otel_calls": [
            "processor_span.set_attribute('processor.type', 'BatchSpanProcessor')",
            "processor_span.set_attribute('exporter.type', 'OTLPSpanExporter')",
            "processor_span.add_event('processor.registered', {...})",
        ],
    },
    "start_as_current_span": {
        "trigger": "run_otel_method_demo('start_as_current_span', custom_input)",
        "backend_code": "with local_tracer.start_as_current_span('span.lifecycle') as span_span:",
        "otel_calls": [
            "span_span.start_as_current_span()",
            "span_span.set_attribute('span.kind', 'internal')",
            "span_span.add_event('start_as_current_span', {...})",
            "span_span.get_span_context()",
        ],
    },
    "set_attribute": {
        "trigger": "run_otel_method_demo('set_attribute', custom_input)",
        "backend_code": "with local_tracer.start_as_current_span('attribute.demo') as attribute_span:",
        "otel_calls": [
            "attribute_span.set_attribute('db.system', 'qdrant')",
            "attribute_span.set_attribute('top_k', 5)",
            "attribute_span.set_attribute('retries', 2)",
            "attribute_span.add_event('attributes.set', {...})",
        ],
    },
    "add_event": {
        "trigger": "run_otel_method_demo('add_event', custom_input)",
        "backend_code": "with local_tracer.start_as_current_span('event.demo') as event_span:",
        "otel_calls": [
            "event_span.add_event('retrieval.started', {...})",
            "event_span.add_event('retrieval.completed', {...})",
        ],
    },
    "get_span_context": {
        "trigger": "run_otel_method_demo('get_span_context', custom_input)",
        "backend_code": "span_context = span_span.get_span_context()",
        "otel_calls": [
            "span_span.get_span_context()",
            "span_span.set_attribute('trace.id', ...)",
        ],
    },
    "record_exception": {
        "trigger": "run_otel_method_demo('record_exception', custom_input)",
        "backend_code": "error_span.record_exception(exc)",
        "otel_calls": [
            "try: raise ValueError(...)",
            "error_span.record_exception(exc)",
            "error_span.set_status(Status(StatusCode.ERROR, ...))",
        ],
    },
    "set_status": {
        "trigger": "run_otel_method_demo('set_status', custom_input)",
        "backend_code": "status_span.set_status(Status(StatusCode.OK, 'method demo successful'))",
        "otel_calls": [
            "status_span.set_status(Status(StatusCode.OK, ...))",
        ],
    },
}
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


@app.get("/health")
def health():
    return jsonify(status="ok")


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

    try:
        result = run_otel_method_demo(method_name, custom_input)
        return jsonify(result)
    except Exception as error:
        return jsonify(error=str(error)), 500


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
            "method_details": METHOD_DETAILS.get(method_key, METHOD_DETAILS["all"]),
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