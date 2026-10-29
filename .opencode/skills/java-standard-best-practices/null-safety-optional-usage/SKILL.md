---
name: null-safety-optional-usage
description: "Use when handling nulls, input validation, or Optional in Java to enforce null-safe boundaries, empty collections, and idiomatic Optional usage."
---

# Null Safety & Optional Usage

Parent: [[java-standard-index]]

## Rules

- Treat `null` as invalid state.
- Never return `null` for collections; return `List.of()`, `Set.of()`, or `Collections.emptyList()`.
- Use `Optional<T>` only for return values where absence is legal.
- Validate inputs at boundaries with `Objects.requireNonNull()` or `@NotNull`.
- Never use `Optional` as a field, parameter, or controller argument.
- Prefer `Optional.map()`, `flatMap()`, and `orElseThrow()` over `.isPresent()` + `.get()`.

```java
public Optional<User> findByEmail(String email) {
    return Optional.ofNullable(userMap.get(email));
}

String domain = userService.findByEmail("user@example.com")
    .map(User::getDomain)
    .orElse("default.com");
```

```java
public class OrderService {
    private final PaymentGateway paymentGateway;

    public OrderService(PaymentGateway paymentGateway) {
        this.paymentGateway = Objects.requireNonNull(paymentGateway, "PaymentGateway must not be null");
    }

    public void processPayment(Order order) {
        Objects.requireNonNull(order, "Order must not be null");
    }
}
```