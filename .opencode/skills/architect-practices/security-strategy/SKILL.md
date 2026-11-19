---
name: security-strategy
description: "Use when designing a bounded context's security posture: threat model, authentication/authorization matrix, data classification, trust boundaries. Decides what must hold and names the capability that holds it - never the framework, file path, or schedule. Stack-agnostic by construction."
---

# Scope
One output: `blackboard/complete/security-spec-<slug>.json`.
Its shape is fixed by `.opencode/skills/architect-practices/security-strategy/references/security-spec.schema.json`
(the `.github/skills` symlink serves the same file to Copilot; read it by that full path, once).

- Decide **what must hold**. Never **how**, **where**, or **when it is scheduled**.
- The architect maps your tokens to mechanisms with the tech-stack skill; the container builds the project.
- You load no stack skill and read no stack rule: reading those files is what puts framework idioms in a requirements context.

# Naming law
| Allowed | Forbidden | Owner of the forbidden form |
| --- | --- | --- |
| capability token, requirement, effect | framework, library, product, `@Annotation`, `FooController` | tech-stack skill + architect |
| concept and field names from the inputs | file path, package, property key, `stage 0`, `T2-004`, agent name | architect, scaffold, orchestrator |

Capability tokens: lowercase kebab, 1-4 words, declared in `duties`, referenced elsewhere.

| Family | Shapes |
| --- | --- |
| Identity | `bearer-jwt-proof`, `device-credential-proof`, `mutual-tls-proof` |
| Decision | `role-check`, `scope-check`, `owner-scoped-query`, `tenant-scoped-query` |
| Protection | `envelope-encryption`, `field-encryption`, `hashing`, `tokenization` |
| Key custody | `key-separation`, `credential-rotation`, `external-key-store` |
| Egress | `log-redaction`, `error-code-only`, `audit-event`, `metric-tag-bound` |
| Input | `boundary-validation`, `typed-deserialization`, `opaque-reference` |

A token is load-bearing only if one observation can prove it false; otherwise it is a wish.

# Procedure
Per bounded context, in order. Every entrant, asset and surface must trace to an input file; anything the inputs do not declare is an `open_questions` entry, never an invention.

1. **Assets** — from `persistence.data_model` and the ubiquitous language.
2. **Entrants** — from `actors` and `external_systems`; add anonymous and internal-service callers.
3. **Surfaces** — the strategy's `surfaces` array IS the list (http, consumer, job, CLI,
   internal call). One matrix row per entry, `surface` copying `surfaces[].name` verbatim:
   that string is how the decomposition finds the unit that must carry the guard. None
   omitted, none merged, none invented - an unlisted surface is an `open_questions` entry.
4. **Crossings** — every boundary where data changes trust: persistence, another context, an external system, logs/metrics/traces, the export sink, an error response, a file.
5. **Capabilities** — what must hold at each crossing, then the `duties` handoff.

# Posture
- `default: deny` on every row; unauthenticated and not-permitted are distinct effects and the difference never reveals existence.
- Fail closed: an unavailable decision source denies.
- Least privilege per principal, action and field.
- Identity is never inferred from a client-supplied field.
- Roles and scopes are maxima; ownership predicates are the binding limit. A role never widens ownership.
- Elevation, delegation and impersonation are rows, never implied by a role name.
- Credentials state lifetime, renewal, revocation and clock-skew tolerance as requirements; revocation fails closed.
- Never weaken a control to fit an implementation: record the conflict as a risk.

# Matrix row contract
| Question | Field |
| --- | --- |
| who | `principal_ids` (must be declared in `principals`) |
| may this class of action | `roles`, `scopes` |
| may this instance | `ownership_rule` |

- `ownership_rule` is required whenever `client_supplied_ids` is non-empty: path variable, body key, message header, cache key, filename. `public` is an explicit answer, never an empty field.
- The predicate covers reads, writes, deletes, exports and aggregates over a collection.
- One tenant clause per source-of-truth concept, defined once and referenced by id; cross-tenant access is its own row with its own audit event.
- `decision_point` names the architectural layer and the component that decides - never a file.
- `test_duty` names three cases: permitted, denied, cross-owner (a valid identifier owned by someone else, which must be refused).

# Classification contract
Classify per concept, never per screen, endpoint or column.

- `public` → `internal` → `confidential` → `restricted`; `restricted` sets `secret: true`.
- `pii` is orthogonal to `secret`: PII owes retention and deletion, secrets owe custody and rotation.
- Per concept: `at_rest`, `in_transit`, `masking`, `retention`, `deletion`, and the three visibility fields.
- `restricted` is `forbidden` in logs, errors and exports. `confidential`/PII is `masked` unless the description demands more, and then it earns an audit event.
- Error responses: opaque reason code, human-safe message, correlation key. Nothing else.
- Log keys and metric tags are bounded sets; an identifier or user text as a label is a disclosure channel.
- Untrusted input is validated at the boundary that received it; deeper layers receive typed values only.
- Name injection surfaces on the row that carries them: deserialization, uploads, redirects, templates, queries, paths, archive entries.
- Key custody, rotation, and the separation of key access from data access are recorded. A reader that automatically holds the key has no separation.
- Identifiers never encode PII, and a public identifier is never a secret or an authorization token.
- Audit floor as event classes: authentication failure, authorization denial, privilege change, service credential use, bulk export.

# Duties
One row per duty. `spec_ref` names the rule it discharges; `obligation` states what must hold; `capability` is the token; `unit_kind` picks the shape from the closed set in that reference file.

- Every `authorization_matrix` row and every `invariant` is discharged by at least one duty.
- Every `spec_ref` resolves to a declared entry.
- `unit_kind` is a shape (port, adapter, predicate, validator, redaction, audit, credential handling, key custody, classification rule), never a technology.
- Do not say whether a duty becomes code, configuration or schema: that is decomposition.

# The gate
`orchestrators/ddd.py` machine-checks the artifact before the phase may finish.

Refused on sight: a realization name, a non-deny `default`, an ownership-blind row, an
undeclared principal, `restricted` data allowed on any surface, a rule discharging no duty,
a dangling `spec_ref`, a malformed capability token, a `unit_kind` outside its enumeration,
a declared surface with no row, a `principals[].source` or `owner_context` no input declares, an unbacked risk.

Nothing above is repeated as a checklist: the gate is the check, and a restated rule is
only another place for the two to disagree.
