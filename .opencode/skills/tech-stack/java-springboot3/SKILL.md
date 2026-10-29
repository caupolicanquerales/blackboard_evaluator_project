---
name: java-springboot3
description: "Use when the coder agent implements Spring Boot 3 tasks. Non-negotiable constraints, anti-patterns, and project execution rules only."
---

# Spring Boot 3 — Coder Constraints

## Task (project execution)

- Read task JSON: `path`, `kind`, `layer`, `feature`, `export`, `intent`.
- Modify only `path`; match existing package/build conventions.
- Export `export`; implement `intent`; no TODOs or placeholders.
- Respect `layer`: `domain` framework-light; `application` use cases; `infrastructure` JPA/adapters; `api` controllers/DTOs; `shared` cross-cutting.
- Layout: `api` -> `application` -> `domain`; `infrastructure` implements ports; one public type per file.
- Run the project's compile/test command; add/update tests; no shared mutable state; fix failures before finishing.

## Non-negotiable

- Java 17+ / Spring Boot 3.x; keep existing build and versions.
- `jakarta.*` only; never `javax.*`.
- Constructor injection only; `final` fields; records for DTOs/commands.
- Add only required starters; Lombok only if already present.
- Validate at boundaries; centralize error mapping.

## Anti-patterns

- No `System.out` or secrets/PII in code/config/logs.
- No business logic, repositories, auth branching, or `HttpSession` in controllers.
- No entities in HTTP responses; DTOs only.
- No `@Data`/`@EqualsAndHashCode` on entities; no public setters for invariants.
- No self-invocation of `@Transactional`/`@Async` methods.
- No `ddl-auto=update` outside tests; no schema changes without migrations.
- No N+1 queries or unbounded relation fetches.
- No swallowed exceptions; map domain errors to HTTP status.

## Components

- **Controllers (`api`)**: `@RestControllerAdvice` + `ProblemDetail`; versioned paths; stable `PageResponse<T>`.
- **Services (`application`)**: `@Transactional` on public methods; `readOnly = true` for queries; command/query separation; inject `Clock`.
- **Repositories/entities (`infrastructure`/`domain`)**: Spring Data JPA; `@Version`; LAZY `@ManyToOne`; unique constraints + FK/filter indexes; `OptimisticLockException` -> 409.
- **Security**: stateless JWT; CSRF only off for stateless token APIs.
- **Configuration**: profiles; env overrides; Flyway/Liquibase migrations.
