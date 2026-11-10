---
name: java-reactive-patterns
description: "Use when the agent-architect plans Spring Boot WebFlux/Reactor/R2DBC/messaging components. Import-contract rules, explicit wiring tasks, and non-blocking patterns only."
---
# Import contracts
Ports (domain/application) import only `reactor.core.publisher.*` + `java.*`; never org.springframework.{web,data.r2dbc,kafka,amqp}. Adapters (infrastructure) implement ports; api depends on application only. I/O contracts return Mono<T>/Flux<T>; never Optional/List/void/Iterable as I/O types. Declare every cross-layer type in the task imports.
# Wiring tasks (plan them explicitly, with dependsOn)
WebFlux routes/controllers + ProblemDetail mapping (api); ReactiveCrudRepository/R2dbcEntityTemplate, messaging bindings, WebClient (infrastructure); Clock/scheduler beans (shared); WebTestClient/StepVerifier (tests); Flyway/R2DBC migration + local runtime (compose/Testcontainers) config. Every process()-style service gets a subscription-bean task wiring source->sink; every port gets a bound adapter task - reject no-caller ports and no-op adapters; subscriptions via SmartLifecycle, disposed on shutdown.
# Event bridges
Adapter tasks translate generic transport payloads into the context's typed domain events (strongly-typed at the boundary).
# Backpressure & caches
No unbounded collections: Sinks.many().multicast().onBackpressureBuffer(capacity); capacity + overflow strategy (DROP_OLDEST|ERROR|BUFFER) declared in the task; check EmitResult of tryEmitNext (retry FAIL_NON_SERIALIZED only; FAIL_OVERFLOW -> declared posture). DB-backed policy data gets a boot-time preload filling a reactive cache (Mono.cache); empty defaults (Map.of()) forbidden - fail startup on missing required data.
# Blocking traps (forbid in intents)
block()/blockFirst() in request paths; Thread.sleep; busy Flux.interval without scheduler; .subscribe() inside business code; unbounded collectList().
