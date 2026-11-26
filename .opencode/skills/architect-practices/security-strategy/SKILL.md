---
name: security-strategy
description: "Use when designing a bounded context's security posture: threat model, authentication/authorization matrix, data classification, trust boundaries. Decides what must hold and names the capability that holds it - never the framework, file path, or schedule. Stack-agnostic by construction."
---

# Scope
One output: `blackboard/complete/security-spec-<slug>.json`.
Its shape is fixed by `.opencode/skills/architect-practices/security-strategy/references/security-spec.schema.json`
(`.github/skills` symlink; read once).

- Decide **what must hold**. Never **how**, **where**, or **when it is scheduled**.
- The architect maps tokens to mechanisms; the container builds.
- You load no stack skill and read no stack rule.

# Naming law
| Allowed | Forbidden | Owner of the forbidden form |
| --- | --- | --- |
| capability token, requirement, effect | framework, library, product, annotation or handler type names | tech-stack skill + architect |
| concept and field names from the inputs | file path, package, property key, `stage 0`, `T2-004`, agent name | architect, scaffold, orchestrator |

Capability tokens: lowercase kebab, 1-4 words, declared in `duties`, referenced elsewhere.

| Family | Shapes |
| --- | --- |
| Identity | `bearer-jwt-proof`, `device-credential-proof`, `mutual-tls-proof`, `service-credential-proof` |
| Decision | `role-check`, `scope-check`, `owner-scoped-query`, `tenant-scoped-query`, `device-binding-check` |
| Protection | `envelope-encryption`, `field-encryption`, `hashing`, `tokenization`, `append-only-history` |
| Key custody | `key-separation`, `credential-rotation`, `external-key-store` |
| Egress | `log-redaction`, `error-code-only`, `audit-event`, `metric-tag-bound` |
| Input | `boundary-validation`, `typed-deserialization`, `opaque-reference` |

A token is load-bearing only if one observation proves it false - else a wish.

# Procedure
Per bounded context: every entrant, asset and surface traces to an input file.

1. **Assets** — from `persistence.data_model` and the ubiquitous language.
2. **Entrants** — from `actors` and `external_systems`; add anonymous and internal-service callers.
3. **Surfaces** — the strategy's `surfaces` array IS the list (http, consumer, job, CLI,
   internal call). One matrix row per entry, `surface` copying `surfaces[].name` verbatim:
   that string locates the guarding unit at decomposition. None
   omitted, none merged, none invented - an unlisted surface is an `open_questions` entry.
4. **Crossings** — boundaries where data changes trust: persistence, another context, an external system, logs/metrics/traces, the export sink, an error response, a file.
5. **Capabilities** — what must hold at each crossing, then the `duties` handoff.

# Posture
- `default: deny` on every row; unauthenticated and not-permitted are distinct, and the difference never reveals existence.
- Fail closed: an unavailable decision source denies.
- Least privilege per principal, action and field.
- Identity is never inferred from a client-supplied field.
- Roles and scopes are maxima; a role never widens an ownership predicate.
- Elevation, delegation and impersonation are rows, never implied by a role name.
- Credentials state lifetime, renewal, revocation, clock-skew tolerance; revocation fails closed.
- Never weaken a control to fit an implementation: record the conflict as a risk.

# Matrix row contract
| Question | Field |
| --- | --- |
| who | `principal_ids` (must be declared in `principals`) |
| may this class of action | `roles`, `scopes` |
| may this instance | `ownership_rule` |

- `ownership_rule` is required whenever `client_supplied_ids` is non-empty: path variable, body key, message header, cache key, filename. `public` is an explicit answer, never an empty field.
- The predicate covers reads, writes, deletes, exports and aggregates over a collection.
- One tenant clause per source-of-truth concept, defined once, referenced by id; cross-tenant access is its own row and audit event.
- `decision_point` names the architectural layer and the component that decides - never a file.
- `test_duty` names three cases: permitted, denied, cross-owner. A row that constrains ids OWES it: the emit gate refuses a row no unit speaks.
- One trust domain, one credential home: rows authenticating the same principal class share one owning row's store; a sibling references it, never re-declares the population.

# Classification contract
Classify per concept, never per screen, endpoint or column.

- `public` → `internal` → `confidential` → `restricted`; `restricted` sets `secret: true`.
- `pii` is orthogonal to `secret`: PII owes retention/deletion, secrets custody/rotation.
- Per concept: `at_rest`, `in_transit`, `masking`, `retention`, `deletion`, and the three visibility fields.
- `restricted` is `forbidden` in logs, errors, exports; `confidential`/PII is `masked` unless the description demands more - then an audit event.
- Error responses: opaque reason code, human-safe message, correlation key. Nothing else.
- Log keys and metric tags are bounded sets; an identifier or user text as a label is a disclosure channel.
- Untrusted input is validated at the receiving boundary; deeper layers get typed values only.
- Name injection surfaces on the carrying row: deserialization, uploads, redirects, templates, queries, paths, archives.
- Key custody, rotation, and the separation of key access from data access are recorded.
- Identifiers never encode PII, and a public identifier is never a secret or an authorization token.
- Audit floor as event classes: authentication failure, authorization denial, privilege change, service credential use, bulk export.

# Duties
One duty per UNIQUE OBLIGATION: `spec_ref` names the primary rule, `covers` the ids
it also answers, `unit_kind` the shape from the reference file.

- ONE duty per unique (`capability`, `unit_kind`, `owner_context`): a rule sharing all
  three joins its `covers` - a repeated triple is refused. The same capability and shape
  in TWO contexts is TWO duties, each naming its `owner_context` (omit only when spanning).
- Every `authorization_matrix` row, invariant, in-row principal
  `credential_capability`, and PII `data_classification` row with masking
  other than `none` is discharged by at least one duty (`spec_ref` or
  `covers`). Prose agreement is not a claim; retention/deletion decide
  by value, masking not.
- Every `spec_ref` and `covers` id resolves to a declared entry.
- `unit_kind` is a shape (port, adapter, predicate, validator, redaction, audit, credential handling, key custody, classification rule), never a technology.
- Do not say whether a duty becomes code, configuration or schema: decomposition decides.

# The gate
`orchestrators/ddd.py` machine-checks the artifact before the phase may finish.

Refused on sight: a realization name, a non-deny `default`, an ownership-blind row, an
undeclared principal, an in-row credential discharged by no duty, an
`authentication: required` principal addressing no row, `restricted` data allowed
on any surface, a dangling `spec_ref` or `covers` id, a repeated (`capability`, `unit_kind`, `owner_context`)
duty triple, a malformed capability token, a `unit_kind` outside its enumeration, a declared
surface with no row, a `principals[].source` or `owner_context` no input declares, an unbacked risk.
