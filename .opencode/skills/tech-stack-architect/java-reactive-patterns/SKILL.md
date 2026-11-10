---
name: java-reactive-patterns
description: "Use when the agent-architect plans Spring Boot WebFlux/Reactor/R2DBC/messaging components. Import-contract rules, explicit wiring tasks, and non-blocking patterns only."
---

# Java Reactive Patterns — Architect Rules

## Import contracts

- Ports (`domain`/`application`) import only `reactor.core.publisher.*` and `java.*`; no `org.springframework.{web,data.r2dbc,kafka,amqp}.*`.
- Adapters (`infrastructure`) implement ports; `api` depends on `application` only.
- Declare every cross-layer type in the task's `imports`; no wildcards.
- I/O contracts return `Mono<T>`/`Flux<T>`; reject `Optional`, `List`, `void`, `Iterable`.

## Explicit wiring tasks

One task per item, each with `dependsOn`:

- WebFlux routes/controllers and `ProblemDetail` error mapping (`api`).
- `ReactiveCrudRepository`/`R2dbcEntityTemplate`, messaging binding, `WebClient` (`infrastructure`).
- `Clock`/scheduler beans (`shared`); `WebTestClient`/`StepVerifier` wiring (tests).
- Flyway/R2DBC schema migration tasks and local runtime containers (Docker Compose/Testcontainers) (`infrastructure`/config).

## Pipeline assembly

- Every `process()`-style service needs a subscription-bean task wiring source to sink.
- Reject ports with no caller or no-op adapter; each port needs a bound adapter task.
- Subscriptions start via `SmartLifecycle` and dispose on shutdown.
- Event bridge adapter tasks translate generic transport payloads (e.g., `Object` intake) into strongly-typed domain events (e.g., `ValidatedOrderEvent`).

## Startup preloading

- DB-backed policy data (e.g., an `R2dbc<X>BoundaryRepository` for rate/entitlement policy) needs a boot-time preload task filling a reactive cache (`Mono.cache`).
- Forbid empty defaults (`Map.of()`); fail startup when required policy data is missing.

## Bounded sinks & backpressure

- Replace unbounded `HashMap<K, List<V>>` buffers with `Sinks.many().multicast().onBackpressureBuffer(capacity)`.
- Declare capacity and overflow strategy (`DROP_OLDEST`, `ERROR`, `BUFFER`) in the task.
- Check `EmitResult` from `tryEmitNext`.

## Non-blocking mandates

- No `.block()`, `Thread.sleep`, or `.toFuture().get()` in request or pipeline paths.
- `Schedulers.boundedElastic()` only for unavoidable blocking calls, inside an adapter.
- Bounded `limitRate`/`buffer`; no unbounded `collectList()` on streams.
- `TransactionalOperator` or `@Transactional` on reactive types; no self-invocation.
- `timeout(...)` and `retryWhen(Retry.backoff(...))` on outbound calls.
- No `ThreadLocal`; use `ContextView`. Consumers are idempotent and ack after success.

## Anti-patterns

- No `subscribe()` in business logic; return the publisher.
- No servlet types or `HttpSession` in reactive components.
- No hardcoded `Duration` or capacity magic numbers in domain/application services; all operational parameters must be bound to externalized configuration properties.
- No error-handling streams (`retryWhen`, `onErrorResume`) without a defined Dead-Letter Queue (DLQ) or fallback sink for unrecoverable errors.

