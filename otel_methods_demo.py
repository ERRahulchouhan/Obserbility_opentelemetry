import os
from time import sleep

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode


endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
resource = Resource.create({"service.name": "otel-methods-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


def rag_demo(question: str) -> str:
    with tracer.start_as_current_span("rag_pipeline") as pipeline:
        pipeline.set_attribute("rag.question.length", len(question))
        pipeline.add_event("query.received", {"question": question})

        with tracer.start_as_current_span("query_validation") as validation:
            validation.set_attribute("validation.type", "empty_check")
            validation.add_event("checked")

        with tracer.start_as_current_span("vector_search") as search:
            search.set_attribute("db.system", "qdrant")
            search.set_attribute("top_k", 5)
            search.add_event("search.started")
            sleep(0.2)
            docs = ["doc-1", "doc-2", "doc-3"]
            search.set_attribute("search.hits", len(docs))
            search.add_event("search.completed", {"hits": len(docs)})

        with tracer.start_as_current_span("reranker") as rerank:
            rerank.set_attribute("reranker.model", "cross-encoder-mini")
            rerank.add_event("ranking.completed", {"ranked_docs": 2})

        with tracer.start_as_current_span("llm.generate") as llm:
            llm.set_attribute("gen_ai.request.model", "mock-llm")
            llm.add_event("generation.started")
            sleep(0.3)
            answer = f"Answer for: {question}"
            llm.set_attribute("gen_ai.response.length", len(answer))
            llm.add_event("generation.completed")

        trace_id = f"{pipeline.get_span_context().trace_id:032x}"
        print(f"Trace ID: {trace_id}")
        return answer


def error_demo():
    with tracer.start_as_current_span("error_demo") as span:
        span.set_attribute("demo.type", "exception")
        try:
            raise ValueError("Simulated failure for tracing")
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            print(f"Exception captured: {exc}")


if __name__ == "__main__":
    print("Starting OpenTelemetry method demo...")
    with tracer.start_as_current_span("demo.request") as root:
        root.set_attribute("demo.service", "otel-methods-demo")
        root.add_event("request.start")

        answer = rag_demo("How does OpenTelemetry tracing help in RAG?")
        print("RAG answer:", answer)

        error_demo()

        root.add_event("request.end", {"result": "completed"})
        root.set_status(Status(StatusCode.OK, "success"))

    print("Telemetry sent to OTLP endpoint:", endpoint)
    print("Open Jaeger at http://localhost:16686 and search for service 'otel-methods-demo'")
