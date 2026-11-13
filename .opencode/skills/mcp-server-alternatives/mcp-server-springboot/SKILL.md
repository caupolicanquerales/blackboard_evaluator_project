---
name: mcp-server-springboot
description: Creates Spring Boot Maven projects by calling the generateSpringBootProject tool of the Spring Boot MCP server running in the Docker image named by SPRINGBOOT_MCP_IMAGE in the project .env file. Use when the agent must check, start or create the springboot-mcp container, or generate a new Spring Boot project.
---
# Purpose
Spring Boot Maven project via `generateSpringBootProject(artifactId, ...)`; ready = `BUILD SUCCESS`|`PROJECT READY`.
# Facts
`SPRINGBOOT_MCP_IMAGE`/`SPRINGBOOT_MCP_PORT` (8900) from `.env`. Container `springboot-mcp`; MCP over SSE: GET /sse, POST /mcp/message?sessionId=...
# Step 1 - ensure container (one block, project root)
    export $(grep -v '^#' .env | xargs); P="${SPRINGBOOT_MCP_PORT:-8900}"; [ -n "$SPRINGBOOT_MCP_IMAGE" ] || { echo MISSING_IMAGE; exit 1; }
    S=$(docker ps -a --filter "name=^springboot-mcp$" --format '{{.Status}}')
    case "$S" in Up*) ;; "") if (command -v ss >/dev/null && ss -ltn "sport = :$P" | grep -q ":$P ") || (command -v lsof >/dev/null && lsof -iTCP:"$P" -sTCP:LISTEN >/dev/null); then echo PORT_BUSY; exit 1; fi; mkdir -p "$(pwd)/../mcp_workspace/projects"; docker run -d --name springboot-mcp --user "$(id -u):$(id -g)" -e HOME=/tmp -p "$P:8900" -v "$(pwd)/../mcp_workspace:/workspace" "$SPRINGBOOT_MCP_IMAGE" >/dev/null ;; *) docker start springboot-mcp >/dev/null ;; esac
    for i in $(seq 1 60); do c=$(curl -s -m 2 -o /dev/null -w '%{http_code}' "http://localhost:$P/sse"); [ "$c" = 200 ] && break; sleep 1; done; [ "$c" = 200 ] && echo READY || { docker logs --tail 50 springboot-mcp; echo NOT_READY; }
READY => Step 2; MISSING_IMAGE/PORT_BUSY/NOT_READY => report it + log tail, stop. Never `docker exec`; one shared container.
# Step 2
Call `generateSpringBootProject(dependencies, bootVersion, groupId, artifactId, javaVersion)`:
- `dependencies`: ONLY IDS VERIFIED IN THE LIVE METADATA. Read `curl -s https://start.spring.io/metadata/client`
  and pick the id whose name matches each plan artifact; NEVER invent or remember an id (an unknown id
  => whole request 400s). Artifacts the catalog does not list (test aggregates, reactive test libs)
  are NOT sent and NOT dropped from the plan: they are added by the Step 4 re-pin/require step,
  which writes them as BOM-managed test-scope dependencies and verifies the whole pom.
  Every plan artifact must be traceable at the end: either a metadata id was sent, or Step 4 `--require` lists it.
- `bootVersion`: NEVER silently the server default - resolve it from the intent's framework pin:
  the HIGHEST metadata release of the pinned major. If metadata lists NO release of the pinned major
  (generator retired it - 2026-11 reality: Boot 3.x is gone from Initializr while Central still
  publishes 3.5.x), that is the REPIN CASE: generate with the CURRENT catalog release and continue to
  Steps 3-4 BEFORE the move. Pass the PLAIN artifact version (`4.1.2`), NEVER the suffixed metadata
  id (`4.1.2.RELEASE` is not published on Maven Central: the container build dies on it and the tool
  returns BUILD FAILURE for a tree Step 4 could otherwise have fixed).
  The plan's pin wins over the generator's catalog; hand-editing the pom never does.
- `javaVersion` = the strategy's language pin, EXACT number. `artifactId` kebab-case (empty => default).
If the server rejects `javaVersion` as an unknown parameter, the running image predates it: report
`STALE_MCP_IMAGE` and stop - do NOT generate an unpinned scaffold. BUILD SUCCESS => Step 3 else report verbatim.
# Step 3 - verification (mandatory, all five checks; in the REPIN CASE checks 2-3 run
# AFTER Step 4 on the final pom - the generated 4.x tree is intentionally pre-repin)
`mcp_workspace/projects/<name>/pom.xml`:
1. `<java.version>` EQUALS the language pin (`21` matches "Java 21"; a `17` under any pin is drift).
2. `<parent><version>` starts with the framework pin's major (pin 3 => `3.x.x`; `4.` under a 3-pin is drift).
3. EVERY intent-named artifact appears in the pom (starter artifactIds + `spring-boot-starter-test`
   + `reactor-test` when named) - map each sent id back to its artifactId before checking.
4. `mcp_workspace/projects/<name>/mvn-build.log` contains `BUILD SUCCESS` - generation is not trusted
   from the tool's return text alone.
5. `mcp_workspace/projects/<name>/src/test/resources/application.properties` EXISTS and carries
   `spring.profiles.active=test` - the boot test's profile-activation route. It is a runtime CONFIG
   resource, not test code: when the generator omits it, the container CREATES it (this is the one
   allowed file write after generation). Without it no profile document is ever active, and the
   only route left to a green boot is H2 as a base default - production wiring fiction (seed-002
   rerun 2026-11-13 13:41 live shape).
Any miss => ONE regeneration with corrected params (fixed id list / resolved bootVersion); still missing
=> report `BLOCKED: generator lacks id <x>` with the exact list - never hand-edit the pom, never proceed.
Report name, path, java version, boot version, status; never edit generated code.
# Step 4 - re-pin when the generator retired the planned major (REPIN CASE only)
Run the skill's deterministic transformation from the repository root (it rewrites ONLY
<parent><version> to the newest release of the pinned major read live from Maven Central, collapses
Boot-4-only per-starter test slices into `spring-boot-starter-test`, adds any `--require` artifact as
a BOM-managed test dependency, verifies with `mvnw -q -DskipTests test-compile`, and RESTORES the
original pom on any failure; this scripted edit is the one sanctioned manifest change - never
hand-edit the pom yourself):
    python3 .opencode/skills/mcp-server-alternatives/mcp-server-springboot/repin-parent.py \
        --project-root ../mcp_workspace/projects/<name>-<timestamp> --major <pinned major> \
        --require <plan artifacts the generator catalog lacked, e.g. test,reactor-test>
status ok (with `to` = a <major>.x version, `changed[]` covering every catalog gap and
`verified: true`) => move to the domain root and finish; status error => report the JSON verbatim
and STOP: an unproven pin must not enter the board. The script also maps known 4.x-only starters
to their 3.x equivalents (built-in proven table: `spring-boot-starter-flyway` ->
`flyway-core`, 4.x test-slices -> `spring-boot-starter-test`, h2console dropped); a gap outside
that table fails verification, reverts itself, and must be added to the table by the operator -
never improvised around.
