---
name: domain-context-mapping
description: "Use after domain-boundary-discovery to build and validate the DDD context map, choose integration relationships and boundary protection, map cross-boundary flows, and assemble the final Domain Boundary Analysis handoff for an architect agent. No code."
---

# Domain Context Mapping & Handoff

Parent: [[java-architect-practices]]

## Purpose

Turn a boundary draft into a validated strategic DDD map:

- Context relationships and integration direction.
- Boundary protection and model-leak prevention.
- Cross-boundary flows and consistency expectations.
- A final **Domain Boundary Analysis** artifact for an architect agent.

Analysis only; no code, APIs, schemas, or infrastructure.

## Prerequisite

Use `domain-boundary-discovery` first for the boundary draft (summary, language, subdomains, contexts, invariants, events, questions). If no draft exists, load that skill and create one. Never invent contexts to skip discovery.

## Workflow

### 1. Confirm inputs

Every context must have a responsibility, language, owned invariants, and source-of-truth concepts. If an invariant has no owner or two owners, return to discovery.

### 2. Identify interactions

For each pair of contexts ask:

- What information or behavior must cross the boundary?
- Who initiates it, and who is upstream/downstream?
- What must never leak across the boundary?
- Can information arrive later, or must it be consistent immediately?

If nothing must cross, the contexts are **separate ways**.

### 3. Choose the relationship pattern

| Pattern | Use when | Watch for |
|---|---|---|
| Partnership | Two areas co-evolve with mutual dependency. | Tight coupling; needs coordination. |
| Shared kernel | A small explicitly shared model is unavoidable. | Keep minimal; name what is shared. |
| Customer-supplier | Downstream depends on upstream with negotiated needs. | Upstream must honor needs. |
| Conformist | Downstream accepts upstream's model without influence. | Downstream loses modeling freedom. |
| Anticorruption layer | Downstream must protect its model from upstream. | Translation cost and ownership. |
| Open host service / published language | Upstream serves many consumers with a stable contract. | Versioning and compatibility. |
| Separate ways | No meaningful integration is needed. | Avoid hidden coupling. |

Choose the weakest relationship that satisfies the business need.

### 4. Define direction and protection

For each relationship record:

- Upstream and downstream; direction of information flow.
- Information exchanged and its meaning in each context.
- Translation/protection at the boundary.
- What must not cross (internal IDs, model internals, local rules).
- Consistency: immediate inside a context, eventual across contexts.

### 5. Map cross-boundary flows

For each end-to-end business process that spans contexts, record:

- Trigger and business outcome.
- Contexts involved, in order.
- Where state changes and who owns it.
- Failure or compensation points.
- What remains temporarily inconsistent, and for how long.

Do not turn flows into technical sequence or message design.

### 6. Validate

- Every interaction has a relationship and direction.
- No invariant or source of truth is duplicated.
- Every shared item is deliberate and named.
- Relationships reflect business power, not team convenience.
- Cross-boundary flows have an explicit consistency expectation.
- No coupling merely because contexts share an entity name.
- Core subdomains are not buried under generic integration concerns.

### 7. Assemble the final artifact

Carry forward the boundary draft, then add mapping and handoff sections. Use plain text for the overview; no diagram code.

```markdown
# Domain Boundary Analysis

## 1-4. Summary, language, subdomains, bounded contexts
(carry forward from the boundary draft)

## 5. Context map
| Upstream | Downstream | Relationship | Direction | Exchanged information | Boundary protection |
|---|---|---|---|---|---|

### Cross-boundary flows
| Business process | Contexts involved | Consistency expectation | Notes |
|---|---|---|---|

### Boundary overview (plain text)
- <Context A> --> <Context B>: <what flows and why>

## 6. Boundary rationale
- Why these boundaries and not adjacent alternatives:
- Rejected splits/merges and the reason:
- Weakest/riskiest boundaries:

## 7. Assumptions, ambiguities, and open questions
| Item | Type | Impact on boundaries | Confidence |
|---|---|---|---|

## 8. Handoff notes for the architect agent
- Modeling focus (core subdomains first):
- Areas needing deeper investigation:
- Coupling or model-leak risks:
- What must remain outside the next analysis:
```

### 8. Handle gaps

- Mark undetermined relationships as `Open question` and state the decision needed.
- Mark conflicting invariant ownership and return it to discovery.
- If the description is too thin, produce the draft and state that mapping is provisional.

## Handoff contract

The architect agent needs the context list with responsibilities and out-of-scope boundaries, terms that must not be merged, invariants and source-of-truth ownership, integration direction and protection per boundary, cross-boundary flows with consistency expectations, and explicit unknowns.

Stop at this artifact. Do not proceed to tactical design, code, packages, databases, or deployment topology.

## Constraints

- Analysis only; no application code.
- Never equate a bounded context with a microservice, module, or package.
- Never omit the context map when more than one context exists.
- Never assign an invariant to two contexts.
- Always state confidence and unresolved questions.
- Use domain language for context and relationship names.
