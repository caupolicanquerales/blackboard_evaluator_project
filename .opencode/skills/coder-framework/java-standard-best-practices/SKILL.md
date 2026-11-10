---
name: java-standard-best-practices
description: "Coder rules for plain Java method bodies: naming, method design, immutability, null safety. Applies to any Java framework."
---

# Java Standard Best Practices

Scope: generate the method BODY only. Signature, braces, and annotations come from the AST context and the task contract. Never change them.

Priority: readability > cleverness. Fail fast. Minimize state. Prefer immutable records and value objects.

## Naming
- Classes `PascalCase`; methods and variables `camelCase`; constants `UPPER_SNAKE_CASE`.
- Booleans: `isX`, `hasX`, `canX`, `shouldX`.
- Methods are verb-noun: `calculateTax()`, `parsePayload()`.
- Collections plural: `orders`, `usersById`.
- Reveal intent. No abbreviations, no Hungarian prefixes.
- Single-letter names only for loop indexes.

## Method body design
- Parameters are fixed by the signature. Do not add, remove, or reorder them.
- Do not create new `record` parameter types. Records only if the contract already declares that type.
- Guard clauses first. Return early on invalid state.
- Keep the body under 15 lines. Extract private helpers only when the contract allows them.
- No boolean flag branching the intent does not require.
- Queries are side-effect free.

## Immutability
- Fields `final` by default.
- A `final` field takes its value ONCE: inline initializer OR constructor assignment,
  never both. When a retry payload must assign a final field in a constructor, re-emit
  the field WITHOUT the initializer (`private final T x;`) - keeping the initialized
  declaration and adding the assignment fails with "cannot assign a value to final
  variable" and costs a full gate cycle.
- Use `record` for DTOs, commands, and value objects.
- Return `List.copyOf()`, `Set.copyOf()`, or `Map.copyOf()`. Never expose internal collections.
- Defensive-copy mutable collection inputs in constructors or compact record constructors.
- No setters on value objects.

## Null safety
- `null` is invalid state. Validate with `Objects.requireNonNull(x, "message")`.
- Collections: return `List.of()`, `Set.of()`, never `null`.
- `Optional<T>` only as a return type where absence is legal.
- Never `Optional` as a field, parameter, or collection element.
- Chain `map`, `flatMap`, `orElseThrow(() -> ...)`. Never `isPresent()` plus `get()`.

## Generics and supertypes
- When the contract type is generic, declare its parameters in the payload `export`
  (`Box<T>`, `Table<K, V extends Comparable<V>>`): the shell the weaver creates carries them
  and `members` may use the variables.
- The parameter clause belongs to the type declaration only: a constructor is
  `public Box(T value)`, never `public Box<T>(T value)`; methods use `T` without re-declaring it
  unless the method needs its OWN variable (`<E> ...`).
- When a frozen test asserts your type IS-A a port (`isInstanceOf(Port.class)`, injection by
  the port type), declare `"implements": ["Port"]` and/or `"extends": "Base"`; the weaver
  lands the clause on the header once. List those types in `imports`.
- A factory the test calls statically (`Order.from(cart)`) needs the modifier spelled in
  the payload `signature` as a COMPLETE declaration: `public static Order from(Cart cart)` -
  the method is redeclared from that text (generics included), keeping existing annotations.

## Imports
- Every type used in the body (for example `Objects`, `List`, `Optional`, `Map`) must be listed in the payload `imports` array as a fully qualified name.
- No `import` statements inside the body.
- Do not list `java.lang.*` types (`String`, `Integer`, `Math`).

## Anti-patterns
- Changing the signature or adding parameter records.
- `null` returns for collections or optionals.
- Mutable getters that leak internal lists.
- Side effects inside query logic.
- Types used in the body but missing from `imports`.
- Generic helper names (`Manager`, `Helper`, `Util`) without real abstraction.

## Example (body only)
Contract signature: `Optional<User> findByEmail(String email)`

```
Objects.requireNonNull(email, "email must not be null");
return Optional.ofNullable(usersByEmail.get(email));
```

Payload `imports`: `java.util.Objects`, `java.util.Optional`
