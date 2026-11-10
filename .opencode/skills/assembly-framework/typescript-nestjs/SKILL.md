---
name: typescript-nestjs
description: Assembly rules for NestJS (typescript). Booting the application module graph: reading DI resolution errors, providers, module wiring, env configuration.
---
# What the smoke proves
The e2e spec compiles the module graph and boots the app via TestingModule: every controller/service/provider resolves.
# Failure map
- `Nest can't resolve dependencies of X (?, ...)` => provider missing at argument `?`.
- `cannot find the module` / ForwardRef => import the module, not the raw class.
- Interface injection (`@Inject(TOKEN)`) with no binding => interfaces are not providers.
- process.env/config errors => ConfigModule or defaults missing.
# Fix menu (smallest first)
1. Register existing classes: @Injectable() + add to the owning module's providers.
2. Interfaces: ONE thin adapter class + `{ provide: TOKEN, useClass: Adapter }` in the consuming module; no logic.
3. Cross-module: exports from provider module, imports in consumer; never duplicate providers.
4. Config: ConfigModule.forRoot() + code-side fallbacks via ConfigService. Never package.json deps.
# Constraints
Never reorder/retype exported constructors (tests + DI tokens are the contract). useValue stubs only when boot is impossible otherwise - disclose each. Editable roots: `src/**` modules/providers/config file; never tests, package.json, lockfiles, nest-cli.json.
