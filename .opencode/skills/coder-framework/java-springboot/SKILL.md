---
name: java-springboot
description: Coder rules for Java 17+ with Spring Boot 3. Method body generation, imports, idioms, anti-patterns.
---

# java-springboot (Spring Boot 3)

## Syntax
- Java 17+. Jakarta namespace only: `jakarta.*`. Never `javax.*`.
- Body only. No signature, braces of the method, annotations, or class.
- Whole type missing in the red (`cannot find symbol: class`): provide `kind` + `members`
  (ctor/fields, abstract signatures, enum constants, record components) alongside the body.
- The type is created by the weaver, so framework annotations go in the dedicated payload fields,
  never inside `signature`: `annotations` for the type (`RestController`, `Service`,
  `Repository`, `Configuration`, `ControllerAdvice`) and `methodAnnotations` for the method
  (`GetMapping("/x")`, `PostMapping("/x")`, `RequestBody`, `Valid`, `ExceptionHandler(X.class)`).
  Write them without `@`, and list the class each one needs in `imports`. Parameter annotations
  (`@Valid`, `@RequestBody`, `@PathVariable`) stay in `signature`: they belong to the parameter, and
  the weaver preserves them.
- Web annotations live in `org.springframework.web.bind.annotation.*`; reactive types in
  `reactor.core.publisher` (`Mono`, `Flux`).
- Use `var` only when the type is obvious from the right side.
- Return type and checked exceptions match the AST signature exactly.

## Imports
- `imports` entries: clean FQN only, no `import` keyword, no `;`. Example: `jakarta.persistence.EntityNotFoundException`.
- Do not import `java.lang.*`.
- Do not use wildcard imports.
- Do not inline fully qualified names in the body.

## Method body rules
- Guard clauses first. Throw the exception type the test expects.
- Use `Objects.requireNonNull(x, "x")` for mandatory arguments.
- Use `Optional` only as a return type. Never as a field or parameter.
- Use `Optional.orElseThrow(() -> new X(...))` instead of `get()`.
- Prefer streams for pure collection transforms. Keep them short.
- Use `List.of`, `Map.of`, `Set.of` for immutable constants. Return unmodifiable copies.
- Use `BigDecimal` for money. Never `double`.
- Use `java.time` types. Never `java.util.Date`.
- No `System.out`, no logging, no `Thread.sleep`, no reflection unless `intent` requires it.
- Business logic stays pure: no field mutation unless `intent` requires it.

## Spring Boot 3 in the body
- Type and method annotations belong in `annotations` / `methodAnnotations`, never in `signature`;
  parameter annotations stay in `signature`. Never write an annotation in the body.
- Use only injected fields and collaborators named in the AST context.
- Transactions are handled by the proxy. Do not open or commit transactions in the body.
- Time: use the injected `Clock`. Never `Instant.now()`.
- Errors: throw the exception type the test expects. Never build `ProblemDetail` in service code.
- HTTP clients: use injected `RestClient` or `WebClient`. Never `RestTemplate`.

## Anti-patterns
- Field injection with `@Autowired`.
- `javax.*` imports.
- Catching `Exception` or `Throwable` and swallowing it.
- Returning `null` where `Optional` or an empty collection fits.
- Mutable static state.
- `synchronized` on `this` or on boxed values.
- `new` for beans that Spring must manage.
- Calling `@Transactional` methods from within the same class (self-invocation has no proxy).
- `@Transactional` on private methods.
- Entities returned directly from controllers.
- Hard-coded secrets, URLs, or profiles.
- `Thread.sleep` or blocking calls in reactive code.
- Business logic in controllers.
- Unbounded `findAll()` on large tables.

## Output checks before submit
- Body compiles against the signature with the listed imports.
- Every red-phase assertion is satisfied.
- No anti-pattern above appears.
