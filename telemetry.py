"""Optional OpenTelemetry tracing shared by the blackboard orchestrators.

Configuration is read from the repository `.env` and the process environment:

  OTEL_EXPORTER_OTLP_ENDPOINT   OTLP collector endpoint (no hardcoded URL)
  OTEL_SERVICE_NAME             service name reported in traces

Tracing activates only when an endpoint is set AND the OpenTelemetry SDK is
importable; otherwise every helper is a no-op and the orchestrators keep working
unchanged.
"""
import atexit
import contextlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENDPOINT_VARS = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLO_ENDPOINT")
DEFAULT_SERVICE_NAME = "blackboard-evaluator"

_TRACER = None
_PROVIDER = None
_STATUS = None
_STATUS_CODE = None


def load_env(path=ENV_FILE):
    """Load KEY=VALUE pairs from ``.env`` into os.environ (existing keys win)."""
    path = Path(path)
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def endpoint():
    for name in ENDPOINT_VARS:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _shutdown():
    if _PROVIDER is not None:
        _PROVIDER.shutdown()


def init_telemetry(service_name=None):
    """Configure the tracer provider; returns the tracer or None when disabled."""
    global _TRACER, _PROVIDER, _STATUS, _STATUS_CODE
    load_env()
    otlp_endpoint = endpoint()
    if not otlp_endpoint:
        return None
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", otlp_endpoint)
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace import Status, StatusCode
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except ImportError:
        print("[otel] endpoint set but the OpenTelemetry SDK is not installed; tracing disabled")
        return None
    name = service_name or os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    _PROVIDER = TracerProvider(
        resource=Resource.create({"service.name": name, "openinference.project.name": name})
    )
    _PROVIDER.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(_PROVIDER)
    _TRACER = trace.get_tracer("blackboard.orchestrator")
    _STATUS = Status
    _STATUS_CODE = StatusCode
    atexit.register(_shutdown)
    return _TRACER


@contextlib.contextmanager
def span(name, attributes=None):
    if _TRACER is None:
        yield None
        return
    with _TRACER.start_as_current_span(name) as current:
        for key, value in (attributes or {}).items():
            if value is not None:
                current.set_attribute(key, value)
        yield current


def mark_error(current, reason):
    if current is None or _STATUS is None:
        return
    current.set_status(_STATUS(_STATUS_CODE.ERROR, str(reason)))


def mark_ok(current):
    if current is None or _STATUS is None:
        return
    current.set_status(_STATUS(_STATUS_CODE.OK))


def task_attributes(task):
    if not isinstance(task, dict):
        return {}
    return {
        "task.id": task.get("id"),
        "task.stage": task.get("stage"),
        "task.kind": task.get("kind"),
        "task.target_agent": task.get("targetAgent"),
        "task.path": task.get("path"),
    }
