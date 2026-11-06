---
name: typescript-nestjs
description: Assembly rules for NestJS (typescript). Booting the application module graph: reading DI resolution errors, providers, module wiring, env configuration.
---

# typescript-nestjs (Application Assembly)

## What the smoke test proves
- The scaffold e2e spec (`test/app.e2e-spec.ts`) compiles the Nest module graph and boots
  the full application through `TestingModule`: every controller, service and provider
  must resolve.
- The gate command is the package's own `test:e2e` script: red here means the
  application cannot start, no matter how green the unit tests are.

## Reading the failure chain
- `Nest can't resolve dependencies of X (?, ...)`: a provider is missing at the `?`
  argument position of X's constructor.
- `Nest cannot find the module [X]`/`ForwardRef` errors: import the module, do not
  reference the raw class.
- Interface tokens: TypeScript interfaces are not providers — the error shows when a
  constructor injects via `@Inject(token)` with no binding.
- Config errors around `process.env`: the configuration module or defaults are missing.

## Fix menu (smallest first)
1. Register an existing class: `@Injectable()` on the service/adapter, and add it to the
  `providers` array of the owning module.
2. Interfaces are not providers: create ONE thin adapter class implementing the
  interface and bind it — `{ provide: TOKEN, useClass: Adapter }` — in the consuming
  module's providers. No new business logic in it.
3. Cross-module dependencies: `exports` from the providing module, `imports` in the
  consuming one; never duplicate providers.
4. Environment/config: `ConfigModule.forRoot()` in the app module and code-side
  fallbacks read through `ConfigService`. Never `package.json` dependencies.

## Constraints
- Never reorder or retype constructor parameters of exported classes: the green unit
  tests and the DI tokens are the contract.
- `useValue` stub providers exist only when boot is impossible otherwise: disclose each
  one in the output.

## Editable roots
- `src/**` (modules, providers, configuration files). Never `test/**`, `package.json`,
  lockfiles, `jest*` configuration.
