# Gauntlet

The pre-flight for the blackboard pipeline. Seconds of compute instead of hours of a
live 80-unit drain discovering the same bug at agent-session prices.

## Run

```
python3 gauntlet/run_gauntlet.py            # skill-script + engine decision suites
python3 gauntlet/run_gauntlet.py --weaver   # + the Java weaver JUnit (needs maven)
```

## Layout and the neutrality rule

| file | tests | allowed vocabulary |
|---|---|---|
| `test_skill_scripts.py` | writer payload schema; run-test-tool normalization | **compiler output text lives only here** - this tool owns syntax |
| `test_engine_decisions.py` | attribution, wave sharing, attempt ledger + grants, auto-grant | structured fields only - no compiler strings |
| `ast_weaver_tools/.../JavaASTWeaver*Test.java` | weaver grammar (generics, supertypes, static reconcile, idempotency) | Java - it IS the Java tool |

Orchestrator modules must stay stack-agnostic: they read the runner's normalized
fields (`status`, `missing_symbols`, `member_demands`, `classes`) and never parse a
toolchain's text. A case that needs a compiler phrase to exist belongs in
`test_skill_scripts.py` feeding the normalization, not in the engine suite.

## History pinned here

Every incident class from the seed-002 tuning week has a case: silent payload-key
drops (W2-W5), `[ERROR]`-prefixed vs bare javac lines (G3), receiver-vs-enclosing
attribution (A1-A4, B1-B2), false scheduling-hole aborts (A5-A6), per-unit rebuild
storms (C1-C3), blind granted attempts burning sessions (D2), doomed repeats billing
sessions (D4), cascade livelock and the grant cap (E1-E6).

**Rule: no merge without a case.** A fix that ships without a fixture here is how
next week's incident is born.
