---
name: clean-name-code-style
description: "Use when writing, reviewing, or refactoring Java identifiers, classes, methods, variables, or constants to enforce clean naming and code style conventions."
---

# Clean Naming & Code Style

Parent: [[java-standard-index]]

## Naming

- Classes/interfaces: `PascalCase`
- Methods/variables: `camelCase`
- Constants: `UPPER_SNAKE_CASE`
- Booleans: `isX`, `hasX`, `canX`, `shouldX`
- Names must reveal intent; no cryptic abbreviations.
- Use verb-noun method names: `calculateTax()`, `sendNotification()`, `parsePayload()`.
- Collections plural: `orders`, `activeUsers`, `usersById`.
- No type prefixes or Hungarian notation: `name`, `count`, `userResponse`.

## Rules

- Use domain language, not generic helpers.
- Prefer `UserValidator` over `UserManager` unless the abstraction is real.
- Single-letter locals only for trivial loop indexes.

```java
List<User> activeUsers = userRepository.findAllByActiveTrue();
int elapsedTimeInDays;
User userAccount;
```
