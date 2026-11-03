---
name: mcp-server-springboot
description: Creates Spring Boot Maven projects by calling the generateSpringBootProject tool of the Spring Boot MCP server running in the Docker image named by SPRINGBOOT_MCP_IMAGE in the project .env file. Use when the agent must check, start or create the springboot-mcp container, or generate a new Spring Boot project.
---

# Spring Boot MCP server

## Purpose
Generate a Spring Boot Maven project through the MCP tool `generateSpringBootProject`. The server creates the project in the shared folder and returns a text status. The project is ready when the response contains `BUILD SUCCESS` or `PROJECT READY`.

## Server facts
- Image, port: `SPRINGBOOT_MCP_IMAGE` and `SPRINGBOOT_MCP_PORT` (default `8900`) from the project-root `.env`. Run all commands from the project root.
- Container: `springboot-mcp`. MCP over SSE: `GET /sse`, then `POST /mcp/message?sessionId=...`.
- Volume: `$(pwd)/../mcp_workspace` mounted at `/workspace`; projects go to `/workspace/projects`.

## Step 1: Ensure the container is up
Run this single block. It loads `.env`, reuses a running or stopped container, creates one otherwise, and waits for SSE readiness:

    export $(grep -v '^#' .env | xargs); P="${SPRINGBOOT_MCP_PORT:-8900}"; [ -n "$SPRINGBOOT_MCP_IMAGE" ] || { echo MISSING_IMAGE; exit 1; }
    S=$(docker ps -a --filter "name=^springboot-mcp$" --format '{{.Status}}')
    case "$S" in Up*) ;; "") if (command -v ss >/dev/null && ss -ltn "sport = :$P" | grep -q ":$P ") || (command -v lsof >/dev/null && lsof -iTCP:"$P" -sTCP:LISTEN >/dev/null); then echo PORT_BUSY; exit 1; fi; mkdir -p "$(pwd)/../mcp_workspace/projects"; docker run -d --name springboot-mcp --user "$(id -u):$(id -g)" -e HOME=/tmp -p "$P:8900" -v "$(pwd)/../mcp_workspace:/workspace" "$SPRINGBOOT_MCP_IMAGE" >/dev/null ;; *) docker start springboot-mcp >/dev/null ;; esac
    for i in $(seq 1 60); do c=$(curl -s -m 2 -o /dev/null -w '%{http_code}' "http://localhost:$P/sse"); [ "$c" = 200 ] && break; sleep 1; done; [ "$c" = 200 ] && echo READY || { docker logs --tail 50 springboot-mcp; echo NOT_READY; exit 1; }

Outcomes:
- `MISSING_IMAGE`: tell the user `.env` lacks the image name, and stop.
- `PORT_BUSY`: tell the user to set a free `SPRINGBOOT_MCP_PORT` in `.env`, and stop. Do not kill processes.
- `NOT_READY`: report the logs, and stop. Do not call the tool.
- `READY`: go to Step 2.

`--user` runs the server as the host UID so generated files are owned by the host user. `HOME=/tmp` gives Maven and Spring Initializr a writable home.


## Step 2: Collect parameters
- `dependencies` (required): comma-separated Spring Initializr IDs, for example `web,data-jpa,postgresql`. Ask if missing.
- `bootVersion` (optional): leave empty so Initializr uses its default GA. Pass a value only if the user asks, without `.RELEASE`.
- Java version: default to 21. The MCP tool does not accept a `javaVersion` argument, so apply it to the generated POM as described in Step 3.
- `groupId` (optional, for example `com.example`); `artifactId` (optional, default `demo`, letters, digits, `-`, `_`, `.`).

## Step 3: Invoke the tool
Call `generateSpringBootProject` on `http://localhost:$SPRINGBOOT_MCP_PORT/sse` (default `8900`). It generates the project into `/workspace/projects/<artifactId>-<timestamp>` and runs `mvn clean install -X`, logging to `mvn-build.log` in that folder.

After generation, set `<java.version>21</java.version>` in the generated `pom.xml`, then run `./mvnw clean install` from the generated project to verify Java 21 before moving or reporting the scaffold. Do not pass `javaVersion` to the MCP tool; its current schema rejects additional properties.

If Initializr rejects `bootVersion` (HTTP 400 or a version error), tell the user, ask for another GA version or offer the default, and do not halt.

## Step 4: Report
- `BUILD SUCCESS`: project ready at `mcp_workspace/projects/<folder>`; run with `./mvnw spring-boot:run`.
- Failure or `BUILD FAILURE`: report the error and the `mvn-build.log` path. Do not retry with the same parameters.
