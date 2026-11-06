---
name: python-fastapi
description: Assembly rules for FastAPI (python). Booting the application: import wiring, settings/env defaults, routers registration, dependency providers.
---

# python-fastapi (Application Assembly)

## What the smoke test proves
- The scaffold smoke test builds the app with `TestClient` and fires one request: every
  module import must resolve and the application object must construct (routers,
  middleware, settings).
- The gate command runs that single test file: red here means the application cannot
  start, no matter how green the unit tests are.

## Reading the failure chain
- `ImportError` / `ModuleNotFoundError` on a package path: broken package layout or a
  missing `__init__.py`.
- `ValidationError` or missing env while building settings: configuration has no
  code-side defaults.
- Empty route table / `RuntimeError` about no routers: the routers were never
  `include_router`-ed into the application.
- `Depends(...)` failing: a dependency callable has no provider in the app module.

## Fix menu (smallest first)
1. Repair package wiring: add missing `__init__.py`, import the router modules where
  the app object is created, register each router with `include_router`.
2. Settings: give each configuration field a safe code-side default so the app builds
  without external env (no secrets, no invented endpoints).
3. A thin wiring module (e.g. `app/wiring.py`) exposing dependency callables that
  delegate to existing units. No new business logic in it.
4. Substitute providers only where a `Depends` has no implementation, delegating to an
  existing unit.

## Constraints
- Never change names or signatures the tests import: they are the contract.
- `dependency_overrides` belongs to tests: never move it into application code.
- Stub dependencies or default configuration added only to boot: disclose each one in
  the output.

## Editable roots
- The application package (`app/**` or `src/**`) and wiring modules. Never `tests/**`,
  `pyproject.toml`, `requirements.txt`, or the test-runner configuration.
