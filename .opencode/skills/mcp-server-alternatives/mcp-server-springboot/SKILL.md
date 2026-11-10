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
Call it, artifactId kebab-case (empty => default); BUILD SUCCESS => Step 3 else report verbatim.
# Step 3 - verification (mandatory)
`mcp_workspace/projects/<name>/pom.xml`: `<java.version>` = strategy pin; drift => ONE regeneration (corrected params). Report name, path, status; never edit generated code.
