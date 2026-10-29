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

- `ast_hints`: target package, exact type name, kind (`record|class|interface|enum`), implements/extends, injected dependencies by type, method signatures with parameter and return types.
- `tdd`: at least one failing test case per public method, stated as `given / when / then`, plus the test class path.
- `constraints`: layer rules from `software-layering-patterns`, language/framework from the tech-stack skill in use.
- Acceptance: compile and test command that must pass.

## 4. Task Schema Definition

Output one JSON file per task, pushed to the Blackboard. Strict schema, no extra keys:

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
    "dependencies": [],
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
