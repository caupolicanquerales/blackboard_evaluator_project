---
name: spring-security
description: "Coder and tester tier (stages 1-2) for Spring Boot 3 / Spring Security units: how to write the chain DSL, the principal adapter, custody and crypto bodies, and how to drive permitted / denied / cross-owner tests with spring-security-test. The plan names the mechanism (tech-stack-architect/spring-security-architect); this file spells it."
---
# Scope
Read this ONLY when the unit's task names a security token (`AZ-`, `SI-`, `DC-`, `TB-`, `SD-` +
`spec_ref`/`capability` pair) in its intent: the architect already chose the mechanism and tabled the
signature, so a non-security unit pays no call for it. Coder §Chain / §Adapter / §Custody below, tester
§Tests. Payload schema and general idioms stay with `coder-framework/java-springboot` and
`tester-framework/java-junit5`; **the plan's table wins over anything here** - if a signature, layer or
posture disagrees with the task, report the disagreement, never re-decide it.

# Chain DSL (the wiring/infrastructure unit's body)
**Two stacks, two APIs. Never mix them on one bean - the names below were read off the API, and a
servlet type in a reactive chain is a compile error the coder pays for.**

### WebFlux (`ServerHttpSecurity`)
`@EnableWebFluxSecurity`; bean `SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http)`,
body ends `return http.build();`.
`http.authorizeExchange(e -> e.pathMatchers(HttpMethod.POST, "/api/x")
 .access(ReactiveAuthorizationManager.hasRole("ADMIN")).anyExchange().denyAll())` - **ALWAYS a terminal
clause**; `.access(...)` guards the ROUTE, never a ROW. JWT:
`.oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))` beside the `ReactiveJwtDecoder` bean the
plan tables; per-device secrets: `.httpBasic(h -> h.authenticationManager(<device manager>))`; client
certificates: `.x509(x -> x.principalExtractor(...).authenticationManager(...))` (defaults
`SubjectX500PrincipalExtractor`, `ReactivePreAuthenticatedAuthenticationManager`). Scope checks read the
mapped authority (`SCOPE_` prefix), not the raw claim. TEST BOOT vs TRANSPORT MATERIAL: the chain's `.x509()`
is asserted WITHOUT a TLS server (header/mutated-auth tests, no `server.ssl.*` needed); when the delivered
config enables `server.ssl.*`, the slice support's `registerProperties` substitutes ONLY the transport keys
for the test boot (generated keystore when the JDK can produce one, else `server.ssl.client-auth=none` in
the dynamic properties) and says so in a comment naming the unit tests that still hold the control - a
support unit that lets the graph fail to boot has not delivered its contract.
STATELESSNESS IS THE CONTEXT REPOSITORY:
`.securityContextRepository(NoOpServerSecurityContextRepository.getInstance())`, plus no
session-backed mechanism (`formLogin` off). CSRF on that token chain:
`.csrf(csrf -> csrf.disable())`, with the posture named in the intent; a cookie client keeps CSRF and the
session - **code whichever posture the intent names, never both**.
`ServerHttpSecurity.sessionManagement(…)` exists (6.3+) but configures CONCURRENT SESSIONS ONLY,
via `concurrentSessions(...)`. The reactive type has no session-creation-policy setter and no
SessionCreationPolicy enum - both are servlet types, and the servlet line in the block below
**does not compile here**.
The deny path answers through
`.exceptionHandling(e -> e.authenticationEntryPoint(<ServerAuthenticationEntryPoint>)
 .accessDeniedHandler(<ServerAccessDeniedHandler>))` with the opaque body (code, human-safe
message, correlation key, nothing else). Extra filters position with
`.addFilterAt(filter, SecurityWebFiltersOrder.<phase>)`.
Reactive-only, so it does not belong to the servlet block below: never `block()` or `.blockFirst()` in an
auth path, and never `subscribe()` inside the chain - the composition the plan tables owns the
subscription (`coder-framework/java-springboot` §Reactive).

### Servlet (`HttpSecurity`)
`@EnableWebSecurity`; bean `SecurityFilterChain filterChain(HttpSecurity http)`.
`http.authorizeHttpRequests(r -> r.requestMatchers(HttpMethod.POST, "/api/x").hasRole("ADMIN")
 .anyRequest().denyAll())`; JWT `.oauth2ResourceServer(o -> o.jwt(withDefaults()))` with a `JwtDecoder`
bean; certificates `.x509(withDefaults())`; deny responses through
`exceptionHandling(e -> e.authenticationEntryPoint(<AuthenticationEntryPoint>)
 .accessDeniedHandler(<AccessDeniedHandler>))`. THIS is where statelessness is a policy:
`http.sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))`
(`org.springframework.security.config.http.SessionCreationPolicy` - a servlet type, absent from WebFlux).

# Principal adapter (the one Spring-Security-importing class in the tree)
`ReactiveSecurityContextHolder.getContext().map(SecurityContext::getAuthentication)`, mapped into the
plan's OWN value type (`PrincipalContext`, `TenantScope`, `TenantKey`) - the `org.springframework.security.*`
import stays in this single infrastructure class, and application/domain units keep receiving plain types.
An empty or absent context **FAILS CLOSED**: deny, never a default tenant, never an "anonymous" tenant id.
A method that returns the decision carries both branches the table's `semantics` names - admitting and
refusing - and the refusal is what the caller's contract expects to see.

# Custody, crypto, credentials (only when the plan scheduled the unit)
`Cipher.getInstance("AES/GCM/NoPadding")`, 256-bit key, a FRESH 12-byte IV per write stored AHEAD of the
ciphertext (deterministic IVs leak equality); envelope = DEK for the data, KEK wrapping the DEK; keys read
from the named bundle/env AT USE TIME - no key constant in source, never logged, never in `toString`, and
the unit that must not hold the key is the one the plan separated on purpose. Credentials:
`PasswordEncoderFactories.createDelegatingPasswordEncoder()` (`{bcrypt}` id-prefix, so rotated writes and
old hashes both verify). Secrets arrive as `${ENV}` placeholders from the config unit; a literal in any
artifact is a defect, not a default - and a placeholder a boot-path bean reads carries a DEFAULT
(`${ENV:}`) or is seeded in the document the test profile activates, because the scaffold's plain
contextLoads boots with no dynamic properties and an unresolvable placeholder is a permanently red
terminal gate. An in-memory credential store built from configured principals has NO legal empty state:
`MapReactiveUserDetailsService` rejects an empty list in its constructor (`Assert.notEmpty`), so a boot
contract with zero credentials either seeds entries (test profile) or lets startup fail with the named
reason - it must not be coaxed past the guard by a placeholder principal, and the auto-configured default
user (generated password) is a fabricated principal the plan never wants.

# Config payloads
Read keys through `@ConfigurationProperties`/`@Value` - never re-spell a literal the config unit owns.
The file's FORMAT follows its KIND (nested YAML in `.yml`, dotted pairs are lookup paths, not layout),
and a key the plan enables must exist in the document the runtime actually loads for that profile.

# Tests (stage 1 - `spring-security-test`)
Per authorization row, THREE cases driven at the ENTRY: permitted (2xx), denied (401/403), and
**CROSS-OWNER** - a well-formed identifier owned by another tenant, presented by a validly authenticated
caller, answered exactly like a missing row and audited. Reactive:
`webTestClient.mutateWith(mockJwt().jwt(j -> j.claim("tenant", "t-1")))`,
`mutateWith(mockUser("device-1"))`, `@WithMockUser(roles = "ADMIN")` (static import
`org.springframework.security.test.web.reactive.server.SecurityMockServerConfigurers.*`). Servlet:
`@WithMockUser` with `.with(csrf())` and `.with(jwt().claim(...))` from
`SecurityMockMvcRequestPostProcessors`. Assert the deny BODY is opaque and that the owner/tenant predicate
reaches the store as a BOUND parameter (spy or captor on the adapter call): a test that only proves the
route was authorized is the IDOR left open. `mockJwt`/`mockUser` symbols missing => report the compile
error naming `spring-security-test`; never hand-build a `SecurityContext` to work around an unscheduled
build duty. A per-unit security gate stays per-unit: it never demands the whole bean graph.
A test that `@Import`s the chain's `@Configuration` must make the container able to BUILD that chain:
every CONCRETE PROJECT TYPE in the chain bean's method parameters is a collaborator of the test's own
slice - double the COLLABORATOR (`@MockitoBean` Boot ≥3.4, `@MockBean` earlier - the pom decides) or
`@Import` the configuration that registers it; never double the chain, its `ReactiveAuthorizationManager`
or its entry points - those ARE the assertions. A needed type absent from every table your message carries
is a PLAN HOLE (rule (z6)): report it, never drop the import to make the context load - an unguarded
slice proves nothing about a guard. 2026-11-19 R3: a controller slice imported the chain while its twin's
contract pinned the chain's manager; the untabled manager killed the context at every boot and the unit
died 3/3 on a gap its plan wrote.
