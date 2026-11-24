---
name: spring-performance-architect
description: "Architect-tier only (agent-planner-architect phase 2, when a performance-spec exists): maps performance tokens onto unit, layer, mechanism IDENTIFIER and config key. Planning facts only; bodies and test code live in the coder/tester tier."
---
# Scope
One row per spec duty; the mechanism column is what the intent spells VERBATIM (a paraphrase
is a citation, not a mapping). Where Boot/reactor/JDK supplies nothing the cell says **no
framework mechanism** and names the plan's OWN class - an honest none stops an invented
import. Bodies and test idiom: `tech-stack/spring-performance` (coder/tester tier).

# Token -> unit, layer, mechanism, key
| token family | unit_kind | layer | the identifier the INTENT must spell | key the config unit owns |
|---|---|---|---|---|
| admission-control / bounded-queue / bounded-buffer / backpressure / drop-policy | admission-control | interface | no framework mechanism: the plan's guard filter answering the declared `429`/`503` with `Retry-After` | the bound key |
| rate-limit | rate-limit-policy | interface/infra | no framework mechanism in Boot core: a plan-added permit guard (token-bucket shape); a provider library is a MANIFEST DUTY decision, never recall | rate + burst keys |
| bounded-semaphore | concurrency-guard | application | `Semaphore(int)` around the critical path, or Reactor `limitRate(n)` | the permits key |
| read-through-cache / negative-cache | cache-policy | application + infra | `@EnableCaching` + `@Cacheable` + a named `CacheManager` (`ConcurrentMapCacheManager` base; bounded sizing = the plan's wrapper); cache the MISS explicitly (no key = storm) | `spring.cache.type`, `spring.cache.cache-names` |
| bounded-attempts / idempotent-retry | retry-policy | application | Reactor `retryWhen(Retry.backoff(N, Duration))`, N config-bound; retries ONLY behind the (q)/(s) dedup identity, attempts metered | attempts + backoff keys |
| page-size-limit | pagination-rule | infrastructure | every list query binds `LIMIT :limit` from config - no unbounded `findAll()` on a request path | page-size + max keys |
| payload-limit | resource-ceiling | config + interface | `spring.codec.max-in-memory-size`; oversized answers the declared status | that key |
| pool-limit | resource-ceiling | config | reactive: `spring.r2dbc.pool.max-size`, `spring.r2dbc.pool.max-idle-time`, `spring.r2dbc.pool.max-acquire-time`; blocking plan: `spring.datasource.hikari.maximum-pool-size` + `server.tomcat.threads.max` | those keys |
| batch-load | batch-policy | application | Reactor `bufferTimeout(n, Duration)` / `window(...)` on the tabled loader | the batch-size key |
| bounded-window | admission-control | application | Reactor `windowTimeout(count, Duration)` / the plan's own reorder buffer over the declared window, spill answered by the drop-policy, never silent | the window count + duration keys |
| subscriber-limit | admission-control | interface | no framework mechanism in Boot core: the plan's own per-stream fan-in permit guard answering the declared status at the cap | the subscribers cap key |
| timeout-budget | timeout-policy | application/infra | `Mono.timeout(Duration)` per external await; `spring.lifecycle.timeout-per-shutdown-phase` | the timeout keys |
| counted proof (budget-observer) | budget-observer | shared/infra | no framework mechanism: the plan's OWN counting decorator wrapping the port (tabled in `ast_hints`) - what makes `query-count` provable | - |

# The wall-clock law (R5)
`measurement.kind` picks the proof surface: the decorator's number, a finite bound read by the
loader, the declared rejection status, the artifact's own size/depth. No clock kind exists on
purpose: load evidence beyond the deterministic contract is a risk-noted post-delivery
activity, never a frozen gate.

# One home, order, trap
Every kind in `ddd.PERFORMANCE_UNIT_KINDS` has a row; a duty this table cannot place is a spec
defect - report, never improvise. Order: guards -> decorators -> cache/pool/timeout
keys (CONFIG unit) -> the slice carries the saturation case. Bounds, statuses and the decorator are
JOIN KEYS to the claimed PB-/PI- ids ((y1) form): an unbounded default passes every unit test
and dies on first load.
