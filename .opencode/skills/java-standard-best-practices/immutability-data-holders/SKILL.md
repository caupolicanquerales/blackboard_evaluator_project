---
name: immutability-data-holders
description: "Use when defining Java records, DTOs, value objects, or data holders to enforce immutability, defensive copying, and safe collection exposure."
---

# Immutability & Data Holders

Parent: [[java-standard-index]]

## Rules

- Prefer immutable state by default.
- Use records for DTOs and commands.
- Default fields to `final` unless mutation is required.
- Defensively copy mutable collections before exposing them.
- Return `List.copyOf()`, `Set.copyOf()`, or unmodifiable views.
- Do not expose internal collection references.
- Avoid setters on non-entity value objects.

```java
public record CreateUserRequest(
    @NotBlank String username,
    @Email String email,
    List<String> roles
) {
    public CreateUserRequest {
        Objects.requireNonNull(username, "Username required");
        Objects.requireNonNull(email, "Email required");
        roles = (roles != null) ? List.copyOf(roles) : List.of();
    }
}
```

```java
public class ShoppingCart {
    private final List<Item> items = new ArrayList<>();

    public List<Item> getItems() {
        return List.copyOf(this.items);
    }

    public void addItem(Item item) {
        Objects.requireNonNull(item, "Item cannot be null");
        this.items.add(item);
    }
}
```
