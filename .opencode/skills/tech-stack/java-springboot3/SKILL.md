---
name: java-springboot3
description: "Use when the coder agent implements Spring Boot 3 tasks. Non-negotiable constraints, anti-patterns, and project execution rules only."
---
# Stack facts
Java 17+; Spring Boot 3.x - keep existing build/versions. `jakarta.*` only, never `javax.*`. Web: spring-boot-starter-web OR webflux (reactive = Mono/Flux everywhere, no blocking adapters). Persistence: spring-boot-starter-data-r2dbc (reactive, non-blocking - the blackboard default) or data-jpa; Flyway for migrations; embedded H2 ONLY for boot/compile verification, never production wiring. Test: spring-boot-starter-test, reactor-test; Mockito allowed; NO unmanaged network at build.
# Language conventions (planning)
Constructor injection, final fields; records for DTOs/commands/queries; interfaces (ports) + thin adapters; validation at boundaries (@Valid + ProblemDetail mapping); @Transactional at the use-case boundary; no business logic in controllers; no entities in responses.
# Layout
base package = strategy `module_layout.base_package`; packages by FEATURE within layer; interfaces in domain/application, JPA/R2DBC entities + adapters under infrastructure; config in shared.
# Build/verify
Wrapper `./mvnw` only; compile `./mvnw -q compile`; test scoped `./mvnw -q -Dtest=<Class> test`. Maven offline-friendly pins; no plugin network surprises.
# Prohibitions (tasks must never specify these)
ddl-auto=update outside tests; secrets in config; Thread.sleep/blocking IO in request paths; unbounded buffers; hardcoded timeouts (bind to config keys); Lombok unless already present.
# Naming for DDL/migrations
Flyway: `V<n>__snake_case_description.sql`, PostgreSQL dialect, snake_case tables/columns, `version` integer column for aggregate roots.
