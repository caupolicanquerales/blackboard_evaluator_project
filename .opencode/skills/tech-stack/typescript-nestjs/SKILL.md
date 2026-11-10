---
name: typescript-nestjs
description: "Stack constraints for planning and emission; technology names and versions come from here."
---
# Stack facts
Node 20 LTS; TypeScript 5 strict; NestJS 10; npm; layout: `src/<feature>` modules with controller/service/(port) + `src/infrastructure` adapters, `test/` e2e via supertest.
# Conventions (planning)
Constructor injection with provider tokens for interfaces (`@Inject(TOKEN)`); DTOs as classes with class-validator decorators at boundaries (whitelist:true pipe), never entities serialized to responses; domain errors thrown as typed exceptions, mapped by an ExceptionFilter; async everywhere - no sync fs/crypto in request paths; configuration via ConfigModule `forRoot()` + typed ConfigService readers with code-side defaults (no raw `process.env` in business code); cross-module deps via exports/imports, no provider duplication.
# Persistence & test
TypeORM (decorators, migrations as `<Tag><Timestamp>.ts` expand-only) or a declared driver per strategy; DatabaseModule isolated from domain; jest unit tests + supertest e2e spec `test/app.e2e-spec.ts` (`npm run test:e2e` is the boot gate); interfaces bound via `{provide, useClass}` thin adapters.
# Build/run
`npm run build` (nest tsc), start:dev watch; package-lock committed; engines.node pinned.
# Prohibitions in tasks
`any` in public contracts, module-level process.env, entity-as-response, sync IO in handlers, unstored schema changes (must be migrations), test-only stubs reaching production wiring.
