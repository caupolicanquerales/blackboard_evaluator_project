---
name: spring-ai-architect
description: "Architect-tier only (agent-architect phase 2, when an ai-spec exists): maps the closed AI tokens onto unit, layer, mechanism IDENTIFIER and config key. Planning facts only; adapter bodies and stubs live in the coder/tester tier. The model is never a gate input: proofs bind to the port."
---
# Scope
The CLOSED token set the AI spec gate enforces. The adapter is the ONE class importing
`org.springframework.ai.*`; everything else stays framework-free. INVOCATION MODE IS A PLAN
FACT: `.call()` blocks, `.stream()` is reactive - the unit's table names the RUNTIME (WebFlux
default; MVC takes the blocking pair), never the coder. Bodies: `tech-stack/spring-ai`.

# Token -> unit, layer, mechanism, key
| token | unit_kind | layer | the identifier the INTENT must spell | key the config unit owns |
|---|---|---|---|---|
| prompt-contract | prompt-contract | app + infra | Java `PromptContract` type holding the FIVE tabled members (version, role, placeholders, output-schema ref, refusal); `ChatClient.prompt()` ONLY through it; template files: no writer | - |
| structured-output-guard | output-validator | infrastructure | `BeanOutputConverter<T>` (or `.call().entity(T.class)` - blocking, wrapped per §Reactive); violation -> one re-ask then the declared refusal - never raw-parse | the re-ask bound |
| context-budget-cap | context-budget | application | no framework mechanism: the plan's assembler (selection + truncation tabled); ceiling on `ChatOptions` | `spring.ai.<provider>.chat.options.*` + assembly bound |
| fallback-model-route | fallback-policy | infrastructure | `Mono.timeout(Duration).onErrorResume(<declared route>)`; no circuit-breaker in Spring AI core: **no framework mechanism** - a plan selector or manifest-duty provider | timeout + route keys |
| retrieval-scope-guard | retrieval-adapter | domain/app + infra store | `VectorStore` returns IDENTIFIERS; the store re-checks `permits(...)` before hydrating; RAG over unreadable rows is IDOR | - |
| tool-call-guard | tool-guard | infra + application | `@Tool` methods (as `ToolCallback`s) DELEGATE to the existing use case - no second implementation, no ambient authority; enumerated or refused | the allow-list key |
| eval-golden-set | eval-harness | shared (test artifact) | no framework mechanism: the plan's golden-set resource + assertion class (tabled in `ast_hints`), run against the STUB port | - |
| memory-boundary | memory-adapter | infrastructure | `ChatMemory` + `MessageWindowChatMemory` (sliding-window); **rolling-summary: no framework mechanism** - the plan's compaction step over `ChatMemory` + store; **semantic-episodic: no framework mechanism** - memory reads via `VectorStore` behind the scope guard; repo per tier: `InMemoryChatMemoryRepository` (session), the plan's durable store | window + retention + summary-interval keys |
| offline-model-port | model-port-adapter + offline-stub | port + adapter + test support | `ChatPort`/`EmbeddingPort` tabled in `ast_hints`; adapter over `ChatClient`/`EmbeddingModel`; the TEST profile binds a `@Primary` STUB port; no boot reaches live | provider keys absent in the test document |
| token-cost-cap | context-budget | app + config | per-flow total on the plan's budget class; over-budget behavior declared; per-call ceiling via `ChatOptions` | the flow-budget key |
| incremental-progress-stream | stream-delivery | port (events) + interface (transport) | port returns tabled `Flux<ProgressEvent>` (chunks THEN terminal); handler answers `Flux<ServerSentEvent<T>>` at `@GetMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)` (MVC: `SseEmitter`); test = stub counter shows chunks before completion | idle-timeout key |
| agent-handoff | orchestration-router | app + infra | no framework mechanism: the plan's `Router` enumerating every edge (role -> role, envelope tabled), dispatching via the receiver's port | - |
| loop-budget-cap | loop-governor | application | no framework mechanism: the plan's `LoopGovernor` counts turns and breaks at the bound with the named outcome; a reactive cycle bounds itself `Flux.take(n)` / `takeUntil(done)`, blocking hops per mode; proof = stub-call-count | the max-turns key |
| human-approval-gate | approval-gate | app + interface | no framework mechanism: propose/approve/deny persisted, execution ONLY from approved (rule (n)), denial first-class; splits the `@Tool` effect | resume channel + retention keys |

# Build coordinates (stage-0 manifest duty; BOM owns versions)
`spring-ai-bom` (import) + `spring-ai-starter-model-<provider>` (compile) when a model-port adapter is emitted; an unlisted coordinate kills the first red compile.

# The trap
Stage-1 asserts the port's contract, not the model's wording; handoff without
`loop-budget-cap` is the AI unbounded queue (gate-refused).
