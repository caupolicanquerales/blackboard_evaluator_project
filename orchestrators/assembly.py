"""Stage 4: application assembly (stack-agnostic engine, stack rules in skills).

Every scoped gate in the pipeline proves ONE unit; none of them boots the
application. Unit tests build collaborators directly with `new`/mocks, so a
production class the framework container cannot supply (an unregistered service, a
port without an adapter, a driver without configuration) passes every unit gate and
still cannot start. The scaffold's own smoke test is the only contract that boots the
whole application, and it exists in every stack this factory scaffolds.

The engine only DETECTS that smoke test per stack and re-runs it as a deterministic gate
after every assembly session. Stacks are DATA: the `STACKS` registry carries each stack's
skill path, composition-root probe (glob + marker + launch requirement) and schema-runner
markers; the probes below only pick smoke test + command. Adding a language/framework
means adding ONE registry row + one probe + one skill - no structural rule in this module
branches on a stack name. All framework vocabulary - failure reading, the ordered fix
menu, the editable roots - lives in one skill per stack:
`.opencode/skills/assembly-framework/<language>-<framework>/`.
`assembly.ensure_tasks()` queues ONE stage-4 task per domain (structurally drained
last: the engine walks stages in ascending order). No blackboard artifact:
completion is the green boot itself, evaluated by the orchestrator, never reported
by the agent.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import settings
import task_queue
import tasks
import test_gate
import workspace

SKILL_FAMILY = "assembly-framework"

# Assembly contract registry: one DATA row per stack the pipeline can scaffold.
# Entry uniqueness and schema-wiring rules are evaluated generically from these rows, so
# adding a stack means: register a probe, add one row here, ship the assembly skill.
# No structural decision reads a stack name through if/elif anywhere else in the module.
STACKS = {
    "java-springboot": {
        "skill": SKILL_FAMILY + "/java-springboot/SKILL.md",
        "entry_label": "@SpringBootApplication classes",
        "entry_globs": ("src/main/java/**/*.java",),
        "entry_marker": "@SpringBootApplication",
        "entry_launch": "public static void main",
        "entry_excludes": (".spec.", ".test."),
        "schema_globs": ("pom.xml", "build.gradle", "build.gradle.kts",
                         "src/main/resources/*"),
        "schema_markers": ("flyway", "liquibase", "sql.init"),
        # seed-002 D3/L3: the marker check alone is marker-deep. A runner that exists
        # but reads an EMPTY locations folder boots green over a schema-less runtime.
        # The alignment rule below asserts the configured locations actually contain
        # the db/migrations scripts. `locations_keys` are the runtime property names
        # (framework namespace REQUIRED: spring.flyway.locations, never bare
        # flyway.locations in a file no runtime reads); `classpath_roots` is where a
        # classpath: location physically resolves to.
        "locations_keys": ("spring.flyway.locations", "flyway.locations", "locations"),
        "locations_props_globs": ("src/main/resources/application*.yml",
                                  "src/main/resources/application*.yaml",
                                  "src/main/resources/application*.properties"),
        "classpath_roots": ("src/main/resources",),
        "schema_hint": "add a migration runner (flyway/liquibase) or spring.sql.init.schema-locations",
        # seed-002 rerun F3: the VACUOUS boot. A composition root that cannot see the
        # domain packages boots a context with NONE of the application, and the smoke
        # test (which lives beside the entry) goes 1/1 green over a dead service. The
        # probe is grammar-deep but stack-neutral: the entry file's package must be an
        # ancestor-or-self of every other main-source package, UNLESS the entry spells
        # one of the row's coverage markers (scan/config directives). Stacks without
        # a package_regex row key (explicit module graphs) skip the rule.
        "package_regex": r"^\s*package\s+([\w.]+)\s*;",
        "coverage_markers": ("scanBasePackages", "basePackages", "ComponentScan"),
        # seed-002 rerun, 13:45 live shape: @SpringBootTest/@DataR2dbcTest-style tests
        # find the configuration by searching packages UPWARDS from the test class -
        # a search that IGNORES scan directives. The assembly agent declared
        # scanBasePackages, the smoke test went green, and two slice tests stayed
        # red forever ("Unable to find a @SpringBootConfiguration by searching
        # packages upwards") with NO payload able to fix them: the entry point must
        # be an ANCESTOR PACKAGE of every context-discovering test, marker or not.
        "test_globs": ("src/test/java/**/*.java",),
        "slice_markers": ("@SpringBootTest", "@DataR2dbcTest", "@DataJpaTest",
                          "@WebFluxTest", "@WebMvcTest", "@JsonTest", "@JdbcTest"),
        "slice_exempt_regex": r"classes\s*=|@ContextConfiguration",
    },
    "typescript-nestjs": {
        "skill": SKILL_FAMILY + "/typescript-nestjs/SKILL.md",
        "entry_label": "modules calling NestFactory.create",
        "entry_globs": ("src/**/*.ts",),
        "entry_marker": "NestFactory.create",
        "entry_launch": "",
        "entry_excludes": (".spec.ts", ".test.ts"),
        "schema_globs": ("package.json", "src/**/*.ts"),
        "schema_markers": ("typeorm", "mikro-orm", "knex", "prisma", "migration"),
        "locations_keys": (),
        "locations_props_globs": ("src/**/*.ts", "ormconfig.json", ".env"),
        "classpath_roots": ("src", "."),
        "schema_hint": "wire the ORM migration tooling (TypeORM/Prisma/knex migrations)",
    },
    "python-fastapi": {
        "skill": SKILL_FAMILY + "/python-fastapi/SKILL.md",
        "entry_label": "app factories (FastAPI instances)",
        "entry_globs": ("src/**/main.py", "app/**/main.py", "backend/**/main.py"),
        "entry_marker": "FastAPI(",
        "entry_launch": "",
        "entry_excludes": (),
        "schema_globs": ("pyproject.toml", "requirements.txt"),
        "schema_markers": ("alembic",),
        "locations_keys": ("script_location", "version_locations"),
        "locations_props_globs": ("alembic.ini", "*.ini", "src/**/settings.py", "app/**/settings.py"),
        "classpath_roots": (".", "src", "app"),
        "schema_hint": "add alembic (or an in-tree migrations package) to apply the schema",
    },
}

# Build markers whose ecosystem the pipeline knows: when one exists but no probe matched,
# that is a scaffold defect, NOT an unknown stack - the log must say which.
_ECOSYSTEM_MARKERS = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json",
                      "pyproject.toml", "setup.py", "requirements.txt", "go.mod", "Cargo.toml")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _matched(service_root: Path, patterns, excludes=()):
    found = set()
    for pattern in patterns:
        for f in service_root.glob(pattern):
            if f.is_file() and not any(x in f.name for x in excludes):
                found.add(f)
    return sorted(found)


def _entry_problems(service_root: Path, stack: str) -> list:
    """One composition root only, and it must be launchable: rules from STACKS data."""
    row = STACKS.get(stack) or {}
    marker = row.get("entry_marker")
    if not marker or not row.get("entry_globs"):
        return []
    candidates = [f for f in _matched(service_root, row["entry_globs"],
                                      row.get("entry_excludes", ()))
                  if marker in _read(f)]
    problems = []
    if len(candidates) > 1:
        problems.append(f"multiple {row['entry_label']} found: "
                        + ", ".join(str(f.relative_to(service_root)) for f in candidates)
                        + " - keep exactly one composition root (collapse the duplicate)")
    if candidates and row.get("entry_launch") and \
            not any(row["entry_launch"] in _read(f) for f in candidates):
        problems.append(f"{row['entry_label']} exist but none can start the application "
                        f"(no {row['entry_launch']!r} in any of them)")
    return problems


def _coverage_problems(service_root: Path, stack: str) -> list:
    """Hollow-boot guard (seed-002 rerun F3): the smoke test boots beside the entry, so
    the booted context can only contain what the entry can SEE. A plan that pins one
    code root while the scaffolded entry lands in the generator's default package
    (Initializr's groupId is not a decision) boots green over a context with NONE of
    the application: no controller, no wiring, dead service, 1/1 gate. Rules read the
    STACKS row only; stacks without package grammar skip it.

    Two halves, one exemption each:
      (1) MAIN sources under packages the entry cannot see - waivable by declaring scan
          coverage (the directive genuinely fixes component scanning);
      (2) context-DISCOVERING tests (@SpringBootTest/@DataR2dbcTest slices) whose package
          does not contain the entry - NOT waivable by any marker, because the upward
          package search that locates @SpringBootConfiguration never reads scan
          directives. The only fix is moving the composition root to the shared root
          package of code and tests."""
    row = STACKS.get(stack) or {}
    pkg_re, markers = row.get("package_regex"), row.get("coverage_markers", ())
    if not pkg_re or not row.get("entry_globs") or not row.get("entry_marker"):
        return []
    candidates = [f for f in _matched(service_root, row["entry_globs"],
                                      row.get("entry_excludes", ()))
                  if row["entry_marker"] in _read(f)]
    if not candidates:
        return []
    entry_texts = [(f, _read(f)) for f in candidates]
    roots = set()
    for _, text in entry_texts:
        for match in re.finditer(pkg_re, text, re.M):
            roots.add(match.group(1))
    if not roots:
        return []
    declared = any(marker in text for _, text in entry_texts for marker in markers)
    problems = []
    if not declared:                      # (1) component scan: the marker waives it
        seen = {f for f, _ in entry_texts}
        invisible = set()
        for f in _matched(service_root, row["entry_globs"], row.get("entry_excludes", ())):
            if f in seen:
                continue
            match = re.search(pkg_re, _read(f), re.M)
            if not match:
                continue
            pkg = match.group(1)
            if not any(pkg == root or pkg.startswith(root + ".") for root in roots):
                invisible.add(pkg)
        if invisible:
            problems.append(
                f"composition root {sorted(roots)} cannot see main sources under other "
                f"package roots [{', '.join(sorted(invisible)[:3])}]: the boot smoke test "
                "loads a context with NONE of the application and stays green over a dead "
                f"service (seed-002 F3) - move the entry above the code root or declare "
                f"scan coverage ({', '.join(markers)})")
    discovering = set()                   # (2) slice discovery: NO marker waives it
    for f in _matched(service_root, row.get("test_globs", ())):
        text = _read(f)
        if not any(marker in text for marker in row.get("slice_markers", ())):
            continue
        if row.get("slice_exempt_regex") and re.search(row["slice_exempt_regex"], text):
            continue                      # explicit classes=/@ContextConfiguration: no search
        match = re.search(pkg_re, text, re.M)
        if not match:
            continue
        pkg = match.group(1)
        if not any(pkg == root or pkg.startswith(root + ".") for root in roots):
            discovering.add(pkg)
    if discovering:
        problems.append(
            f"context-discovering test(s) under [{', '.join(sorted(discovering)[:3])}] search "
            f"UPWARDS for the configuration and cannot reach the entry {sorted(roots)} - "
            "scan directives do NOT fix this search: move the composition root to the shared "
            "root package of the code and the tests (seed-002 rerun 13:45: two slice units "
            "unweavable-red forever behind a green smoke test)")
    return problems


def _schema_problems(service_root: Path, stack: str) -> list:
    """db/migrations SQL must be APPLIED by something, or the schema is fiction (P0-2).

    The runner evidence is searched per the stack row's markers; additionally an
    in-tree migrations package satisfies the rule. The assembly unit - the only stage
    allowed to touch wiring - is what this failure redirects.
    """
    migrations = service_root / "db" / "migrations"
    if not migrations.is_dir() or not any(migrations.glob("*.sql")):
        return []
    row = STACKS.get(stack) or {}
    blob = " ".join(_read(f) for f in _matched(service_root, row.get("schema_globs", ())))
    blob = blob.lower()
    if any(marker in blob for marker in row.get("schema_markers", ())):
        return _migration_alignment_problems(service_root, stack)
    if any((service_root / d).is_dir() for d in
           ("alembic", "migrations", "src/migrations", "src/alembic",
            "app/migrations", "backend/migrations", "db/migrations/versions")):
        return _migration_alignment_problems(service_root, stack)
    hint = row.get("schema_hint", "register the stack in assembly.STACKS with its runner markers")
    return [f"db/migrations/*.sql exist but nothing applies them - {hint}: "
            "the app boots and dies on its first real query"]


def _configured_location_tokens(service_root: Path, stack: str) -> list:
    """Locations the RUNTIME is told to read, from the framework's own property
    namespace (spring.flyway.locations / alembic script_location / ...). Keys outside
    the runtime namespace are inert and only match inside files the probe reads."""
    row = STACKS.get(stack) or {}
    keys = row.get("locations_keys") or ()
    tokens = []
    if not keys:
        return tokens
    for f in _matched(service_root, row.get("locations_props_globs", ())):
        text = _read(f)
        for key in keys:
            for match in re.finditer(re.escape(key) + r"\s*[=:]\s*[\"']?([^\"'\n;,]+)", text):
                tokens.extend(tok.strip() for tok in match.group(1).split(",") if tok.strip())
    return tokens


def _resolve_location(service_root: Path, token: str, stack: str) -> list:
    """Concrete folders one location token addresses (classpath:X resolves under the
    stack's resource roots; filesystem: and plain paths under the service root)."""
    row = STACKS.get(stack) or {}
    roots = row.get("classpath_roots") or (".",)
    raw = token.strip()
    for prefix in ("classpath:", "filesystem:", "file:"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            if prefix == "classpath:":
                return [service_root / r / raw for r in roots]
            break
    return [service_root / raw]


def _migration_alignment_problems(service_root: Path, stack: str) -> list:
    """seed-002 D3 step 4 (§10.5 upgrade): marker-deep became ALIGNMENT-deep.

    When db/migrations/*.sql exist and a runner is wired, every migration filename
    must be discoverable under the locations the runtime actually reads. Boot-green
    over an empty locations folder is a schema-less runtime, not a green gate.
    """
    wanted = {f.name for f in (service_root / "db" / "migrations").glob("*.sql")}
    tokens = _configured_location_tokens(service_root, stack)
    if tokens:
        dirs = [d for token in tokens for d in _resolve_location(service_root, token, stack)]
        seen = {str(d) for d in dirs}
        if not any(d.is_dir() for d in dirs):
            return [f"configured schema locations {sorted(seen)} resolve to no existing folder "
                    f"- the {len(wanted)} db/migrations scripts would never run"]
        visible = set()
        for d in dirs:
            if d.is_dir():
                visible |= {f.name for f in d.rglob("*") if f.is_file()}
        missing = sorted(wanted - visible)
        if missing:
            return [f"db/migrations/*.sql exist but the configured locations "
                    f"({', '.join(sorted(seen))}) carry none of them ({missing[:3]}...) - "
                    "copy the scripts under the locations folder or point the runner at "
                    "db/migrations; boot-green over an empty locations folder is a "
                    "schema-less runtime (seed-002 D3/L3)"]
        return []
    # No location key configured anywhere: the migrations must at least live under a
    # conventional runner folder the marker implies (in-tree package = its own location).
    script_suffixes = {".sql", ".py", ".ts", ".js", ".mjs", ".cjs"}
    candidates = [f for f in _matched(service_root, ("src/main/resources/db/migration/*",
                                                     "src/main/resources/migrations/*",
                                                     "db/migrations/versions/*",
                                                     "migrations/*", "src/migrations/*",
                                                     "alembic/versions/*", "app/migrations/*"))
                  if f.suffix in script_suffixes and f.name != "__init__.py"]
    if wanted and candidates:
        return []
    return [f"db/migrations has {len(wanted)} scripts and the wired runner names no locations "
            "folder that contains them - configure the locations in the runtime property "
            "namespace (e.g. spring.flyway.locations) pointing at a folder holding these "
            "files (seed-002 D3: flyway.locations in an unread profile file is inert)"]


def _detect_java(service_root: Path):
    """Spring Boot probe: @SpringBootTest smoke class + @SpringBootApplication entry."""
    test_root = service_root / "src" / "test" / "java"
    main_root = service_root / "src" / "main" / "java"
    if not (main_root.is_dir() and test_root.is_dir()):
        return None
    smoke = next((f for f in sorted(test_root.rglob("*Test*.java"))
                  if "@SpringBootTest" in _read(f)), None)
    annotated = [f for f in sorted(main_root.rglob("*.java"))
                 if "@SpringBootApplication" in _read(f)]
    entry = next((f for f in annotated if "public static void main" in _read(f)),
                 annotated[0] if annotated else None)
    if smoke is None or entry is None:
        return None
    runner = "./mvnw" if (service_root / "mvnw").is_file() else "mvn"
    return {"stack": "java-springboot", "class": smoke.name[:-5],
            "command": f"{runner} -Dtest={smoke.name[:-5]} test", "entry": entry,
            "test_file": smoke}


def _detect_nestjs(service_root: Path):
    """NestJS probe: e2e spec compiled by the package's own test:e2e script."""
    manifest = service_root / "package.json"
    entry = service_root / "src" / "main.ts"
    if not manifest.is_file() or not entry.is_file():
        return None
    try:
        package = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    script = next((name for name in (package.get("scripts") or {})
                   if name.startswith("test:e2e") or name == "test-e2e"), None)
    if script is None:
        return None
    test_root = service_root / "test"
    smoke = next(iter(sorted(test_root.rglob("*.e2e-spec.ts"))), None) if test_root.is_dir() else None
    if smoke is None:
        return None
    return {"stack": "typescript-nestjs", "class": smoke.name,
            "command": f"npm run {script}", "entry": entry, "test_file": smoke}


def _detect_fastapi(service_root: Path):
    """FastAPI probe: the scaffold smoke test that builds the app object with TestClient."""
    build = (service_root / "pyproject.toml").is_file() or (service_root / "requirements.txt").is_file()
    if not build:
        return None
    entry = next((service_root / c / "main.py" for c in ("app", "src", "backend")
                  if (service_root / c / "main.py").is_file()
                  and "FastAPI" in _read(service_root / c / "main.py")), None)
    if entry is None:
        return None
    tests = service_root / "tests"
    smoke = next((f for f in sorted(tests.rglob("test_*.py"))
                  if "TestClient" in _read(f)), None) if tests.is_dir() else None
    if smoke is None:
        return None
    rel = smoke.relative_to(service_root).as_posix()
    return {"stack": "python-fastapi", "class": smoke.name,
            "command": f"python3 -m pytest {rel}", "entry": entry, "test_file": smoke}


DETECTORS = (_detect_java, _detect_nestjs, _detect_fastapi)


def detect(service_root: Path):
    """Assembly contract for one domain service, or None when no registered probe matches.

    Structural problems (composition-root uniqueness, schema wiring) are evaluated for
    EVERY stack from the STACKS row; a probe returning an unregistered stack is reported
    instead of crashing the drain.
    """
    for probe in DETECTORS:
        found = probe(service_root)
        if not found:
            continue
        row = STACKS.get(found["stack"])
        found.setdefault("problems", [])
        if row is None:
            found["skill"] = None
            found["problems"].append(
                f"stack {found['stack']!r} has no assembly.STACKS row: cannot evaluate "
                "entry/schema rules or load a skill - register it or extend the probe")
            return found
        found["skill"] = row["skill"]
        found["problems"] = found["problems"] + _entry_problems(service_root, found["stack"]) \
            + _coverage_problems(service_root, found["stack"]) \
            + _schema_problems(service_root, found["stack"])
        return found
    return None


def ensure_tasks(report=print):
    """Queue one stage-4 assembly task per domain that has a smoke test. Idempotent."""
    root = workspace.get_project_root()
    services = sorted((root / settings.PROJECTS_SUBDIR).glob("*")) \
        if (root / settings.PROJECTS_SUBDIR).is_dir() else []
    for service in services:
        slug = service.name
        index = task_queue.load_index()
        if any(t.get("project") == slug and t.get("stage") == settings.ASSEMBLY_STAGE
               for t in index.values()):
            continue  # already queued or completed: ids are never re-emitted
        contract = detect(service)
        if contract is None:
            known = next((m for m in _ECOSYSTEM_MARKERS if (service / m).exists()), None)
            report(f"[asm  ] {slug}: " + (
                f"known ecosystem ({known}) but no smoke-test contract - the scaffold task did "
                f"not produce the boot test; assembly not scheduled" if known else
                "stack not registered in assembly detectors; assembly not scheduled"))
            continue
        task = {
            "id": task_queue.next_task_id(settings.ASSEMBLY_STAGE),
            "targetAgent": settings.STAGE_AGENTS[settings.ASSEMBLY_STAGE],
            "stage": settings.ASSEMBLY_STAGE,
            # No dependsOn: the engine drains stages in ascending order, so stage 4
            # structurally runs after every stage-3 task of the pass. Empty deps also
            # survive the quarantining of a failed T3, which would dangle a dependency.
            "dependsOn": [],
            "path": str(contract["entry"].relative_to(service)).replace("\\", "/"),
            "kind": settings.STAGE_KINDS[settings.ASSEMBLY_STAGE][0],
            "layer": "root",
            "feature": None,
            "export": contract["entry"].stem,
            "intent": (f"Bounded context {slug}: boot the generated application. The scaffold "
                       f"smoke test {contract['class']} proves the full application wiring "
                       f"resolves: every collaborator the framework must construct at startup "
                       f"(services, adapters for ports, drivers, configuration) exists. Detect "
                       f"the stack and load your assembly skill ({contract['skill']}); its fix "
                       f"menu and editable roots govern everything you change. Assembly gate "
                       f"command (argv-only, run it through run-test-tool, never invent "
                       f"another): {contract['command']}. Edit production sources only; never "
                       f"touch tests, build manifests, migrations, or another domain."),
            "project": slug,
        }
        tmp = Path(tempfile.mkdtemp(prefix="assembly-"))
        p = tmp / tasks.task_file_name(task)
        p.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        reason = task_queue.emit_tasks([str(p)])
        report(f"[asm  ] {slug}: {'queued ' + task['id'] if not reason else reason}")


def gate(task):
    """(ok, reason): the deterministic stage-4 verification - boot the application, no LLM."""
    service = workspace.project_root_for(task["project"])
    contract = detect(service)
    if contract is None:
        return False, "assembly smoke test vanished from the tree"
    problems = contract.get("problems") or []
    if problems:
        return False, "assembly gate (structural): " + "; ".join(problems)
    test_gate.ensure_wrapper_executables(service)
    tool_command = [
        sys.executable, str(settings.RUN_TEST_TOOL),
        "--cwd", str(service),
        "--cmd", contract["command"],
        "--timeout", str(settings.TEST_GATE_TIMEOUT),
    ]
    print(f"[asm  ] {task['id']} booting the application ({contract['stack']}): "
          f"{contract['command']}")
    try:
        completed = subprocess.run(
            tool_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=settings.TEST_GATE_TIMEOUT + 30,
            cwd=str(settings.ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"assembly gate could not run: {exc}"
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False, f"assembly gate produced unparseable output: {completed.stdout.strip()[:400]}"
    if not isinstance(result, dict):
        return False, f"assembly gate produced unexpected output: {str(result)[:400]}"
    if result.get("status") == "passed":
        counts = result.get("counts") or {}
        print(f"[asm  ] {task['id']} green ({counts.get('run', '?')} tests passed): "
              "the application boots")
        return True, ""
    detail = test_gate._failure_detail(result) if hasattr(test_gate, "_failure_detail") \
        else json.dumps(result)[:400]
    return False, f"assembly gate: {detail[:900]}"
