#!/usr/bin/env python3
"""Re-pin a generated Spring Boot pom to the PLANNED major when start.spring.io retired it.

2026-11 state: the public Initializr serves only Boot 4.x, so a "Spring Boot 3" plan cannot
be generated 1:1. Maven Central still publishes every Boot 3.5.x release, and the drift
between what the generator emits and what a Boot 3 plan needs is SMALL, FIXED and KNOWN:
  1. <parent><version>            -> newest release of the pinned major (live Central lookup)
  2. spring-boot-starter-<x>-test -> the single spring-boot-starter-test (the per-starter
                                     test slices exist only in the 4.x catalog)
  3. --require entries            -> test-scope artifacts the plan names but the generator
                                     catalog no longer offers (e.g. io.projectreactor:reactor-test,
                                     versions BOM-managed, none written)
Everything else (starters, drivers, flyway modules) carries the same coordinates across both
majors and is left untouched. After the rewrite the WHOLE pom is verified with
`mvnw -q -DskipTests test-compile`; ANY failure restores the original bytes, so the board can
never inherit an unproven tree. This scripted transformation is the one sanctioned manifest
edit in the container stage - deterministic, minimal, reversible, machine-verified.

Usage:
  python3 repin-parent.py --project-root <dir> --major 3 [--require test,reactor-test] \
      [--surefire-timeout 300]
                          [--timeout 600]
Output: one JSON line {status, from, to, changed[], verified, reason?}.
Exit 0 = repinned and verified (or already conforming); 1 = nothing written / verification failed.
Standard library only.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CENTRAL_META = ("https://repo1.maven.org/maven2/org/springframework/boot/"
                "spring-boot-starter-parent/maven-metadata.xml")
RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")
TEST_SLICE_RE = re.compile(
    r"\s*<dependency>\s*<groupId>org\.springframework\.boot</groupId>\s*"
    r"<artifactId>spring-boot-starter-[\w-]+-test</artifactId>.*?</dependency>", re.S)
STARTER_TEST = ("\n\t\t<dependency>\n\t\t\t<groupId>org.springframework.boot</groupId>\n"
                "\t\t\t<artifactId>spring-boot-starter-test</artifactId>\n"
                "\t\t\t<scope>test</scope>\n\t\t</dependency>")
REQUIRED_ARTIFACTS = {  # plan-side name -> (groupId, artifactId) written without version (BOM-managed)
    "test": ("org.springframework.boot", "spring-boot-starter-test"),
    "reactor-test": ("io.projectreactor", "reactor-test"),
    # The security test aggregate: named by the architect-tier security table's Build
    # coordinates, absent from the Initializr catalog - the SAME class of artifact this
    # table exists for (2026-11-18 live: its absence made the container halt a build-manifest
    # duty mid-flight and a false [done] followed).
    "spring-security-test": ("org.springframework.security", "spring-security-test"),
}

# 4.x-only coordinates -> Boot-3 equivalents, PROVEN live against start.spring.io (2026-11)
# with a green `test-compile`. None = no 3.x equivalent; the feature is carried by an
# artifact the generated pom already keeps (h2console: autoconfig + com.h2database:h2).
CATALOG_MAP_4_TO_3 = {
    "spring-boot-starter-flyway": ("org.flywaydb", "flyway-core"),
    "spring-boot-h2console": None,
}


def _major(version: str) -> int:
    try:
        return int(str(version).split(".")[0])
    except ValueError:
        return -1


def newest_release(major: str) -> str:
    with urllib.request.urlopen(CENTRAL_META, timeout=30) as response:
        root = ET.fromstring(response.read())
    versions = [v.text.strip() for v in root.findall(".//versions/version")
                if v.text and RELEASE_RE.match(v.text.strip())
                and v.text.strip().startswith(f"{major}.")]
    if not versions:
        raise ValueError(f"Maven Central lists no spring-boot-starter-parent release {major}.x")
    return max(versions, key=lambda t: tuple(int(p) for p in t.split(".")))


def _has(text: str, artifact: str) -> bool:
    return re.search(rf"<artifactId>\s*{re.escape(artifact)}\s*</artifactId>", text) is not None


def transform(text: str, target_version: str, requires: list,
              surefire_timeout: int = 0) -> tuple:
    """Returns (new_text, changed[]) - pure, testable, no I/O."""
    changed = []
    cross_4_to_3 = False
    parent = re.search(r"<parent>.*?</parent>", text, re.S)
    if parent:
        block = parent.group(0)
        current = re.search(r"<version>\s*([^<\s]+)\s*</version>", block)
        if current and current.group(1) != target_version:
            cross_4_to_3 = _major(current.group(1)) == 4 and _major(target_version) == 3
            new_block = block[:current.start(1)] + target_version + block[current.end(1):]
            text = text.replace(block, new_block, 1)
            changed.append(f"parent {current.group(1)} -> {target_version}")
    slices = TEST_SLICE_RE.findall(text)
    if slices:
        first = text.find(slices[0])
        text = text[:first] + STARTER_TEST + text[first + len(slices[0]):]
        for extra in slices[1:]:     # drop the remaining slices (single aggregate replaces all)
            text = text.replace("\n" + extra, "", 1) if ("\n" + extra) in text \
                else text.replace(extra, "", 1)
        changed.append(f"collapsed {len(slices)} starter test-slice(s) into spring-boot-starter-test")
    for name in requires:
        group, artifact = REQUIRED_ARTIFACTS.get(name, (None, name))
        if group is None:
            raise ValueError(f"unknown --require entry {name!r}; only {sorted(REQUIRED_ARTIFACTS)}")
        if not _has(text, artifact):
            deps = re.search(r"<dependencies>.*?</dependencies>", text, re.S)
            if not deps:
                raise ValueError("pom has no <dependencies> block")
            block = deps.group(0)
            addition = ("\n\t\t<dependency>\n\t\t\t<groupId>" + group + "</groupId>\n"
                        "\t\t\t<artifactId>" + artifact + "</artifactId>\n"
                        "\t\t\t<scope>test</scope>\n\t\t</dependency>")
            text = text.replace(block, block[:-len("</dependencies>")] + addition + "\t</dependencies>", 1)
            changed.append(f"added test-scope {group}:{artifact}")
    if cross_4_to_3:
        for artifact, repl in CATALOG_MAP_4_TO_3.items():
            pattern = re.compile(
                r"\s*<dependency>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>"
                + re.escape(artifact) + r"</artifactId>.*?</dependency>", re.S)
            if not pattern.search(text):
                continue
            if repl is None:
                text = pattern.sub("", text, count=1)
                changed.append(f"dropped 4.x-only {artifact}")
            else:
                group, target_artifact = repl
                text = pattern.sub("\n\t\t<dependency>\n\t\t\t<groupId>" + group + "</groupId>\n"
                                   "\t\t\t<artifactId>" + target_artifact + "</artifactId>\n\t\t</dependency>",
                                   text, count=1)
                changed.append(f"4.x-only {artifact} -> {group}:{target_artifact}")
    if surefire_timeout and int(surefire_timeout) > 0:
        # The scaffold-intent test-run guardrail (a hung test must fail fast, never
        # freeze the suite). The generator emits no surefire block and hand-editing is
        # forbidden - without THIS scripted addition the requirement had no sanctioned
        # route and stage 0 deadlocked (live 2026-11-16 14:01: the container agent
        # generated a green project, could not add the guardrail, refused to deliver,
        # and the run died fatal on 'pom.xml was not created').
        updated = _add_surefire_timeout(text, int(surefire_timeout))
        if updated != text:
            text = updated
            changed.append(f"surefire forkedProcessTimeoutInSeconds={int(surefire_timeout)}")
    return text, changed


def _add_surefire_timeout(text: str, timeout: int) -> str:
    if "<forkedProcessTimeoutInSeconds>" in text:
        return text
    plugin = ("<plugin>\n"
              "\t\t\t\t<groupId>org.apache.maven.plugins</groupId>\n"
              "\t\t\t\t<artifactId>maven-surefire-plugin</artifactId>\n"
              "\t\t\t\t<configuration>\n"
              f"\t\t\t\t\t<forkedProcessTimeoutInSeconds>{timeout}</forkedProcessTimeoutInSeconds>\n"
              "\t\t\t\t</configuration>\n"
              "\t\t\t</plugin>")
    plugins = re.search(r"([ \t]*)<plugins>(.*?)</plugins>", text, re.S)
    if plugins:
        indent = plugins.group(1)
        return text[:plugins.end(2)] + "\n" + indent + plugin + text[plugins.end(2):]
    build = re.search(r"([ \t]*)<build>(.*?)</build>", text, re.S)
    if build:
        block = "\n\t\t<plugins>\n\t\t\t" + plugin + "\n\t\t</plugins>"
        return text[:build.end(2)] + block + text[build.end(2):]
    wrapper = ("\n\t<build>\n\t\t<plugins>\n\t\t\t" + plugin
               + "\n\t\t</plugins>\n\t</build>\n")
    return text.replace("</project>", wrapper + "</project>", 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--major", required=True, help="planned framework major, e.g. 3")
    ap.add_argument("--require", default="", help="comma list of test artifacts the plan names"
                                                  " but the generator catalog may lack"
                                                  " (test, reactor-test, spring-security-test)")
    ap.add_argument("--surefire-timeout", type=int, default=0,
                    help="seconds for maven-surefire forkedProcessTimeoutInSeconds (the"
                         " scaffold-intent test-run guardrail); 0 = leave the pom untouched")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    pom = root / "pom.xml"
    out = {"status": "error", "from": "", "to": "", "changed": [], "verified": False}
    if not pom.is_file():
        out["reason"] = f"no pom.xml under {root}"
        print(json.dumps(out))
        return 1
    original = pom.read_text(encoding="utf-8")
    try:
        target = newest_release(args.major)
    except (OSError, ValueError, ET.ParseError) as exc:
        out["reason"] = f"central metadata lookup failed: {exc}"
        print(json.dumps(out))
        return 1
    parent = re.search(r"<parent>.*?</parent>", original, re.S)
    current = re.search(r"<version>\s*([^<\s]+)\s*</version>", parent.group(0)) if parent else None
    out["from"] = current.group(1) if current else ""
    out["to"] = target
    requires = [r.strip() for r in args.require.split(",") if r.strip()]
    try:
        new_text, changed = transform(original, target, requires,
                                      surefire_timeout=args.surefire_timeout)
    except ValueError as exc:
        out["reason"] = str(exc)
        print(json.dumps(out))
        return 1
    out["changed"] = changed
    if not changed:
        out["status"], out["verified"] = "ok", True      # already conforming
        print(json.dumps(out))
        return 0
    pom.write_text(new_text, encoding="utf-8")

    wrapper = root / "mvnw"
    runner = None
    if wrapper.is_file() and any(root.glob(".mvn/wrapper/maven-wrapper.properties")):
        wrapper.chmod(wrapper.stat().st_mode | 0o755)
        runner = [str(wrapper)]
    else:
        import shutil as _shutil
        system_mvn = _shutil.which("mvn")
        if system_mvn:
            runner = [system_mvn]
    if runner is None:
        pom.write_text(original, encoding="utf-8")
        out["reason"] = ("verification could not run: no usable mvnw (missing .mvn/wrapper/) "
                         "and no system mvn on PATH; pom reverted")
        print(json.dumps(out))
        return 1
    try:
        built = subprocess.run(runner + ["-q", "-DskipTests", "test-compile"],
                               cwd=str(root), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, timeout=args.timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        pom.write_text(original, encoding="utf-8")
        out["reason"] = f"verification could not run: {exc}; pom reverted"
        print(json.dumps(out))
        return 1
    if built.returncode != 0:
        pom.write_text(original, encoding="utf-8")
        noise = ("Help 1", "re-run Maven", "Re-run Maven", "stack trace", "debug logging",
                 "possible solutions", "articles:")
        lines = [line.strip()[:180] for line in (built.stdout or "").splitlines()
                 if "ERROR" in line and not any(n in line for n in noise) and len(line.strip()) > 25]
        out["reason"] = (f"repin verification failed (pom reverted to {out['from']}): "
                         + " | ".join(lines[:4])[:400])
        print(json.dumps(out))
        return 1
    out["status"], out["verified"] = "ok", True
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
