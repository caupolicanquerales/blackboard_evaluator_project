---
name: software-layering-patterns
description: Use when defining package/directory layout, layer boundaries, dependency direction, or ports and adapters inside a single module. Stack agnostic; directives only.
---
# Topology
Hexagonal when several inbound channels/external systems; Clean/Onion for one channel + rich domain; modular monolith = contexts in one deployable, each module owning its layers, exposing only its public API. Default hexagonal; never mix topologies in one module.
# Layers (dependencies inward only)
- domain: entities, value objects, domain services, events; stdlib only; zero framework/persistence/transport annotations.
- application: use cases, commands, queries, orchestration, transaction boundaries; imports domain + its own ports; no presentation/infrastructure types.
- infrastructure: adapters implementing outbound ports (persistence, messaging, clients, config); never imported inward.
- interface/presentation: controllers, consumers, CLI; imports application only; maps DTOs<->commands; never exposes domain objects.
Composition root wires adapters to ports.
# Ports
Inbound (driving): in application, named by use-case intent (`PlaceOrderUseCase`), implemented by application services, called by presentation. Outbound (driven): interfaces in application (domain when the concept is domain-level), named by business role (`OrderRepository`, `PaymentGateway`), implemented in infrastructure. Signatures: domain/application types only - no ORM/HTTP/SDK types. One port per use case or aggregate root; no generic `DatabaseService`.
# Boundaries & tasks
Collaborators addressed only by the owning context's port/event - never another context's internals or repository. Cross-context reads via query ports/events; writes via commands/events per the map's consistency. One component/contract per task; `layer` = where the file lives; wiring is its own infrastructure task; DTOs never cross inward.
