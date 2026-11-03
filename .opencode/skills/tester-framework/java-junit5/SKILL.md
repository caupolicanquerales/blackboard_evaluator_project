---
name: java-junit5
description: Use when the agent-tester writes or reviews Java unit tests with JUnit 5, AssertJ, or Mockito for a blackboard task (stage 1 red phase). Covers test structure, naming, assertions, parameterized and exception tests, Mockito doubles, and what to avoid. Test code only.
---

# java-junit5

## Rules
- Test code only, at task `path`; never edit `src/main`, `pom.xml`, scaffolds.
- Deps: only those in `pom.xml`; missing → report.
- Imports: `org.junit.jupiter.api.*`, static AssertJ. BANNED: `org.junit.Test/Assert`, `javax.*`, Hamcrest mixed with AssertJ.
- Class `<Export>Test`, package mirrors production; no `@SpringBootTest`.
- Name `method_condition_expected`; one behavior per test; <15 lines; AAA.
- No shared mutable state; `@BeforeEach` only for stateless fixtures.

## Assertions
- AssertJ: `isEqualTo`, `hasSize(n).containsExactly(..)`, `isPresent().contains(v)`, `usingRecursiveComparison()`.
- BigDecimal: `isEqualByComparingTo`.
- Several checks: `assertAll`.
- Exceptions: `assertThatThrownBy(() -> ..).isInstanceOf(T)`; no-throw: `assertThatNoException().isThrownBy(..)`.
- Parameterized: `@ParameterizedTest` + `@CsvSource`/`@ValueSource`/`@EnumSource`/`@MethodSource`.

## Mockito
- Only out-of-unit collaborators; never mock value objects, records, or unit.
- `@ExtendWith(MockitoExtension.class)`, `@Mock`, `@InjectMocks`.
- `when().thenReturn()`, `thenThrow()`, `verify(m, never())`, `verifyNoMoreInteractions`, `ArgumentCaptor`.
- Strict stubs: remove unused; `lenient()` only if intent needs. No `mockStatic`/`mockConstruction` unless intent names them.
- Simple ports: private static in-memory fake.

## Spring (only if intent requires)
- Web: `@WebMvcTest` + `@MockBean` (Boot 3.x) or `@MockitoBean` (Boot 3.4+); check pom; `MockMvc`.
- Persistence: `@DataJpaTest`, embedded DB only.
- `@SpringBootTest` only for explicit integration.

## Validation and environment
- Test every intent constraint: null, blank, negative, range, duplicate.
- Bean Validation: `Validation.buildDefaultValidatorFactory().getValidator()`, `jakarta.*`.
- Time: inject `Clock`, `Clock.fixed(..)`; never `Instant.now()`.
- Fixed ids; never `UUID.randomUUID()` for equality.
- No network, DB, or file I/O except `@TempDir Path`.

## Red phase
- Reference intent's API; if missing, keep reference and report symbol. No stubs or placeholder classes.
- Expect compile error or assertion failure; a passing test is invalid.
- Run via tool, never raw Maven:
  `python3 .opencode/skills/tester-framework/run-test-tool.py --cwd <project_root> --cmd "./mvnw -q -Dtest=<TestClass> test"`
- Use its JSON as the red-phase result: `status`, `missing_symbols`, `failures`, `counts`.
- Persist it (overwrites on each loop), piping the tool output into the writer:
  `... run-test-tool.py ... | python3 .github/skills/read-write-file-ddd/writer-red-phase/write-red-phase.py --root <project_root> --task-id <id>`
- Writer creates `blackboard/red-phase/<id>.json` with `executed: true`; the orchestrator continues only after this file exists.

## BANNED
- `assertTrue(true)`, empty tests, `@Disabled`, commented asserts.
- `toString()` or reflection on private fields; `Thread.sleep`; real timeouts.
- Catching `Exception`/`Throwable`; `try { fail(); } catch`.
- Testing framework behavior; shared static state; order dependence; `System.out`.
- Recomputing production logic for expected values.

## Output
- One class at task path; report red outcome: compile error (missing symbols) or assertion failures, with counts.
.
