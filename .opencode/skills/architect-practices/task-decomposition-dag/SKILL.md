---
name: task-decomposition-dag
description: Use when the architect agent splits a component into a dependency-ordered task queue (DAG) for the TDD + AST coder loop. Produces task JSON files for the Blackboard only.
---

# Task Decomposition DAG

## 1. Granularity & Scope Directives

- One component or one contract = one task.
- A task creates or modifies exactly one `path`, exports exactly one type.
- Split when a task needs more than one layer, more than 3 collaborators, or more than one public method group.
- Never create a task for a package, a folder, or "the whole module".
- Do not invent requirements; each task traces to the source spec.

## 2. DAG Dependency Rules

- Order: Value Objects -> Entities/Aggregates -> Repository/Outbound Ports -> Application Services/Use Cases -> Inbound Ports -> Controllers/Consumers -> Configuration.
- A task lists only direct `depends_on` task IDs. No cycles; reject the plan if one exists.
- A task may start only after all its `depends_on` tasks are complete.
- Independent tasks at the same level have empty or shared dependencies; do not chain them artificially.
- Tests are not separate tasks; each task carries its own acceptance criteria.

## 3. AST & TDD Metadata Injection

Every task payload must include:

- `ast_hints`: the unit's API contract table - namespace, implemented supertypes, collaborators pinned to producing task ids, and the COMPLETE signature (parameter and return types, spelled as the language's own declaration) of every boundary method the unit must provide, INCLUDING the methods of every implemented supertype. This table is the single API truth: the tester asserts only against it, the coder implements exactly it, and the queue validator rejects a task that implements supertypes while leaving the method list empty. Pure value objects may carry an empty method list.
- `tdd`: at least one failing test case per public method, stated as `given / when / then`, plus the test class path.
- `constraints`: layer rules from `software-layering-patterns`, language/framework from the tech-stack skill in use.
- Acceptance: compile and test command that must pass.

## 4. Task Schema Definition

Output one JSON file per task, pushed to the Blackboard. File name: `T-###-<domain-slug>.json` where the domain slug comes from `feature`. Strict schema, no extra keys:

```json
{
  "id": "T-001",
  "depends_on": [],
  "path": "relative/path/to/File.ext",
  "kind": "record|class|interface|enum",
  "layer": "domain|application|infrastructure|presentation|shared",
  "feature": "string",
  "export": "FullyQualifiedTypeName",
  "intent": "one sentence",
  "ast_hints": {
    "package": "string",
    "implements": [],
    "dependencies": [{"type": "FullyQualifiedContractType", "task_id": "T-###"}],
    "methods": [{"signature": "string", "returns": "string"}]
  },
  "tdd": {
    "test_path": "relative/path/to/FileTest.ext",
    "cases": [{"method": "string", "given": "string", "when": "string", "then": "string"}]
  },
  "acceptance": "build/test command"
}
```

Rules: `id` unique and sequential; `depends_on` references existing IDs only; `path` is relative to project root; `layer` must match the file's package layer.

## 5. Wiring Contract Directives

- **Collaborator Pinning**: every entry in `ast_hints.dependencies` names the exact contract type and the `id` of the task that produces it, e.g. `{"type": "FQN.Port", "task_id": "T-004"}`. The producing task must appear in `depends_on`. A dependency with no producing task is a plan error. **The producing task's `ast_hints.methods` must spell every member its consumers touch (accessors included): a type other tasks pin as a collaborator while its own table is empty is a plan error** - consumers would have to improvise its surface, and two frozen artifacts disagree.
- **Type Scope**: collaborators are typed by the port or interface in the layer that owns them, never by an adapter or implementation class. Application and domain tasks may reference only domain and application types; adapters are referenced only by configuration tasks.
- **Canonical Constructors**: each class declares exactly one constructor. `ast_hints.methods` lists its parameters in order, each with the type and the collaborator task it is pinned to. Two parameters of the same type or two bindings of the same property are a plan error.
- **Configuration Bindings**: every operational value (timeouts, windows, capacities) is read through a single configuration-binding task that owns the property key and type. Each property has exactly one binding task; other tasks receive the bound type, never the raw property or a literal default.
