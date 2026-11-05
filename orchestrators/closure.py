"""Task closure: every production type the unit tests import must have a producer task.

The architect decomposes work by "units", but stage-1 tests import whole
collaborator graphs (ports, events, exceptions, repositories). Surefire compiles
the entire test source set for every run, so a single producer-less import turns
the whole domain permanently red. This module finds those gaps and can emit the
missing stage-2 producers (+ matching stage-3 evaluators) through the normal
validated queue writer.

Usage:
  python3 orchestrators/closure.py            # report gaps
  python3 orchestrators/closure.py --emit     # queue missing producer/refactor tasks

Requires a project root previously selected by an orchestrator run (default: the
first projects/<seed> layout is resolved through workspace at call time).
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import settings
import task_queue
import workspace

MAX_REPORT = 6


def _imported_classes(test_file: Path):
    """(class_name, package) pairs imported from the test file's own root package."""
    text = test_file.read_text(encoding="utf-8", errors="ignore")
    pkg = re.search(r"package ([\w.]+);", text)
    if not pkg:
        return
    root = ".".join(pkg.group(1).split(".")[:4])
    for line in text.splitlines():
        m = re.match(r"import (?:static )?([\w.]+);", line)
        if not m or not m.group(1).startswith(root + "."):
            continue
        segs = m.group(1).split(".")
        if segs[-1][:1].isupper():
            yield segs[-1], ".".join(segs[:-1])
        elif len(segs) >= 2 and segs[-2][:1].isupper():
            yield segs[-2], ".".join(segs[:-2])


def _kind_hint(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith("event"):
        return "domain event (record) carrying the fields the tests construct"
    if lowered.endswith("port") or "publisher" in lowered:
        return "domain port interface with exactly the methods the tests invoke or stub"
    if lowered.endswith("repository"):
        return "repository port interface with the find/save operations the tests stub"
    if lowered.endswith("exception"):
        return "domain exception thrown where the tests expect it"
    if lowered.endswith("status") or lowered.endswith("state") or lowered.endswith("hold"):
        return "domain enum/aggregate the tests reference"
    return "domain collaborator defined from its test usages only"


TYPE_POSITIONS = (
    r"new\s+([A-Z]\w*)\s*[(<]",
    r"\b([A-Z]\w*)\s+[a-z_$]\w*\s*[=,)]",
    r"([A-Z]\w*)\.class",
    r"instanceof\s+([A-Z]\w*)",
    r"catch\s*\(\s*([A-Z]\w*)",
    r"throws\s+([A-Z]\w*)",
    r"isInstanceOf\(\s*([A-Z]\w*)",
    r"forClass\(\s*([A-Z]\w*)\.class",
)


def _declared_in_file(text: str) -> set:
    return set(re.findall(r"\b(?:class|interface|enum|record)\s+([A-Z]\w*)", text))


def _used_without_import(text: str, imported_or_same: set, declared: set) -> set:
    """Uppercase names appearing in type position that the file neither imports nor declares."""
    found = set()
    for pattern in TYPE_POSITIONS:
        found |= set(re.findall(pattern, text))
    blocklist = {"Test", "BeforeEach", "AfterEach", "BeforeAll", "AfterAll", "Nested",
                 "DisplayName", "TempDir", "Timeout", "RepeatedTest", "EnumSource",
                 "CsvSource", "MethodSource", "ValueSource", "Mock"}
    blocklist |= {"String", "UUID", "List", "Map", "Set", "Optional", "LocalDate",
                  "LocalDateTime", "ZoneId", "LocalTime", "Instant", "Duration", "BigDecimal",
                  "BigInteger", "Integer", "Long", "Double", "Object", "Class", "Exception",
                  "RuntimeException", "Thread", "Arrays", "Collections", "ChronoUnit",
                  "Collectors", "Stream", "IllegalArgumentException", "IllegalStateException",
                  "NullPointerException", "UnsupportedOperationException", "NumberFormatException",
                  "ClassCastException", "ArithmeticException", "IndexOutOfBoundsException",
                  "ConcurrentModificationException", "TimeoutException", "Iterable", "Enum",
                  "Record", "Void", "Boolean", "Byte", "Short", "Character", "Comparable"}
    return found - imported_or_same - declared - blocklist


def gaps(service_root: Path, slug: str, index: dict) -> list:
    """Types this domain's tests reference (imports or type positions) with no producer."""
    test_root = service_root / "src" / "test" / "java"
    main_root = service_root / "src" / "main" / "java"
    if not test_root.is_dir():
        return []
    produced = {task["export"].split(".")[-1] for task in index.values()
                if task.get("project") == slug and isinstance(task.get("stage"), int)
                and task["stage"] == settings.TDD_STAGE}
    produced |= {f.stem for f in main_root.rglob("*.java")}
    missing = {}
    for f in test_root.rglob("*.java"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        pkg_match = re.search(r"package ([\w.]+);", text)
        own_pkg = pkg_match.group(1) if pkg_match else ""
        imported_simple = set(re.findall(r"import (?:static )?[\w.]*?\.([A-Z]\w*);", text))
        declared = _declared_in_file(text) | {
            n for other in test_root.rglob("*.java") if other != f
            for n in (_declared_in_file(other.read_text(encoding="utf-8", errors="ignore"))
                      if other.parent == f.parent else set())}
        for cls, pkg in _imported_classes(f):
            if cls not in produced and cls not in missing:
                missing[cls] = {"class": cls, "package": pkg, "test": f.name}
        for cls in _used_without_import(text, imported_simple | produced, declared):
            if cls not in missing:
                missing[cls] = {"class": cls, "package": own_pkg, "test": f.name}
    return list(missing.values())


def _build_task(stage: int, task_id: str, slug: str, gap: dict, scaffold_id: str, tester_id: str | None) -> dict:
    pkg_path = gap["package"].replace(".", "/")
    rel_path = f"src/main/java/{pkg_path}/{gap['class']}.java"
    layer = "application" if ".application" in "." + gap["package"] else "domain"
    depends = [scaffold_id] + ([tester_id] if tester_id else [])
    return {
        "id": task_id,
        "targetAgent": settings.STAGE_AGENTS[stage],
        "stage": stage,
        "dependsOn": depends,
        "path": rel_path,
        "kind": settings.STAGE_KINDS[stage][0],
        "layer": layer,
        "feature": None,
        "export": gap["class"],
        "intent": (f"Bounded context {slug}: define {gap['class']} ({_kind_hint(gap['class'])}) in "
                   f"package {gap['package']}. Contract is fixed by its usage in test {gap['test']}; "
                   "implement the smallest correct type that satisfies every usage."),
        "project": slug,
    }


def emit_all(report=print) -> int:
    root = workspace.get_project_root()
    emitted = 0
    for service in sorted((root / settings.PROJECTS_SUBDIR).glob("*")) if (root / settings.PROJECTS_SUBDIR).is_dir() else []:
        slug = service.name
        for gap in gaps(service, slug, task_queue.load_index()):
            scaffold_id = task_queue.scaffold_task_id(slug)
            tester_id = next((t["id"] for _, t in sorted(task_queue.load_index().items())
                              if t.get("project") == slug and t.get("stage") == settings.TESTER_STAGE
                              and gap["test"] in str(t.get("path", ""))), None)
            t2_id = task_queue.next_task_id(settings.TDD_STAGE)
            batch = [_build_task(settings.TDD_STAGE, t2_id, slug, gap, scaffold_id, tester_id)]
            t3_id = task_queue.next_task_id(3)
            t3 = _build_task(3, t3_id, slug, gap, scaffold_id, tester_id)
            t3["dependsOn"] = [t2_id]
            batch.append(t3)
            tmp = Path(tempfile.mkdtemp(prefix="closure-"))
            paths = []
            for task in batch:
                p = tmp / f"{task['id']}-{slug}.json"
                p.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
                paths.append(str(p))
            reason = task_queue.emit_tasks(paths)
            if reason:
                report(f"[closure] skipped {slug}/{gap['class']}: {reason}")
                continue
            emitted += len(batch)
    return emitted


def main() -> int:
    ap = argparse.ArgumentParser(description="Report or close task-closure gaps (test imports without producers).")
    ap.add_argument("--emit", action="store_true", help="queue the missing stage-2/3 tasks")
    ap.add_argument("--project-root", help="generated project root (default: orchestrator layout under projects/)")
    args = ap.parse_args()
    if args.project_root:
        workspace.set_project_root(args.project_root)

    total = 0
    root = workspace.get_project_root()
    services = sorted((root / settings.PROJECTS_SUBDIR).glob("*")) if (root / settings.PROJECTS_SUBDIR).is_dir() else []
    for service in services:
        found = gaps(service, service.name, task_queue.load_index())
        total += len(found)
        names = [g["class"] for g in found][:MAX_REPORT]
        print(f"{service.name:16} gaps={len(found):2} {names}")
    if args.emit:
        print("---- emitting ----")
        print("emitted tasks:", emit_all())
    return 0 if total or args.emit else 1


if __name__ == "__main__":
    sys.exit(main())
