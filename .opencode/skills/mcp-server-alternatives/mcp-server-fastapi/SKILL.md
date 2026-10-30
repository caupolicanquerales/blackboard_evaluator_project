---
name: mcp-server-fastapi
description: Creates FastAPI projects by calling the create_fastapi_project tool of the FastAPI MCP server running in the Docker image caupolicanquerales/fastapi_mcp_server. Use when the agent must verify the FastAPI MCP image, launch a stdio session, or generate a new FastAPI project.
---

# FastAPI MCP server

## Purpose
Generate a FastAPI project skeleton through the MCP tool `create_fastapi_project`. The server creates the project in the shared folder, compiles it, and returns a text status. The project is ready when the response contains `COMPILE OK`.

## Server facts
- Image: `FASTAPI_MCP_IMAGE` from the project-root `.env`. Run all commands from the project root.
- Transport: stdio (JSON-RPC over stdin/stdout). No port, no persistent daemon.
- Volume: `$(pwd)/../mcp_workspace` mounted at `/workspace`; projects go to `/workspace/projects`.
- Tool: `create_fastapi_project(project_name: str = "hello-fastapi")`

## Step 1: Prepare the workspace and launch command
Run this block to load `.env` and create the shared folder. It does not start a container:

    export $(grep -v '^#' .env | xargs); [ -n "$FASTAPI_MCP_IMAGE" ] || { echo MISSING_IMAGE; exit 1; }; mkdir -p "$(pwd)/../mcp_workspace/projects" && echo WORKSPACE_READY

- `MISSING_IMAGE`: tell the user `.env` lacks `FASTAPI_MCP_IMAGE`, and stop.
- `WORKSPACE_READY`: go to Step 2.

The MCP client starts the server per session with this command. `docker run` pulls the image automatically if it is missing. Pass it as the server command in the MCP client configuration. Do not run it as a plain shell step, because it blocks on stdin:

    docker run -i --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$(pwd)/../mcp_workspace:/workspace" "$FASTAPI_MCP_IMAGE"

`--user` runs the server as the host UID so generated files are owned by the host user. `HOME=/tmp` gives pip a writable home. No container is kept between sessions: stdio servers exit when their client closes stdin, and `docker exec` is never used for this server.

If the session closes immediately, report the error output of that `docker run` command and stop.

## Step 2: Collect the parameters
Ask the user for the value before calling the tool if it was not given:
- `project_name` (optional): letters, digits, `-`, `_`. Default `hello-fastapi`. The server adds a timestamp to the folder name.

## Step 3: Invoke the tool
Call `create_fastapi_project` with `project_name` through the stdio session from Step 2. The tool writes the project to `/workspace/projects/<project_name>-<timestamp>`, which is `mcp_workspace/projects/<project_name>-<timestamp>` on the host.

## Step 4: Report the result
- `COMPILE OK` in the response: tell the user the project is ready, give the path under `mcp_workspace/projects`, and the run command `pip install -r requirements.txt && uvicorn main:app --reload`.
- Error in the response: report the error text. Do not retry with the same parameters.
- Session ends without a response: report the stderr from `docker run` output.
