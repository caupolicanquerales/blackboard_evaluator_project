# task-decomposition-dag - DECISIONS LOG (operator history)

The post-mortems behind the invariants in `SKILL.md` / `QUICKREF.md`. This file is
NOT a planning input and never rides a session: dated war stories in runtime carriers
paid for themselves in re-read tokens every launch (2026-11-25 context audit); the
law lives in the carriers, the history lives here, one entry per incident, keyed by
the rule it produced. `draft_is_fresh` deliberately ignores this file (neither
normative carrier).

- rule (j)/(u) floor ownership, 2026-11-13: the execution strategy promised 5 step
  logs, phase 2 claimed none, the delivered code logged nothing, every gate stayed
  green because all validators checked consistency and none checked completeness.
  Layer 1: the floor is unconditional for every executable context. Layer 2: claims
  must be VERBATIM by exactly one stage-2 unit. 2026-11-20 V9: the per-context-dict
  floor spelling skipped the whole check - BOTH shapes flatten.
- rules (a)/(c)/(d)/(e) plan validity, 2026-11-16 seed-002 D1..D3: an intent said
  "also provide pom.xml" while the manifest was a different unit's duty; a runtime
  plan shipped with no config unit; a request DTO pinned a streamed collection while
  its frozen test posted an array body; `revision (>=1)` lived in prose only and four
  foreign fixtures fabricated the illegal literal. The emit validator refuses all
  four classes; prose-vs-table drift (the constructor-PROSE half) is refused both
  ways (rerun F2).
- rule (b) config unit + (h) config-surface completeness, 2026-11-16 rerun F5: a
  config-unit intent enumerated one document while its test pinned base + profiles;
  an enabled migration reader with no configured URL migrated an auto-detected
  throwaway store. 2026-11-19 R4: the record bound `devices` as a LIST while the
  config contract seeded `devices.secret-hash` as a scalar - no file can satisfy
  both, the credential store booted empty forever, and no per-unit gate saw it.
- rule (g) composition-root visibility, 2026-11-16 + 13:45: components outside the
  entry package's subtree were invisible to the boot; context-booting test slices
  IGNORE scan directives.
- rules (f)/(n) provider closure + one registration mechanism, 2026-11-16 rerun F4:
  injected types nobody provided; one component registered BOTH by stereotype and
  factory - which one wins was container precedence, not the plan.
- rule (i) stream egress, 2026-11-16 rerun F9: a published stream nobody subscribed
  to overflow-dropped every event behind green unit tests. 2026-11-24: a repair pass
  wrapped the publisher return in an envelope to silence the start-of-type regex -
  the check now reads the type wherever it sits; a shape dodge is an admission.
- rule (k) consumer closure / rule reachability, 2026-11-16: a service implementing
  the core business rule was constructed but pinned by NOBODY - zero callers,
  subscribers none; the rule executed zero times while the whole suite stayed green.
- rule (l) shared literals, 2026-11-16: one "first revision number" fact spelled in
  four contracts with three values (1 / 0 / >1); one connection string read by two
  runtime readers needing different URL shapes - no environment satisfies both.
- rule (m) signal branches, 2026-11-16: an egress method returned false on overflow,
  the producer proved it, the consumer's contract described only the happy path and
  discarded the signal - under burst the payload vanished while the entry answered
  ACCEPTED.
- rules (o)/(p) real substrate + request-path slice, 2026-11-16 PART II N1: the audit
  adapter mocked the database client; NOT NULL/PK population stayed unproven and
  EVERY production audit write failed with 186 tests green. contextLoads boots a
  context without sending a request; only the end-to-end slice makes entry, store and
  schema agree. 2026-11-19 R5: the slice shared one substitute across cases and
  asserted a global COUNT - test-runner order froze into the contract. 2026-11-24: a
  repair slice tabled "invalid payload 400, no row" against a use case that had
  already frozen "tag VALIDATION_FAILED, never drop" - one input, two contracts.
  2026-11-25 v7: the taught exemplar described the drive without the marker words
  (`end-to-end`/`integration slice`/`request-path`) the gate greps, four sessions
  imitated the prose faithfully, and the batch refused every inbound in the domain.
- rule (q)/(s) idempotency + value axis, 2026-11-16 PART II N4 / PART III G2: a
  retry indistinguishable from a correction minted spurious revisions; then rule (q)
  was HONORED as UNIQUE(device, metric, t) and that is exactly how the corrections
  rule died - the identity decided by omission. The identity-axis sentence must be
  spelled, and BOTH resend classes become test duties.
- rule (t) promised mechanisms, 2026-11-16 PART III G3: the strategy promised
  correlation "via context-propagation", the decomposition planned manual hand-passes
  AND tabled "no context-propagation library is used" - plan and strategy disagreed
  in prose, every gate green. Amend the promise to what ships, or schedule it.
- rule (u) no acknowledged outcome unmetered, 2026-11-16 PART III G4: a subscriber
  swallowed per-event errors AFTER the FAILED audit - failures durable in the store,
  invisible in every counter, floor "complete" because it only promised the happy
  path.
- rule (v) config artifact kind, 2026-11-16: a runtime YAML written as a flat list of
  dotted keys - the properties form smuggled into a structured document; boot-green
  (loaders flatten both), human-visible rot. Refused at plan time; the delivered-time
  half lives at the assembly gate as the argued exception to (r) (shape only, values
  untouched).
- rule (w) test-file ownership, 2026-11-17 drain: EVERY stage-1 task carried the
  production path; the tester - bound to write only at `path` - wrote test classes
  into the production tree; the import-closure guard stopped the drain at the first
  red close-out instead of billing a hundred sessions against it.
- rule (x) handler registration, 2026-11-17 drain: a handler forbidden annotation
  registration while its stack maps handlers ONLY by that marker - boot green, every
  inbound answered not-found; the (p) slice caught it, the per-unit gates could not.
- rule (y) security reach, 2026-11-18 probe: every duty CLAIMED, yet the entry unit
  had no guard on its path - the claim sat in an island the entry never pinned, the
  surface closed before its predicate existed, per-unit gates green.
- (y4)/(y5) root gate + per-kind entry, 2026-11-24 v4 fatal: two contexts each
  installed a root-wide admission and each cited the other's routes; repair round 1
  deleted a cross-context citation to satisfy z6, round 2 re-added it to satisfy
  pair identity - a gate-vs-gate ping-pong that burned both repair sessions. The
  law: ONE gate, owned by the first context; later contexts PIN, never re-install,
  never table a foreign address. 2026-11-25: the gate's foreign-address table is
  ENGINE-injected from the strategy surface table (`root_gate`), because a prose
  "tables no foreign address" law kept colliding with a join that demanded them.
- rules (z)/(z4)/(z5)/(z6) literal joins, 2026-11-19 drain: the consumer test pinned
  `telemetry.samples.validation_failed` while the facade's regenerated test pinned
  `telemetry.validation.failed` - two frozen spellings of one meter, the coder died
  3/3 on the contradiction (R1/R2); an entry-unit test cited a route literal its
  chain never served (R2); a list/child impossible pair (R4); a controller test
  imported a chain whose concrete bean the factory alone registered -
  NoSuchBeanDefinition at every slice boot while its twin, which pinned the manager,
  loaded fine (R3). All four classes became machine joins at emit; on 2026-11-25 the
  COPY burden moved off the session entirely (hydrate_batch: references in, tables
  out) after v7 showed a 16-call budget consumed by verbatim re-spelling.
- format-shape history: 2026-11-24 v4 the compact-only law lost to the model's
  prior (a format law that loses does not save tokens, it shaves requirements); v6
  the mixing ban met the law and the session DROPPED the (p) slice "for not knowing
  its compact form" - a contradiction between two laws is resolved in the CARRIERS,
  not by hoping the model picks the right one; v7 both shapes are honest, one per
  file, the (p) slice's lone stage-1 is the stated extra object.
- config channel, 2026-11-25 seed-002 v7: the ONE config unit belongs to the first
  context; a later context binding a key could not edit A's draft, could not fork a
  second unit, and the gaps file carried coordinates only - the honest session
  disclosed 4 orphaned rule-valued keys in prose no machine read; the validator
  replay found 26. The law now has a lawful home (gaps `config_paths`, engine
  append) and a refusal (coverage) behind it.
- carrier cost, 2026-11-20 context audit + 2026-11-25 bottleneck pass: the full
  contract rode every session (~9.5K skill tax per session; profiles+skill+map
  ~8K); the QUICKREF became the default read (AS13 word budget) and the engine
  pre-concatenates the four sections into ONE context file; 2026-11-25 moved the
  dated post-mortems here - history is for the operator, law is for the session.
