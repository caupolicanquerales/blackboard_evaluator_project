---
name: spring-performance
description: Coder/tester tier for performance units (reached from java-springboot §Performance units and java-junit5 §Performance tests): how to WRITE the counting decorator, the bounded retry/concurrency/timeout bodies, the cache activation and the deterministic saturation assertions. Plan facts and config keys come from tech-stack-architect/spring-performance-architect; this file is composition only.
---
# Who reads this
A stage-2 coder whose unit's table carries a performance claim (a PB-/PI- id in its intent),
or its stage-1 tester. The architect table names WHAT class and WHICH key; this file is
composition. The task's table wins over every example; a disagreement is reported, not
re-decided.

# The counting decorator (budget-observer) - the query-count proof
A final class implementing the SAME port it wraps: count each passing call (`AtomicLong`),
delegate, expose `calls()`. The wiring unit wraps the real adapter (one product, one
registration - rule (n)). Never count by log-scraping; the counter never leaks through the
port interface.

# Bounded bodies (reactor + JDK - the table's identifiers, composed)
- retry: `.retryWhen(Retry.backoff(attempts, baseDelay).transientErrors(true))`; bounds are
  constructor arguments read from config, never literals; exhaustion falls through to the
  failure path the tabled `semantics` names; attempts feed the floor meter.
- concurrency: prefer the stateless operator - inner sources via `.flatMap(mapper, N)`; a
  cross-path guard uses `Semaphore.tryAcquire` released in `doFinally`. Never park a reactive
  thread waiting for a permit - refusal IS the contracted outcome.
- admission: a `WebFilter` that tries the permit and on refusal answers the declared status
  (`429`/`503`) + `Retry-After` WITHOUT delegating; release in the completion callback. A
  429 with no bound behind it is decoration.
- cache: `@Cacheable` on the PORT-ADAPTER method the call actually crosses + `@EnableCaching`
  on a scheduled configuration class - an unactivated annotation is decoration (the
  un-`@Valid`'d-DTO class); self-invocation bypasses the proxy, so cache one layer out.
- timeouts: `.timeout(configuredDuration)` per external await with the tabled
  `onErrorResume(<declared outcome>)`; shutdown bounds are config payloads, never code.
- batching: `.bufferTimeout(maxSize, maxWait)` on the tabled loader; both bounds arrive from
  the config unit.
- keys (pool, codec size, page caps): operational values belong in the config artifact
  (non-code payloads section of `java-springboot`); the body reads what the unit's
  constructor receives.

# Tester law: deterministic, or it is not a gate
- No wall clock in a frozen test: no sleeps, no timing equality. Where a duration shapes
  behavior (backoff, timeout, flush), drive it with `StepVerifier.withVirtualTime` -
  deterministic by construction.
- `query-count` -> the decorator, flow once, assert `calls()` against the PB- bound;
  `config-key` -> load through the runtime loader, assert the bound is finite and positive;
  `status-code` -> saturate STRUCTURALLY: `Flux.range(1, permits + 1).flatMap(req -> post)`
  against the bounded guard and assert a refusal - bounded permits make it a theorem, not a
  race; `payload-size`/`queue-depth` -> the built artifact's own size/depth.
- The saturation case belongs to the slice when the surface is the guarded one (rule (p)
  family); per-unit gates may stub everything below the guarded method.
- Every asserted identifier comes from the task's tables; anything they omit is a plan hole
  you report - never a name harvested from delivered sources (the anti-convergence law).
