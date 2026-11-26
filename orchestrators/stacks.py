"""ONE stack-toolchain registry for the whole engine (2026-11-26 consolidation).

Before this module the SAME fact - which build marker identifies which ecosystem,
what command compiles it, tests it, typechecks it, which wrapper files it carries -
lived in FIVE private copies (verification.py's if-chain, test_gate.py's shape
tables, assembly.py's marker tuple, closure.py's detection chain, ddd.py's pom.xml
fallback). Every incident added a case to whichever copy was in the blast radius,
and the copies drifted (gradle had verify commands but no scoped shape; python's
marker list differed between verification and closure; the migration gate assumed
one stack's FILE NAMING as board law). This module is the single home.

Two axes, deliberately separate:
  * ECOSYSTEM (here): toolchain facts keyed by build markers - how to build,
    test and typecheck a tree.
  * STRUCTURAL CONTRACT (assembly.STACKS): entry uniqueness, schema wiring,
    composition rules per scaffoldable framework stack.
A gradle-built Spring Boot service is contract `java-springboot` and ecosystem
`java-gradle`; neither table reaches into the other's axis.

Adding an ecosystem = one row here + its skills. No engine module may read a
build marker, wrapper name, verify command or scoped-test shape again.
"""
import pathlib
import sys


def _has(root, name):
    return (root / name).exists()


def _is_file(root, name):
    return (root / name).is_file()


# --- verification command shapes (marker-priority order = today's chain order) ----
def _verify_maven(root, mode):
    return (("mvn", "-q", "-DskipTests", "compile") if mode == "typecheck"
            else ("mvn", "-q", "-DskipTests", "package"))


def _verify_gradle(root, mode):
    gradle = str(root / "gradlew") if _has(root, "gradlew") else "gradle"
    return ((gradle, "compileJava", "-q") if mode == "typecheck"
            else (gradle, "build", "-q"))


def _verify_flutter(root, mode):
    return (("flutter", "analyze") if mode == "typecheck"
            else ("flutter", "build", "bundle"))


def _verify_angular(root, mode):
    return ((("npx", "tsc", "--noEmit") if mode == "typecheck"
             else ("npx", "ng", "build", "--configuration", "development")))


def _verify_node(root, mode):
    # node typechecks only where TypeScript is configured; it always "builds"
    if mode == "typecheck":
        if _has(root, "tsconfig.json") or _has(root, "tsconfig.app.json"):
            return ("npx", "tsc", "--noEmit")
        return None
    return ("npm", "run", "build")


def _verify_go(root, mode):
    return ("go", "vet", "./...") if mode == "typecheck" else ("go", "build", "./...")


def _verify_rust(root, mode):
    return ("cargo", "check") if mode == "typecheck" else ("cargo", "build")


def _verify_python(root, mode):
    return (sys.executable, "-m", "compileall", "-q", ".")  # same gate for both modes


ROWS = (
    {"key": "java-maven", "markers": ("pom.xml",), "wrappers": ("mvnw",),
     "verify": _verify_maven,
     "test_suffixes": (".java", ".kt", ".kts", ".scala"),
     "scoped": lambda stem, test_path, root: f"./mvnw -Dtest={stem} test",
     "closure": "java"},
    {"key": "java-gradle", "markers": ("build.gradle", "build.gradle.kts"),
     "wrappers": ("gradlew",), "verify": _verify_gradle,
     # no scoped shape: gradle module tests select by other means; closure shares java
     "test_suffixes": (".java", ".kt", ".kts", ".scala", ".groovy"),
     "scoped": None, "closure": "java"},
    {"key": "flutter", "markers": ("pubspec.yaml",), "verify": _verify_flutter,
     "test_suffixes": (), "scoped": None, "closure": None},
    {"key": "angular", "markers": ("angular.json",), "verify": _verify_angular,
     "test_suffixes": (".ts",), "scoped": None, "closure": None},
    {"key": "node", "markers": ("package.json",), "verify": _verify_node,
     "test_suffixes": (".ts", ".tsx", ".js", ".jsx", ".mjs"),
     "scoped": lambda stem, test_path, root: f"npx jest {stem}",
     "closure": "ts", "closure_requires_dir": "src"},
    {"key": "go", "markers": ("go.mod",), "verify": _verify_go,
     "test_suffixes": (".go",),
     "scoped": lambda stem, test_path, root: f"go test -run {stem} ./...",
     "closure": None},
    {"key": "rust", "markers": ("Cargo.toml",), "verify": _verify_rust,
     "test_suffixes": (".rs",), "scoped": None, "closure": None},
    {"key": "python",
     "markers": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
     "verify": _verify_python, "test_suffixes": (".py",),
     "scoped": lambda stem, test_path, root: f"python3 -m pytest {test_path}",
     "closure": "python", "closure_markers": ("pyproject.toml", "setup.py",
                                              "requirements.txt"),  # closure's OWN list (fidelity)
     "source_dirs": ("src", "app", "backend")},
)

BY_KEY = {row["key"]: row for row in ROWS}

# the JVM-family package grammar, ONE home (assembly's contract rows, the closure
# indexer and the test gate's import index all read these constants, never a literal):
# PACKAGE_REGEX searches a source string; PACKAGE_MATCH is the anchored form the
# composition-coverage rule uses on a full line.
PACKAGE_REGEX = r"package ([\w.]+);"
PACKAGE_MATCH = r"^\s*package\s+([\w.]+)\s*;"
JAVA_MARKERS = BY_KEY["java-maven"]["markers"] + BY_KEY["java-gradle"]["markers"]

# every build marker the pipeline knows, in row order (assembly's ecosystem-name
# lookup derives from this single list)
BUILD_MARKERS = tuple(dict.fromkeys(m for row in ROWS for m in row["markers"]))
WRAPPER_FILES = tuple(dict.fromkeys(w for row in ROWS for w in row.get("wrappers", ())))

# the maven/gradle dependency-classpath probe: wrapper preference, then the default
# tool (fidelity: mvnw if present, else gradlew if present, else mvn)
CLASSPATH_PROBE_WRAPPERS = ("mvnw", "gradlew")
CLASSPATH_PROBE_DEFAULT = "mvn"


def detect(root):
    """The row whose build marker is present (first wins = marker priority)."""
    root = pathlib.Path(root)
    for row in ROWS:
        if any(_has(root, m) for m in row["markers"]):
            return row
    return None


def verification_command(root, mode):
    """Stack-appropriate compile/typecheck command (None for unknown stacks)."""
    row = detect(root)
    return row["verify"](pathlib.Path(root), mode) if row else None


def scoped_test_command(test_path, root):
    """The scoped single-test command for one test file (None when no shape fits).

    Fidelity to the old chain: marker rows are consulted in SCOPED order
    (maven, node, go), then python by file suffix ALONE (no marker required)."""
    root = pathlib.Path(root)
    p = pathlib.Path(test_path)
    by_key = {r["key"]: r for r in ROWS}
    for key in ("java-maven", "node", "go"):
        row = by_key[key]
        if any(_is_file(root, m) for m in row["markers"]) and p.suffix in row["test_suffixes"]:
            return row["scoped"](p.stem, str(test_path), root)
    if p.suffix == ".py":
        return by_key["python"]["scoped"](p.stem, str(test_path), root)
    return None


def classpath_probe_runner(root):
    """Runner argv for `dependency:build-classpath` (wrapper if present, else maven)."""
    root = pathlib.Path(root)
    for name in CLASSPATH_PROBE_WRAPPERS:
        if _is_file(root, name):
            return [str(root / name)]
    return [CLASSPATH_PROBE_DEFAULT]


def closure_language(root):
    """Which import-gap parser grounds on this tree: java | python | ts | None.

    Fidelity: java by test dir OR either java build marker; ts needs package.json
    AND src/; python by its OWN marker list OR sources under its source dirs."""
    root = pathlib.Path(root)
    if (root / "src" / "test" / "java").is_dir() or any(
            _is_file(root, m) for m in ("pom.xml", "build.gradle", "build.gradle.kts")):
        return "java"
    py = BY_KEY["python"]
    if any(_is_file(root, m) for m in py["closure_markers"]) or any(
            next((root / d).rglob("*.py"), None) is not None
            for d in py["source_dirs"] if (root / d).is_dir()):
        return "python"
    node = BY_KEY["node"]
    if _is_file(root, "package.json") and (root / "src").is_dir():
        return "ts"
    return None
