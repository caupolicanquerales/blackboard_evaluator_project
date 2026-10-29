---
name: software-layering-patterns
description: Use when defining package/directory layout, layer boundaries, dependency direction, or ports and adapters inside a single module. Stack agnostic; directives only.
---

# Software Layering Patterns

## 1. Topology Selection Protocol

- Hexagonal (Ports & Adapters): multiple inbound channels (HTTP, queue, CLI) or multiple external systems behind ports.
- Clean/Onion: one primary delivery channel, rich domain model, infrastructure swappable.
- Modular Monolith: several bounded contexts in one deployable; each module owns its layers and exposes a public API only.
- Default to Hexagonal when unsure. Do not combine topologies inside one module.

## 2. Inner-to-Outer Layer Directives

- `domain`: entities, value objects, domain services, domain events. Imports only itself and language stdlib. No framework, persistence, or transport annotations.
- `application`: use cases, commands, queries, orchestration, transaction boundaries. Imports `domain` and its own ports. No presentation or infrastructure types.
- `infrastructure`: adapters implementing outbound ports (persistence, messaging, external clients, config). Imports `application` and `domain`. Never imported by `domain` or `application`.
- `presentation`: inbound adapters (controllers, consumers, CLI). Imports `application` only. Maps transport DTOs to commands/queries and results to responses. Never exposes domain objects.
- Dependencies point inward only. Composition root wires adapters to ports.

## 3. Port & Adapter Contract Rules

- Inbound (driving) ports: interfaces in `application` named by use case intent (`PlaceOrderUseCase`). Implemented by application services. Called by `presentation`.
- Outbound (driven) ports: interfaces in `application` (or `domain` when the concept is a domain abstraction) named by business role (`OrderRepository`, `PaymentGateway`). Implemented in `infrastructure`.
- Port signatures use domain/application types only. No ORM, HTTP, or SDK types in signatures.
- One port per use case or per aggregate root for persistence. No generic `BaseRepository` or `GenericService`.
- Adapter names state technology plus port (`JpaOrderRepository`, `StripePaymentGateway`).

## 4. Non-Negotiable Layering Constraints

- FAIL: `domain` or `application` importing `infrastructure` or `presentation` packages.
- FAIL: framework or persistence annotations on `domain` types.
- FAIL: controllers or consumers calling repositories or outbound ports directly.
- FAIL: entities or persistence models returned from `presentation`.
- FAIL: cycles between layers or between modules.
- FAIL: a module reaching into another module's internal packages; only its public API is allowed.
- FAIL: business rules in `presentation` or `infrastructure`.
- FAIL: `util`, `common`, or `helpers` packages holding business logic.
