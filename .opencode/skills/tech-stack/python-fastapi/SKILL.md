---
name: python-fastapi
description: "Stack constraints for planning and emission; technology names and versions come from here."
---
# Stack facts
Python 3.11+; FastAPI >=0.115; Uvicorn ASGI; pydantic v2 (pydantic-settings for config). Layout: `src/app` (or `app`) with routers/, services/ (use cases), domain models as pydantic models or dataclasses, persistence adapters behind Protocols.
# Conventions (planning)
Async endpoints (`async def`) with no blocking calls inside (sync drivers go behind `run_in_threadpool` or are declared non-async); dependency injection via `Depends` on thin provider functions; Pydantic DTOs at boundaries, never DB models in responses; domain errors raised as typed exceptions, mapped centrally by exception handlers; configuration ONLY through a settings object with safe defaults (env-file overrides), never module-level `os.getenv` in business code; background work via `BackgroundTasks` or a declared worker - no threads in request paths.
# Persistence & test
SQLAlchemy 2.x async OR a declared driver per strategy; Alembic for expand-only migrations (`<rev>_<slug>.py`); pytest + httpx AsyncClient + `dependency_overrides` (tests only), in-memory sqlite for boot verification.
# Build/run
`uvicorn main:app`; requirements.txt pinned exact versions; no poetry/pipenv unless the strategy says.
# Prohibitions in tasks
blocking IO in async endpoints, module-level env reads, ORM models serialized directly, test secrets, unpinned dependencies, `python -m pytest` with network fixtures.
