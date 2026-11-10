---
name: java-springboot
description: Assembly rules for Spring Boot (java). Booting the application context: reading dependency-failure chains, bean registration, port adapters, driver configuration.
---
# What the smoke proves
`contextLoads` (@SpringBootTest) boots the ENTIRE context: component scan + every injection site. Red here = the app cannot start, regardless of unit green.
# Failure map
- `UnsatisfiedDependencyException ... parameter N ... No qualifying bean of type 'X'` => X must be supplied at that site.
- `expected at least one bean which qualifies as autowire candidate` => class exists, not registered.
- `NoSuchBeanDefinitionException` on an interface => port has no adapter.
- `Failed to load ApplicationContext` + driver/Flyway errors => missing/wrong config in resources.
# Fix menu (smallest first)
1. Register an existing class with its layer stereotype: @Service (application), @Component (domain collaborator), @Repository/@Configuration.
2. Unimplemented port: ONE thin adapter in the context's `infrastructure` package delegating to an existing unit; no logic inside.
3. Unannotatable types (Clock, Duration, sizes): @Bean factories in a `*WiringConfiguration` under `src/main/java/.../infrastructure/`.
4. Driver config ONLY in `src/main/resources/application.yml` (r2dbc/jdbc url, Flyway). Never pom.xml.
# Constraints
Java 17+, `jakarta.*` only; never change constructor signatures, exported types, or method bodies (green unit tests are the contract). Ambiguous beans: @Primary on YOUR configuration only. Iteration cap and placeholders: disclose every stub. Editable roots: `src/main/java/**`, `src/main/resources/**`.
