---
name: spring-security-architect
description: "Architect-tier only (agent-planner-architect, phase 2 of the split): maps a security spec's capability tokens onto the unit, layer, mechanism name and config keys a plan must schedule in Spring Boot 3. Planning facts only - method bodies and test syntax live in the coder/tester-tier skill tech-stack/spring-security."
---
# Scope
Phase 2, rule (y): the mechanism column IS the identifier the intent must spell - `AZ-03` plus a
paraphrase is a citation, not a mapping. Copy it from this table and carry nothing the table
does not hold - an unrealizable token is still an added unit (its home is in the row), never an
invented class and never discharged by a risk alone.
The cell names the IDENTIFIER - class, annotation, or call name - never its composition: bodies and
test syntax live in `tech-stack/spring-security` (the coder and
tester tier, reached from the java framework skills). WebFlux is the default; an MVC plan takes
the servlet pair.

# Capability token -> unit, layer, mechanism, key
| token | unit (`unit_kind`) | layer | the identifier the INTENT must spell (prose = a citation, not a mapping) | key the config unit owns |
|---|---|---|---|---|
| `bearer-jwt-proof` | policy-adapter | infrastructure | resource-server JWT decoder bean (`ReactiveJwtDecoder`) on the chain | `spring.security.oauth2.resourceserver.jwt.issuer-uri` (derives validation), `.jwk-set-uri` (the offline/test route), `.jws-algorithms` [`RS256`], `.audiences` |
| `device-credential-proof` | credential-handling | infrastructure | `httpBasic` + a per-device `ReactiveAuthenticationManager` (or a `ReactiveUserDetailsService` behind it); the single in-memory dev user is never the delivered posture. A credential is a TRIPLE: the custody path is tabled `ast_hints.config` kind `list` with fields `id`, `secret-hash`, `scope` (z5 - one scalar env var per role cannot carry a triple); the store has NO legal empty state, so the boot posture is declared in the config contract: fail-fast when unseeded, or test-profile seed entries - never an invented placeholder principal | credential-list path (kind `list`, fields above), defaultable `${VAR:}` or profile-seeded |
| `mutual-tls-proof` | credential-handling | infrastructure | `x509` on the chain with `SubjectX500PrincipalExtractor` + `ReactivePreAuthenticatedAuthenticationManager`, over the peer certificate the container exposes | `server.ssl.client-auth` |
| `role-check` | policy-adapter | infrastructure | `ReactiveAuthorizationManager.hasRole(...)` on the matcher - or `@PreAuthorize` with `@EnableReactiveMethodSecurity` active | - |
| `scope-check` | policy-adapter | infrastructure | `ReactiveAuthorizationManager.hasAuthority("SCOPE_...")`; the claim becomes that authority through `JwtGrantedAuthoritiesConverter` | `spring.security.oauth2.resourceserver.jwt.authority-prefix` |
| `owner-scoped-query` / `tenant-scoped-query` | ownership-predicate + policy-adapter | domain or application + infrastructure | `permits(...)` / `byIdAndTenant(...)` on the unit that performs the LOOKUP, tenant bound as a PARAMETER (`@Query(":tenantId")`, `DatabaseClient.bind(...)`), never concatenated SQL | - |
| `deny-by-default` | policy-port + wiring duty | infrastructure (chain bean) | the chain's terminal `anyExchange().denyAll()` (servlet: `anyRequest().denyAll()`) | - |
| `hashing` | credential-handling | infrastructure | `PasswordEncoder` bean = `PasswordEncoderFactories.createDelegatingPasswordEncoder()` (the id-prefix lets rotated writes and old hashes both verify) | - |
| `field-encryption` / `envelope-encryption` | policy-adapter | infrastructure | no framework mechanism: the plan's OWN adapter at the store boundary (`AesGcmPayloadCipher.encrypt(...)` / `decrypt(...)` tabled), key read through the named bundle - its paired test runs on the REAL substrate and asserts the stored column is not the plaintext | `spring.ssl.bundle.pem.<name>.*` |
| `tokenization` | policy-adapter | store or domain | no framework mechanism: the unit that MINTS and resolves the surrogate (`SurrogateReferenceStore.mint(...)`) - its test asserts the raw reference never reaches a response, log or export | - |
| `key-separation` | key-custody | CONFIG unit + infrastructure | no single class does this: the config unit names one bundle per purpose and `SslBundles.getBundle("<purpose>")` reads it - server TLS != data key != resource-server client secret | `spring.ssl.bundle.*`, distinct key per reader |
| `credential-rotation` | key-custody | CONFIG unit | no framework mechanism for the schedule: the config unit owns the window and material is re-read through `SslBundles` (never cached in a field); its test asserts no secret literal anywhere | `spring.ssl.bundle.watch.file.quiet-period` |
| `external-key-store` | key-custody | CONFIG unit | no framework mechanism in process: the config unit owns `${ENV}` / mounted-path resolution at boot - its test asserts no key literal in source, fixtures, logs or artifacts | - |
| `log-redaction` | redaction | application (port) + infrastructure (adapter) | no framework mask for FIELDS: a `RedactionPort` (application) + adapter tabled in `ast_hints`, applied BEFORE the audit/step-log write - never a logger call | - |
| `error-code-only` | classification-rule | interface + config | `ServerAuthenticationEntryPoint` + `ServerAccessDeniedHandler` on `exceptionHandling`, answering code, human-safe message, correlation key | `server.error.include-message`, `server.error.include-stacktrace`, `server.error.include-binding-errors` |
| `audit-event` | audit-event | application + infrastructure | the strategy's own audit port (`AuditPort` + one infrastructure adapter fed by an `ApplicationEventPublisher` listener) - never a second ad-hoc logger | - |
| `metric-tag-bound` | classification-rule | config + shared | `MeterRegistry` meters over a CLOSED tag set, with a `MeterFilter`/`TagFilter` refusing unbounded tags; a tenant id or device key as a tag is a disclosure and a cardinality bomb | `management.metrics.tags` |
| `boundary-validation` | validator | interface | `jakarta.validation` constraints on the DTO + the ACTIVATION (`@Valid` on the handler parameter, or `@Validated` on the class) - an unactivated constraint is decoration | - |
| `typed-deserialization` | validator | interface | typed DTO parameter (no `Map`/`Object` body); Jackson `activateDefaultTyping` stays OFF on the `ObjectMapper` the codec builds | - |
| `opaque-reference` | policy-adapter | domain or store | no framework mechanism: the unit that MINTS the public id (`OpaqueReferenceGenerator.next(...)`) - its test asserts the id is neither derived from nor reversible to the row key, and carries no PII | - |

# Build coordinates (schedule as the stage-0 build-manifest duty - the ONE lawful stage-0 task
# the tasks phase may emit, path = the stack's build file; the parent owns versions - never write one)
| coordinate | scope |
|---|---|
| `org.springframework.boot:spring-boot-starter-security` | compile |
| `org.springframework.boot:spring-boot-starter-oauth2-resource-server` | compile, with any JWT/device token row |
| `org.springframework.boot:spring-boot-starter-validation` | compile, with `boundary-validation` |
| `org.springframework.security:spring-security-test` | **test** | An unlisted test coordinate kills the first red compile: schedule the manifest duty before any tester runs. 

# Bootability (the tree must BOOT with every claimed control)
A KEY-column entry whose runtime material the TEST tree cannot have (server TLS: `server.ssl.client-auth`,
bundle paths) is HALF the duty - `external-key-store`'s row is the pattern: resolution at boot belongs to a
named owner. The plan must pin the substitute in the request-path slice's SUPPORT-unit contract (rule (p),
`@DynamicPropertySource` registration): generate ephemeral trust material where the JDK can, otherwise
substitute the TRANSPORT keys for the test profile only - never neutralize a chain, an authorization decision
or a codec the unit's own tests assert. An unassigned substitute deadlocks the slice on the first
`@SpringBootTest` boot (`SSL is enabled but no trust material`), while every unit gate around it keeps
passing - the boot gap is invisible per-unit by construction (observed live 2026-11-18: `mutual-tls-proof`
claimed, keys written, nobody owned the boot).
THE CHAIN'S BEANS ARE BOOT FACTS TOO (2026-11-19 R3): every CONCRETE PRODUCT parameter of the chain bean
method is a collaborator of EVERY surface unit the chain guards - the surface unit pins it in its table
(rule (z6)), because a controller slice that imports the chain must construct it, and a bean the plan's
wiring law registers only in the composition root is NoSuchBeanDefinition there. Prefer a framework
interface parameter whose framework default DENIES (never count on an autoconfigured default principal);
where the concrete type is the point (a per-device manager), the pin is the duty - the doubled collaborator
comes from the table, the chain itself is never doubled in its own slice. And the credential store keeps no
empty legal state: the config contract declares the boot posture (fail-fast unseeded, or seeded test-profile
entries) instead of letting a frozen boot test invent one.
# The Spring-specific delta
- **Import boundary.** `PrincipalContextPort` (application) speaks the context's own value type -
  `Mono<PrincipalContext>`, `boolean permits(TenantScope, TenantKey)`. `SpringSecurityPrincipalAdapter`
  (infrastructure) is the ONLY class in the tree that imports `org.springframework.security.*`; it reads
  `ReactiveSecurityContextHolder` and maps claims into that record. A use case taking an `Authentication`
  parameter has leaked the framework inward and its test cannot be written without it.
- **One chain bean per composition root:** `@Configuration(proxyBeanMethods = false)` with
  `@EnableWebFluxSecurity` (reactive) or `@EnableWebSecurity` (servlet); the bean is
  `SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http)` whose body ends
  `return http.build();`, or `SecurityFilterChain filterChain(HttpSecurity http)`; the chain bean is
  the wiring unit's factory duty - one mechanism registers it.
- **`unit_kind` -> its one DAG home** (a duty is claimed in the unit that owns its kind, never in a
  filler that only recites the token): `policy-port` = application port + `policy-adapter` =
  infrastructure adapter; `ownership-predicate` = the unit that performs the lookup;
  `validator` = the interface/entry unit; `redaction` and `classification-rule` = application port +
  the egress adapter (tag bounds are the CONFIG unit's keys); `audit-event` = application port +
  infrastructure adapter + migration when queryable; `credential-handling` and `key-custody` = the
  CONFIG unit (placeholders, lifetimes, rotation windows) plus an adapter only where a codec runs.
  A kind whose realization the framework does not supply keeps the SAME home - the unit is then the
  plan's own class, and its paired test is what proves the requirement, not the citation.
- **DAG order:** ports -> predicates -> adapters -> chain bean -> inbound handler -> config unit ->
  end-to-end slice. The handler unit names its `surfaces[].name`, pins the enforcing unit and depends on it.
- Every authorization row's stage-1 test asserts permitted, denied and cross-owner cases with
  `spring-security-test`.

# The trap this table exists for
Exchange authorization decides a ROUTE, never a ROW: `.access(...)` on a matcher with no predicate at
the lookup is the IDOR the spec forbids. A chain with no terminal clause has no default, and an absent
or empty security context must fail CLOSED - never fall back to a default tenant. A widened actuator
endpoint (`management.endpoints.web.exposure.include`, default `health` only) is a NEW inbound surface:
it needs its own `surfaces[]` entry and authorization row before it ships.
