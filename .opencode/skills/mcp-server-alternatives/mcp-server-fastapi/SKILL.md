---
name: mcp-server-fastapi
description: Creates FastAPI projects by calling the create_fastapi_project tool of the FastAPI MCP server running in the Docker image caupolicanquerales/fastapi_mcp_server. Use when the agent must verify the FastAPI MCP image, launch a stdio session, or generate a new FastAPI project.
---
# Purpose
Generate a FastAPI skeleton via MCP tool `create_fastapi_project(project_name: str = "hello-fastapi")`. Server creates, compiles, returns status text; ready marker = `COMPILE OK`.
# Facts
Image `FASTAPI_MCP_IMAGE` from project-root `.env`. Transport stdio (JSON-RPC over stdin/stdout) - no port, no daemon. Volume `$(pwd)/../mcp_workspace` -> `/workspace`; projects land in `/workspace/projects`.
# Step 1 (run from project root; does NOT start a container)
    export $(grep -v '^#' .env | xargs); [ -n "$FASTAPI_MCP_IMAGE" ] || { echo MISSING_IMAGE; exit 1; }; mkdir -p "$(pwd)/../mcp_workspace/projects" && echo WORKSPACE_READY
MISSING_IMAGE => tell the user `.env` lacks the var, stop. WORKSPACE_READY => Step 2.
# Step 2 (MCP client config, NOT a plain shell step - it blocks on stdin)
    docker run -i --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$(pwd)/../mcp_workspace:/workspace" "$FASTAPI_MCP_IMAGE"
`--user` gives host-owned files; HOME=/tmp gives pip a writable home; stdio exits with the client - never `docker exec`, no container kept. Image auto-pulls on first run; session closes immediately => report its stderr.
# Step 3: call create_fastapi_project with project_name kebab-case; `COMPILE OK` => Step 4; else report exactly what failed.
# Step 4 Scaffold verification (mandatory before reporting ready)
Read `mcp_workspace/projects/<name>/requirements.txt`; pin the MAJOR version the strategy names (replace loose `fastapi` / `uvicorn` lines with `fastapi==<major>.*` style + compatible `uvicorn[...]`). Re-check the file reflects the pin.
# Step 5: report name, path, `COMPILE OK`, the pin applied. No edits to generated code - report issues instead.
