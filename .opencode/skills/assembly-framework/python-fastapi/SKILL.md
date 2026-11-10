---
name: python-fastapi
description: Assembly rules for FastAPI (python). Booting the application: import wiring, settings/env defaults, routers registration, dependency providers.
---
# What the smoke proves
TestClient builds the app and fires one request: every import resolves and the app object constructs (routers, middleware, settings).
# Failure map
- ImportError/ModuleNotFoundError => broken package layout or missing `__init__.py`.
- ValidationError / missing env while building settings => no code-side defaults.
- Empty routes / "no routers" => routers never `include_router`-ed.
- Depends(...) failing => no provider for that dependency.
# Fix menu (smallest first)
1. Repair package wiring: add missing `__init__.py`, import router modules where the app is built, register each with include_router.
2. Settings: safe code-side defaults for every field so the app boots without external env (no secrets, no invented endpoints).
3. Thin wiring module (e.g. `app/wiring.py`) exposing dependency callables delegating to existing units; no logic.
4. Substitute providers only where a Depends has no implementation, delegating to an existing unit.
# Constraints
Never rename/retype what tests import (contract). `dependency_overrides` stays in tests. Stubs disclosed. Editable roots: the app package (`app/**` or `src/**`) + wiring; never `tests/**`, `pyproject.toml`, `requirements.txt`, runner config.
