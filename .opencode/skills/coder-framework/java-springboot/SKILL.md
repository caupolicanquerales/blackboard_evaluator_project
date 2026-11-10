---
name: java-springboot
description: Coder rules for Java 17+ with Spring Boot 3. Method body generation, imports, idioms, anti-patterns.
---
# Syntax
Java 17+, `jakarta.*` only. `body` = pure body. Framework annotations via fields, never in signature: `annotations` (type level: RestController, Service, Configuration...), `methodAnnotations` (GetMapping("/x"), RequestBody...) - no `@`, classes into imports. Parameter annotations (@Valid, @RequestBody, @PathVariable) stay inside `signature`.
# Payload shaping
- Missing class in red: `kind` + `members`: class: fields+ctor; interface: abstract sigs+empty body; enum: constants; record: one entry per component, never a joined line (bare components route to the header).
- Generic: `export` = `Box<T>` / `Table<K, V extends Comparable<V>>`; the shell carries parameters, members use them; ctors/methods never repeat `<T>`.
- IS-A (isInstanceOf, port injection, @Override blame): `"implements": ["NotificationGateway"]` / `"extends": "AuditHandler"` - header clause lands once; supertype FQNs into imports; interface payload: implements = extends. Never the header as a member.
- Static factory (`Order.from(cart)`): full `signature` `public static Order from(Cart cart)` - redeclared from the text (modifiers, generics, return), existing annotations kept; a bare signature keeps the current shape.
# Reactive
Mono/Flux per contract; never block (.block, sleep, sync IO); Sinks: check EmitResult (retry FAIL_NON_SERIALIZED only; FAIL_OVERFLOW per declared posture); bounded buffers, capacity+overflow from config; compose chains (.map/.flatMap/.onErrorResume), never subscribe in business code; @RestControllerAdvice + ProblemDetail; time/capacity from config only.
# Misc
imports: clean FQNs, no keyword/`;`/wildcards, no java.lang. `var` only when obvious. records for immutable payloads. Tests: StepVerifier (reactor-test).
