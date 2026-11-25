---
name: typescript-nestjs
description: "Stack constraints for planning and emission; technology names and versions come from here."
---
# Stack facts
Node 20 LTS; TypeScript 5 strict; NestJS 10; npm; layout: `src/<feature>` modules with controller/service/(port) + `src/infrastructure` adapters, `test/` e2e via supertest.
# Conventions (planning)
Constructor injection with provider tokens for interfaces (`@Inject(TOKEN)`); DTOs as classes with class-validator decorators at boundaries (whitelist:true pipe), never entities serialized to responses; domain errors thrown as typed exceptions, mapped by an ExceptionFilter; async everywhere - no sync fs/crypto in request paths; configuration via ConfigModule `forRoot()` + typed ConfigService readers with code-side defaults (no raw `process.env` in business code); cross-module deps via exports/imports, no provider duplication.
# Persistence & test
TypeORM (decorators, migrations as `<Tag><Timestamp>.ts` expand-only) or a declared driver per strategy; DatabaseModule isolated from domain; jest unit tests + supertest e2e spec `test/app.e2e-spec.ts` (`npm run test:e2e` is the boot gate); interfaces bound via `{provide, useClass}` thin adapters. Migration RUNNER config belongs in the DataSource the app constructs (`migrations: [path]` resolved via ConfigService) or `ormconfig` the tooling CLI loads - never a key in an unread file; the configured glob must match where the plan's migration scripts physically live (`src/migrations`), and the boot gate fails if the two disagree.
# Observability & audit design (concrete side of the strategy's `observability` object)
Logs: Nest `Logger` (JSON transport configured in the module/config unit), one logger per owning class, no `console.log`. Export for external tools (the strategy's `observability.export`): the contract sink is an NDJSON file written by the logger transport (pino `transport.target: pino/file` with `destination`, or the configured Logger serializers - keys carried by ConfigService: path, rollover), tailed by Filebeat/Fluent Bit/Vector into Elasticsearch; the app writes files, the platform ships them. Direct transports (elasticsearch transport, OTLP exporter) ONLY when the description names the endpoint, off under the boot test so it passes offline. Correlation: one middleware/interceptor unit generating/adopting `requestId`, carried via AsyncLocalStorage so async paths keep it; the id is ALSO an explicit audit-record field, never only ambient context. Audit trail: application-port token (`@Inject(TOKEN)`) whose DTO shape is tabled in ast_hints (actor, action, outcome, timestamp, correlation id) + a TypeORM append-only entity + migration owned by the database step; same-transaction vs best-effort per the invariant. Metrics via a thin counting provider (prom-client only if the description asks), bounded labels only. Test surfaces: jest spies on the Logger capturing structured arguments, the audit port's recording provider bound with `{provide, useClass}` (assert every tabled field), counting-provider totals; assertions on rendered strings are forbidden.
# Build/run
`npm run build` (nest tsc), start:dev watch; package-lock committed; engines.node pinned.
# Record keys (board `ast_hints` vocabulary -> this language)
`package` = the module's source path (e.g. `src/intake`); `implements` = the TypeScript
`implements` interface names (the port contracts), `[]` for plain classes;
`methods[].signature` is the TS method header with declared types; `config[].path` = dotted
ConfigService keys;
`routes[].method`/`path` = the HTTP verb and full path of the `@Controller` + `@Get`/`@Post` decorator pair; `path` = the `.ts` file. A build `coordinate` = the npm package name
with its pinned version spelled EXACTLY as `package.json` carries it (`dependencies` or
`devDependencies` key), and `missing_coordinates` / the ONE manifest's intent use that same
spelling.
# Scaffold facts (the strategy phase's ONLY dependency source)
Scaffold generator: Nest CLI (mcp-server-nestjs). Spell dependencies as its GENERATOR-NATIVE
ids - `@nestjs/core`, `@nestjs/common`, `@nestjs/platform-express`, `@nestjs/config`,
`@nestjs/testing`, `rxjs`, plus the driver/ORM packages the persistence strategy names -
NEVER npm aliases or bare names the CLI cannot resolve. The list MUST include
`@nestjs/testing` (the test artifact); e2e lanes add `supertest`. The generator's default
major is a trap - the strategy's pin wins; the stage-0 re-pin fallback keeps package.json
equal to it.

# Worked draft example
TWO honest unit records for THIS stack - the planner brief lifts them
verbatim; the shape is law everywhere, these spellings are NestJS/TypeScript's
only. Unit 21 is the OWNER (inbound surface, its own serves/owns literals, its
claimed step). Unit 22 is the CONSUMER: `uses_meters`/`uses_routes`/`claims_steps`
reference 21's literals - never a re-spelling; the engine hydrates the canonical
entries at claim. Unit 21 expands to
T1-021/T2-021/T3-021 with the IDENTICAL ast_hints pair (the engine mirrors it):
```json
[
 {"n": 21, "project": "telemetry", "layer": "interface", "feature": null,
  "dependsOn": {"test": ["T0-001", "T1-020"], "code": ["T0-001", "T2-020"]},
  "test": {"path": "test/intake/ingress.controller.spec.ts",
           "export": "IngressControllerSpec",
           "intent": "End-to-end request-path slice drives POST /ingress/packets AT the lookup: owner's packet appended (AZ-02 permitted); a VALID packet bearing a foreign tenant's id REFUSED 403 (cross-owner); duplicate key a no-op; assert the appended row, the refused status, the counted meter."},
  "code": {"path": "src/intake/ingress.controller.ts",
           "export": "IngressController",
           "intent": "Unit IS the surface 'packet ingest HTTP inbound': AZ-02 tenant-scoped-query enforced at the lookup - findByTenant scoped find on the injected SampleStore provider token, a foreign tenant's packet never fetched, 403 on refusal; counts telemetry.ingest.accepted per append; duplicate key a no-op.",
           "claims_steps": ["packet received"],
           "ast_hints": {"package": "src/intake", "implements": ["SampleStoreToken"],
             "dependencies": [{"type": "SampleStore", "task_id": "T2-020"}],
             "methods": [{"signature": "ingest(request: IngressRequest): Promise<void>", "returns": "Promise<void>"}],
             "meters": [{"name": "telemetry.ingest.accepted", "duty": "owns"}],
             "routes": [{"method": "POST", "path": "/ingress/packets", "duty": "serves"}],
             "config": []}}},
 {"n": 22, "project": "telemetry", "layer": "application", "feature": null,
  "dependsOn": {"test": ["T0-001"], "code": ["T0-001", "T2-021"]},
  "test": {"path": "test/intake/window-reader.spec.ts",
           "export": "WindowReaderSpec",
           "intent": "WindowReaderSpec proves the reader forwards accepted frames and counts the SHARED meter on both branches, against the tables the engine hydrated from unit 21's ownership - the spec names no literal unit 22 does not own."},
  "code": {"path": "src/intake/window-reader.service.ts",
           "export": "WindowReaderService",
           "intent": "WindowReaderService subscribes the accepted-sample feed and counts the shared meter per forwarded frame; it owns no literal - every fact it reads belongs to unit 21's table.",
           "ast_hints": {"package": "src/intake", "implements": [],
             "dependencies": [{"type": "IngressController", "task_id": "T2-021"}],
             "methods": [{"signature": "drain(frame: SampleFrame): Promise<void>", "returns": "Promise<void>"}],
             "meters": [], "routes": [], "config": []},
           "uses_meters": ["telemetry.ingest.accepted"],
           "uses_routes": ["POST /ingress/packets"],
           "claims_steps": ["packet received"]}}
]
```

# Prohibitions in tasks
`any` in public contracts, module-level process.env, entity-as-response, sync IO in handlers, unstored schema changes (must be migrations), test-only stubs reaching production wiring.
