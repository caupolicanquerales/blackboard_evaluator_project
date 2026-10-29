---
name: method-design-clean-functions
description: "Use when designing or refactoring Java methods, controllers, or services to enforce small single-responsibility functions, guard clauses, and thin controllers."
---

# Method Design & Clean Functions

Parent: [[java-standard-index]]

## Core rules

- One responsibility per method.
- Small methods; prefer 3 params or fewer.
- Group arguments into a `record` when related.
- Guard clauses before business logic.
- No hidden side effects in queries.
- Controllers: thin, DTO-based, no business logic.
- Use `ResponseEntity<T>` for typed responses.
- Avoid boolean flag arguments; split methods by intent.
- Prefer records for DTOs and commands.
- Keep method bodies short; extract helpers.

## Controller rules

- Controllers route requests only; services own business rules, authentication logic, and redirects.
- Never expose entities directly via HTTP.
- Validate request DTOs at the boundary.
- No repository injection in controllers.
- No custom auth branching, security checks, or session handling in endpoints or controller helpers.
- No private helper methods in controllers for business, security, or view resolution logic. Delegate decisions to services.

```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {
    private final UserService userService;

    @PostMapping
    public ResponseEntity<UserResponse> createUser(@Valid @RequestBody CreateUserRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
            .body(userService.createUser(request));
    }
}
```

## Method design

- Prefer `record` parameter objects over long argument lists.
- Fail early; return immediately on invalid state.
- Queries must be side-effect free.
- Use command/query separation.

```java
public record UpdateUserCommand(
    @NotNull UUID userId,
    @NotBlank String firstName,
    @NotBlank String lastName,
    @Email String email,
    boolean active
) {}

public void updateUser(UpdateUserCommand command) {
    Objects.requireNonNull(command, "Command must not be null");
    if (!command.active()) {
        deactivateUser(command.userId());
        return;
    }
    applyUserUpdates(command);
}
```

## Agent constraints

- No repositories in controllers.
- No auth branching or `request.getSession()` in controllers.
- No unnecessary `FooService` + `FooServiceImpl` unless required.
- DTOs and commands: records.
- Keep methods under 15 lines when possible.
