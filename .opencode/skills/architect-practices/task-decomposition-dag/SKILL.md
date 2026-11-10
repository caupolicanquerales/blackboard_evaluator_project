---
name: task-decomposition-dag
description: Use when the architect agent splits a component into a dependency-ordered task queue (DAG) for the TDD + AST coder loop. Produces task JSON files for the Blackboard only.
---
# Granularity
One component/contract = one task: one `path`, one exported type. Split above 1 layer, 3 collaborators, or 1 method group. Never tasks for packages/folders/modules; no invented requirements - trace to the spec.
# DAG
Order: value objects -> aggregates -> outbound ports -> use cases -> inbound ports -> controllers -> configuration. `dependsOn` = direct only; cycles => reject. Siblings share or omit deps. Every unit = stage-1 test task + stage-2 code task (engine mirrors stage 3).
# Payload contract (stage-1/2 tasks)
- `ast_hints` = THE API table: `package`; `implements` supertypes; `dependencies` [{type,task_id}] pinned to producers (a pin without one is a plan error; the producer must also be in `dependsOn`); `methods` [{signature,returns}] spelling EVERY boundary method the unit provides - all implemented supertype methods + every accessor a pinned consumer touches; returns "" when none; value objects may list []. Testers assert ONLY this table; the validator refuses implements-without-methods: an untabled collaborator makes consumers improvise contradictory signatures.
- `tdd`: >=1 failing case per public method as given/when/then + test class path.
- `constraints`: layer rules + language/framework from the active tech-stack skill.
# Fields
id (T<stage>-### from the prompt), path (relative to the domain project root), kind, layer, feature, export (FQN), intent (implementation-ready: context, unit, invariants, error cases, externalized config keys; never fallback literals), dependsOn, project (slug).
# Emission
ALL tasks in ONE JSON array => `python3 <runner> --emit <file>`; on rejection fix every listed error in one rewrite, re-emit once. Never write `blackboard/queue` directly; never reuse ids.
