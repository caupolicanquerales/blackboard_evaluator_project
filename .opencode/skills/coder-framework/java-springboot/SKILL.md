---
name: java-springboot
description: Coder rules for Java (default 21; the strategy pin is exact) with Spring Boot 3. Method body generation, imports, idioms, anti-patterns.
---
# Syntax
Java at the strategy-pinned version (21 default; modern language features allowed at the pin, never assume 17-only), `jakarta.*` only. `body` = pure body. A table binding spelled WITHOUT a visibility modifier is a PUBLIC API member (frozen tests consume it across packages; the weaver lands the default) - never ship a package-private accessor the table did not spell. Framework annotations via fields, never in signature: `annotations` (type level: RestController, Service, Configuration...), `methodAnnotations` (GetMapping("/x"), RequestBody...) - no `@`, classes into imports. Parameter annotations (@Valid, @RequestBody, @PathVariable) stay inside `signature`. Observability units implement ONLY what the task tables: audit adapter persists the port's record shape, meters use the exact tabled names with bounded tags, a logger field is added only when the intent names the step - never invent ad-hoc log lines in other units' bodies.
# Payload shaping
- Missing class in red: `kind` + `members`: class: fields+ctor; interface: abstract sigs+empty body; enum: constants; record: one entry per component, never a joined line (bare components route to the header).
- Generic: `export` = `Box<T>` / `Table<K, V extends Comparable<V>>`; the shell carries parameters, members use them; ctors/methods never repeat `<T>`.
- IS-A (isInstanceOf, port injection, @Override blame): `"implements": ["NotificationGateway"]` / `"extends": "AuditHandler"` - header clause lands once; supertype FQNs into imports; interface payload: implements = extends. Never the header as a member.
- Static factory (`Order.from(cart)`): full `signature` `public static Order from(Cart cart)` - redeclared from the text (modifiers, generics, return), existing annotations kept; a bare signature keeps the current shape.
# Reactive
Mono/Flux per contract; never block (.block, sleep, sync IO); Sinks: check EmitResult (retry FAIL_NON_SERIALIZED only; FAIL_OVERFLOW per declared posture); bounded buffers, capacity+overflow from config; compose chains (.map/.flatMap/.onErrorResume), never subscribe in business code; @RestControllerAdvice + ProblemDetail; time/capacity from config only.
# Misc
imports: clean FQNs, no keyword/`;`/wildcards, no java.lang. `var` only when obvious. records for immutable payloads. Tests: StepVerifier (reactor-test).
