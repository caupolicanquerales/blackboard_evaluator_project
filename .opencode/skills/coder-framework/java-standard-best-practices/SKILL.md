---
name: java-standard-best-practices
description: "Coder rules for plain Java method bodies: naming, method design, immutability, null safety. Applies to any Java framework."
---
# Scope
Method BODY only; signatures/annotations come from the contract - never change them. Readability > cleverness; fail fast; minimize state.
# Naming
PascalCase types; camelCase members; UPPER_SNAKE constants; booleans isX/hasX/canX/shouldX; verb-noun methods; plural collections; no abbreviations/Hungarian; single letters only for indexes.
# Body
Parameters fixed by signature; no new record types (only contract-declared); guard clauses first; <15 lines; private helpers only if the contract allows; no unrequested flag branching; queries side-effect free.
# Immutability
Fields final. A final field: inline initializer OR constructor assignment, NEVER both - when a retry constructor must assign, re-emit as `private final T x;` (keeping both = "cannot assign a value to final variable" + a burned gate cycle). records for DTOs/commands/value objects; List/Set/Map.copyOf exposure; defensive-copy mutable inputs; no value-object setters.
# Null
`null` invalid: Objects.requireNonNull(x,"msg"); collections List.of()/Set.of(); Optional only as return type where absence is legal - never field/param/element; map/orElseThrow chains, no isPresent()+get().
# Generics & supertypes (payload)
Generic type: parameters on `export` (`Box<T>`); clause belongs to the TYPE only - constructor `public Box(T value)`, never `public Box<T>(T value)`; methods use T without re-declaring unless they need their own. IS-A: implements/extends payload fields (header clause once; supertypes into imports). Static factory: full signature `public static Order from(Cart cart)` (redeclares; keeps annotations).
# Guards
No logging/IO/sleeps/random/global state unless intent demands; no swallowed exceptions; throw the tested error type.
