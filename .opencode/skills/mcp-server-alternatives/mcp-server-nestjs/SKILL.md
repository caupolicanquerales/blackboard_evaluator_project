---
name: mcp-server-nestjs
description: Creates NestJS projects by calling the create_nestjs_project tool of the NestJS MCP server running in the Docker image named by NESTJS_MCP_IMAGE in the project .env file. Use when the agent must launch a stdio session for the NestJS MCP server or generate a new NestJS project.
---
# Purpose
Generate a NestJS skeleton via MCP tool `create_nestjs_project(project_name: string = "hello-nestjs")`. Server creates, validates, returns status text; ready marker = `PROJECT READY`.
# Facts
Image `NESTJS_MCP_IMAGE` from project-root `.env`. Transport stdio - no port/daemon. Volume `$(pwd)/../mcp_workspace` -> `/workspace`; projects in `/workspace/projects`.
# Step 1 (from project root; does not start a container)
    export $(grep -v '^#' .env | xargs); [ -n "$NESTJS_MCP_IMAGE" ] || { echo MISSING_IMAGE; exit 1; }; mkdir -p "$(pwd)/../mcp_workspace/projects" && echo WORKSPACE_READY
MISSING_IMAGE => report the missing `.env` var, stop. WORKSPACE_READY => Step 2.
# Step 2 (MCP client config, NOT a plain shell step - blocks on stdin)
    docker run -i --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$(pwd)/../mcp_workspace:/workspace" "$NESTJS_MCP_IMAGE"
`--user` keeps files host-owned (no chown); HOME=/tmp lets npm write cache; stdio server dies with the client; never `docker exec`. Image auto-pulls; immediate close => report stderr.
# Step 3: call create_nestjs_project with kebab-case project_name; `PROJECT READY` => Step 4; else report the failure verbatim.
# Step 4 Scaffold verification (mandatory)
Read `mcp_workspace/projects/<name>/package.json`: engines.node must pin the strategy's MAJOR (`">=<major>.0.0 <major+1>.0.0"`); adjust ONLY that field if it drifts, keep every generated dependency/version.
# Step 5: report name, path, `PROJECT READY`, the pin. Never edit generated code - report anomalies.
