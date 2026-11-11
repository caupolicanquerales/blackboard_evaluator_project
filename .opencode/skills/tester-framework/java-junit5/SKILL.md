---
name: java-junit5
description: Use when the agent-tester writes or reviews Java unit tests with JUnit 5, AssertJ, or Mockito for a blackboard task (stage 1 red phase). Covers test structure, naming, assertions, parameterized and exception tests, Mockito doubles, and what to avoid. Test code only.
---
# Rules
Test code only at `path`; never `src/main`/`pom.xml`. Deps: pom-declared (missing => report). Imports: org.junit.jupiter.api.*, static AssertJ; banned org.junit.*, javax.*, Hamcrest. Class `<Export>Test`; package = ast_hints.package; NO @SpringBootTest. `method_condition_expected`; one behavior/test; <15 lines; AAA; no shared state.
# Assertions
isEqualTo; hasSize(n).containsExactly(...); isPresent().contains(v); usingRecursiveComparison(); BigDecimal.isEqualByComparingTo; assertAll; assertThatThrownBy(...).isInstanceOf(T); @ParameterizedTest + @CsvSource/@EnumSource/@MethodSource.
# Doubles
Mock only out-of-unit collaborators; never records/value objects/your unit. @ExtendWith(MockitoExtension.class), @Mock/@InjectMocks; when/thenReturn/thenThrow; verify(m,never()), ArgumentCaptor; strict stubs (lenient() only if intent demands); no mockStatic/mockConstruction unless named. Simple ports: in-memory fake OK. Reactive: StepVerifier, never .blockFirst().
# Spring (only if intent requires)
Web: @WebMvcTest + @MockBean (Boot 3.x)/@MockitoBean (3.4+), MockMvc - check pom. @DataJpaTest + embedded DB. @SpringBootTest only explicit integration.
# Coverage & red
Every intent constraint: null/blank/negative/range/duplicate/boundary. Injected Clock; @TempDir; no network/system env. Expected red = compile_error (missing symbols) or assertion_failure; passing => fix the test. Nested types via enclosing type.
# Run + record
`python3 <repo>/.opencode/skills/tester-framework/run-test-tool.py --cwd <project root> --cmd "./mvnw -Dtest=<Class> test"` piped to `write-red-phase.py --root <repo> --task-id <id> --cmd "<argv>"`. Max 2 runs. Forbidden: @Disabled, always-true asserts, sleeps, unseeded random, production edits.


