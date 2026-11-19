---
name: spring-ai
description: Coder/tester composition tier for AI units (reached by path from java-springboot §AI units and java-junit5 §AI tests): port adapters, offline stub, validation, memory, multi-agent bodies, golden-set tests.
---
# The one import law
Coder/tester of any AC-/AM- unit. The adapter is the ONLY class importing
`org.springframework.ai.*`; `ChatPort` / `EmbeddingPort` (plan interfaces, tabled in
`ast_hints`) speak the context's types - a use case holding a `ChatClient` cannot be
stubbed, which is the entire point.

# Shared core - both runtimes
- generation: the prompt contract is a JAVA type (`PromptContract`: the five tabled members - version, role, placeholders, output-schema ref, refusal), assembled as `chatClient.prompt().system(contract.system()).user(contract.render(vars))`, `.options(...)` ceilings from configured values - never literals. Never a `resources/*.st` template file: no writer on this board (plan hole - report). The TERMINAL comes from the planned runtime: pick EXACTLY ONE block below; mixing them is the Q29 bug class at the model hop.
- structured output: `BeanOutputConverter<T>` types the answer; failure takes the TABLED
  path: one re-ask inside the attempt budget, then the declared refusal. Model text is never
  raw-parsed, logged, or echoed into an error body.
- embeddings: `EmbeddingPort` over `EmbeddingModel.embed(...)`; batch bounds from config.
- PLAN-HOLE law: a class/key the tables do not carry is reported, never harvested from
  delivered sources or memory (anti-convergence).
- memory: the repo follows the spec's statefulness (`InMemoryChatMemoryRepository` for
  session; the plan's tabled durable store; no memory object at all for none), and the
  role's `memory_technique` picks the body:
  - `sliding-window`: `MessageWindowChatMemory.builder().chatMemoryRepository(repository)
    .maxMessages(window)` - window from config; older turns dropped.
  - `rolling-summary`: no framework mechanism - the plan's compaction step. When turns pass
    the configured summary interval, the compactor is invoked THROUGH `ChatPort` (the
    summarization is a model call too - `ChatClient` never appears outside the adapter, not
    even here), the condensed summary persists to the durable store beside the retained
    recent window. Test: compaction fires at the threshold, once per crossing
    (`stub-call-count`).
  - `semantic-episodic`: embed turns/facts via `EmbeddingPort` into `VectorStore` WITH the
    owner/tenant metadata; retrieval takes top-k from config but MUST pass the same
    `permits(...)` predicate as the human path before hydrating context - the scope guard
    lives in the flow, not behind the store. Test: seed memories for two owners, query as
    one, assert the foreign owner's memories are absent (`deterministic-count`).
- tools: `@Tool` methods DELEGATE to the same use case the human path calls - no second
  implementation, no ambient authority; registration enumerates the allowed operations
  (rule (n) applies to tool lists too).
- Router (`agent-handoff`): plan-owned, topology is DATA - enumerated edge table (from-role,
  to-role, envelope type), ONE dispatch method calling the RECEIVER'S PORT; an un-listed edge
  is refused at the router; ports only, never a client. Envelopes are value objects with
  their own stage 1/2/3 triple.
- Governor (`loop-budget-cap`): counts turns at the increment, bound from config; the
  bounding SHAPE comes from the block below. The cycle-break is a first-class result
  (persisted, metered), never `null`, never an endless loop.
- Approval gate (`human-approval-gate`): the high-impact tool SPLITS: `proposeAction(...)`
  persists action + `awaiting_approval`, returns its id; `approve(id)`/`deny(id)` move the
  state ONLY through the declared resume channel; EXECUTION runs solely from approved (one
  use case carries the effect). Retention/expiry is a config key.

# Execution and test shapes, split by the planned runtime (WebFlux default; an MVC plan
# takes the blocking pair)
A copy across the blocks does not belong: a scheduler hop on a servlet thread costs latency
for nothing; an unwrapped blocking call on an event loop is the `block()` defect in a model
costume. The import law is shared, the runtime is NOT.

### Reactive (WebFlux - event-loop threads)
- streaming text: `chatClient.prompt()...stream().content()` returns `Flux<String>`;
  `.timeout(configuredDuration)`, `.take(maxTurns)`, `.takeUntil(done)`,
  `.onErrorResume(<declared route>)` compose IN-CHAIN - the governor bounds cycles this way.
- typed answers: the SDK terminal `.call()` BLOCKS, so move it off the loop:
  `Mono.fromCallable(() -> chatClient.prompt()...call().entity(Answer.class))`
  `.subscribeOn(Schedulers.boundedElastic())` (embeddings wrap the same way); boundedElastic
  is a bounded resource - its sizing is a performance-plan duty.
- NEVER `block()`, `blockFirst()` or `blockLast()` to skip the wrapping. An in-chain timeout
  cannot see a hop that is not a reactive type: the wrapped call's own deadline is the
  provider client's request-timeout key (config unit, tabled).
- delivery (`stream-delivery`): map `.stream().content()` chunks into the tabled
  `ProgressEvent` - events built as `ServerSentEvent.builder(chunk).event("progress").build()`
  - and CONCATENATE the terminal completion after them (`Flux<ProgressEvent>` out of the
  port, `Flux<ServerSentEvent<T>>` at the handler); a governor loop emits one progress event
  per turn before the break result. Test: chunks THEN terminal, never a blocked call -
  `StepVerifier.create(port.deliver(req)).thenConsumeWhile(e -> !e.terminal())
  .expectNextMatches(ProgressEvent::terminal).verifyComplete()`.
- tests: `StepVerifier`; where a duration gates the step, `StepVerifier.withVirtualTime`
  (deterministic - the wrap adds no clock). Drive the stub until the break, assert calls <=
  maxTurns + the cycle-break outcome. No sleeps, no timing equality.

### Blocking (Servlet / Spring MVC - request/worker threads)
- direct calls: `chatClient.prompt()...call().entity(Answer.class)` (typed) or
  `...call().content()` (text) on the request/worker thread; embeddings call `embed(...)`
  directly; `spring.threads.virtual.enabled=true` gives cheap blocking threads when tabled.
  No scheduler hop is needed and one costs latency for nothing.
- deadlines: the provider client's connect/read timeout keys (config unit); on expiry the
  SDK throws and the fallback is ordinary
  `try { call } catch (<declared failure>) { return <declared route>; }` - never a swallowed
  exception.
- governance: a plain `turns.incrementAndGet() > max` at the cycle increment returning the
  declared break outcome; approval waits are already asynchronous state (the proposal
  table), never a blocked or joined future.
- delivery (`stream-delivery`): push from the worker - `emitter.send(SseEmitter.event()
  .name("progress").data(chunk))` per turn, terminal event last, then `emitter.complete()`
  (failure paths: `completeWithError`); or the spec's declared POLLED-COMPLETION posture
  against the durable store - whichever the plan tabled. Test: `assertThat` the event
  sequence has chunks before the terminal, and a second send-after-complete throws.
- tests: direct JUnit 5 + AssertJ (`assertThat(...)`, `assertThrows(...)`) against the stub
  port - no reactive verifier or reactor-test scaffolding; a servlet gate importing the
  other block's test vocabulary tests the wrong runtime.

Testers, both blocks: handoff -> un-listed edge refused + receiver stub count; approval ->
submit (pending, effect NOT run), approve (ran ONCE - the counter proves it), deny (refusal),
foreign resume-id refused.

# The offline stub (offline-model-port) - every gate tests against THIS, both runtimes
- The slice-support contract registers the stub FOR THE PORT:
  `@TestConfiguration static class StubChatPortConfiguration { @Bean @Primary ChatPort stubChatPort() { return new StubChatPort(); } }`
  - it records calls (`AtomicInteger`) and returns queued canned answers (the golden set).
  Live provider keys are ABSENT from the activated test document: a test that can reach the
  network means the design failed.
- BEAN PRECEDENCE IS A CONTRACT, NOT A HAPPENING: the production adapter IS registered
  (wiring unit, rule (n)) - a second `ChatPort` with no precedence decision is
  `NoUniqueBeanDefinitionException` at every boot. Default: **the stub carries `@Primary`** -
  it wins explicitly, the production unit never has to know (making two frozen contracts
  coordinate is the failure (z) prevents). Alternative: `@ConditionalOnMissingBean(ChatPort.class)`
  on the production bean, ONLY when the plan tabled it there; one side carries the marker,
  decided AT PLAN TIME, named in both intents.
- `@TestConfiguration` GOTCHA: a TOP-LEVEL `@TestConfiguration` is NOT picked up silently -
  only a NESTED class or an `@Import`ed one joins the context; an un-imported stub boots the
  production adapter and reaches live - an offline-port violation disguised as green wiring.
  Prove the binding: one frozen case asserts the resolved `ChatPort` bean IS the stub
  (`isInstanceOf`) - witnessed, not assumed.
- Golden-set eval: versioned resource (input + expected properties) + `@ParameterizedTest`
  against the stub: schema holds / refusal fires / budget respected - property assertions,
  never wording equality. `stub-call-count` -> the counter; `schema-validation` -> a canned
  malformed answer returns the refusal; `config-key`/`payload-size` -> the runtime loader and
  the prompt's assembled size.
