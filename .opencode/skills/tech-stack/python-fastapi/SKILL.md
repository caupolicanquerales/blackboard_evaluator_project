---
name: python-fastapi
description: "Stack constraints for planning and emission; technology names and versions come from here."
---
# Stack facts
Python 3.11+; FastAPI >=0.115; Uvicorn ASGI; pydantic v2 (pydantic-settings for config). Layout: `src/app` (or `app`) with routers/, services/ (use cases), domain models as pydantic models or dataclasses, persistence adapters behind Protocols.
# Conventions (planning)
Async endpoints (`async def`) with no blocking calls inside (sync drivers go behind `run_in_threadpool` or are declared non-async); dependency injection via `Depends` on thin provider functions; Pydantic DTOs at boundaries, never DB models in responses; domain errors raised as typed exceptions, mapped centrally by exception handlers; configuration ONLY through a settings object with safe defaults (env-file overrides), never module-level `os.getenv` in business code; background work via `BackgroundTasks` or a declared worker - no threads in request paths.
# Persistence & test
SQLAlchemy 2.x async OR a declared driver per strategy; Alembic for expand-only migrations (`<rev>_<slug>.py`); pytest + httpx AsyncClient + `dependency_overrides` (tests only), in-memory sqlite for boot verification. Migration RUNNER config lives where the runtime reads it: `script_location`/`version_locations` in `alembic.ini` (or the settings object's migration path), and the env target imports the app's settings - never a standalone profile fragment nothing loads. The versions folder the runner names must contain the migration scripts the plan's `db/migrations` produced (generate or copy them there).
# Observability & audit design (concrete side of the strategy's `observability` object)
Logs: stdlib `logging` via ONE configured logger (or structlog if the strategy names it), JSON output configured in the settings object - levels/format keys are config-unit literals, never `print()`. Export for external tools (the strategy's `observability.export`): the contract sink is a rotating file of JSON lines (`logging.dictConfig` FileHandler/RotatingFileHandler or structlog's file renderer, keys carried by the settings object: path, max bytes, backups), tailed by Filebeat/Fluent Bit/Vector into Elasticsearch - the app writes files, the platform ships them. Direct handlers (elasticsearch-py, OTLP push) ONLY when the description names the endpoint, disabled under the test profile so boot passes offline. Console may stay human-readable; the FILE is the contract surface. Correlation: one ASGI middleware unit attaching `request_id` through the request state / contextvars so every log record and audit row carries it. Audit trail: application port (a `Protocol`) recording the tabled entry (actor, action, outcome, timestamp, correlation id) + a persistence adapter writing an append-only table through the same driver/migration the database step owns; transactional join or best-effort is stated per invariant. Metrics only if the strategy names them: a thin counting port the adapters satisfy (prometheus client only when the description asks), bounded labels. Test surfaces the tester asserts: pytest `caplog` records' FIELDS (message template args/extra, not formatted text), the audit Protocol's recording fake in `dependency_overrides`, and counting-port totals; a meter name or record field missing from `ast_hints` is a plan hole.
# Build/run
`uvicorn main:app`; requirements.txt pinned exact versions; no poetry/pipenv unless the strategy says.
# Record keys (board `ast_hints` vocabulary -> this language)
`package` = the module's import path (dotted location of the file, e.g. `app.intake`);
`implements` = base classes / `typing.Protocol` names the unit declares (`[]` for plain
modules); `methods[].signature` is the Python `def` header (name, typed parameters, return
type); `config[].path` = dotted settings/pydantic fields; `path` = the `.py` file.
`routes[].method`/`path` = the verb and path string of the router decorator (`@router.post("/ingress/packets")`); A build
`coordinate` = the pinned requirement string (`fastapi==x.y.z`) spelled EXACTLY as the
manifest carries it, and `missing_coordinates` / the ONE manifest's intent use that same
spelling (requirements.txt / pyproject), never a short-id alias.
# Scaffold facts (the strategy phase's ONLY dependency source)
Scaffold generator: the FastAPI project generator (mcp-server-fastapi). Spell dependencies
as their REQUIREMENTS-NATIVE distribution names - `fastapi`, `uvicorn[standard]`, `pydantic`,
`sqlalchemy` or the declared driver, `pytest`, `httpx` - NEVER import names (`uvicorn`
extras spelled with the bracket form the resolver expects). The list MUST include `pytest`
and `httpx` (the test artifact + test client); the test lane runs against the ASGI app in
-process. The generator's default version is a trap - the strategy's pin wins; the stage-0
re-pin fallback keeps requirements equal to it.

# Worked draft example
ONE honest unit record for THIS stack - the planner brief lifts it verbatim; the shape
is law everywhere, these spellings are Python/FastAPI's only. Unit 21 expands to
T1-021/T2-021/T3-021 with the IDENTICAL ast_hints pair (the engine mirrors it):
```json
[
 {"n": 21, "project": "telemetry", "layer": "interface", "feature": null,
  "dependsOn": {"test": ["T0-001", "T1-020"], "code": ["T0-001", "T2-020"]},
  "test": {"path": "tests/intake/test_ingress_router.py",
           "export": "test_ingress_router",
           "intent": "Slice drives POST /ingress/packets AT the lookup: owner's packet appended (AZ-02 permitted); a VALID packet bearing a foreign tenant's id REFUSED 403 (cross-owner); duplicate key a no-op; assert the appended row, the refused status, the counted meter."},
  "code": {"path": "app/intake/ingress_router.py",
           "export": "ingress_router",
           "intent": "Unit IS the surface 'packet ingest HTTP inbound': AZ-02 tenant-scoped-query enforced at the lookup - get_for_tenant on the injected SampleStore dependency, a foreign tenant's packet never fetched, 403 on refusal; counts telemetry.ingest.accepted per append; duplicate key a no-op.",
           "ast_hints": {"package": "app.intake", "implements": [],
             "dependencies": [{"type": "SampleStore", "task_id": "T2-020"}],
             "methods": [{"signature": "ingest(request: IngressRequest) -> None", "returns": "None"}],
             "meters": [{"name": "telemetry.ingest.accepted", "duty": "owns"}],
             "routes": [{"method": "POST", "path": "/ingress/packets", "duty": "serves"}],
             "config": []}}}]
```

# Prohibitions in tasks
blocking IO in async endpoints, module-level env reads, ORM models serialized directly, test secrets, unpinned dependencies, `python -m pytest` with network fixtures.
