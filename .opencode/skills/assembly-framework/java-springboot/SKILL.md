---
name: java-springboot
description: Assembly rules for Spring Boot (java). Booting the application context: reading dependency-failure chains, bean registration, port adapters, driver configuration.
---

# java-springboot (Application Assembly)

## What the smoke test proves
- The scaffold `contextLoads` (`@SpringBootTest`) boots the ENTIRE application context:
  component scan plus every injection site in the woven production classes.
- The gate command runs that test alone: red here means the application cannot start,
  no matter how green the unit tests are.

## Reading the failure chain
- `UnsatisfiedDependencyException ... constructor parameter N ... No qualifying bean of type 'X'`:
  type X must be supplied; the named class is the injection site that needs it.
- `expected at least one bean which qualifies as autowire candidate`: the class exists
  but is not registered.
- `NoSuchBeanDefinitionException` on an interface: no adapter implements that port.
- `Failed to load ApplicationContext` with driver errors (r2dbc/jdbc url, Flyway):
  missing or wrong configuration in resources.

## Fix menu (smallest first)
1. Register an existing class: add the stereotype that matches its layer —
   `@Service` (application), `@Component` (domain collaborator), `@Repository`/`@Repository`-equivalent
   (infrastructure), `@Configuration` (wiring).
2. Port/interface with no implementation: create ONE thin adapter class under the
   context's `src/main/java/.../infrastructure/` package, delegating to an existing
   unit. No new business logic in it.
3. `@Bean` factories for types a constructor cannot annotate (`Clock`, `Duration`,
   window sizes) inside a `*WiringConfiguration` under `src/main/java/.../infrastructure/`.
4. Driver configuration in `src/main/resources/application.yml` only (r2dbc/jdbc url,
   Flyway toggles). Never `pom.xml`.

## Constraints
- Java 17+, `jakarta.*` namespace only; never change constructor signatures, exported
  types, or method bodies — the green unit tests are the contract.
- Ambiguous bean matches: `@Primary` on YOUR configuration, never re-annotate foreign classes.
- Empty policy maps, no-op publishers, stub urls: the application boots but does not
  behave. Disclose every placeholder in the output.

## Editable roots
- `src/main/java/**`, `src/main/resources/**`. Never `src/test/**`, `pom.xml`, `mvnw*`,
  `db/migrations/**`.
