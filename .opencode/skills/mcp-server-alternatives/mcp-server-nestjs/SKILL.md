---
name: mcp-server-nestjs
description: Creates NestJS projects by calling the create_nestjs_project tool of the NestJS MCP server running in the Docker image named by NESTJS_MCP_IMAGE in the project .env file. Use when the agent must launch a stdio session for the NestJS MCP server or generate a new NestJS project.
---

# NestJS MCP server

## Purpose
Generate a NestJS project skeleton through the MCP tool `create_nestjs_project`. The server creates the project in the shared folder, validates its files, and returns a text status. The project is ready when the response contains `PROJECT READY`.

## Server facts
- Image: `NESTJS_MCP_IMAGE` from the project-root `.env`. Run all commands from the project root.
- Transport: stdio (JSON-RPC over stdin/stdout). No port, no persistent daemon.
- Volume: `$(pwd)/../mcp_workspace` mounted at `/workspace`; projects go to `/workspace/projects`.
- Tool: `create_nestjs_project(project_name: string = "hello-nestjs")`

## Step 1: Prepare the workspace and launch command
Run this block to load `.env` and create the shared folder. It does not start a container:

    export $(grep -v '^#' .env | xargs); [ -n "$NESTJS_MCP_IMAGE" ] || { echo MISSING_IMAGE; exit 1; }; mkdir -p "$(pwd)/../mcp_workspace/projects" && echo WORKSPACE_READY

- `MISSING_IMAGE`: tell the user `.env` lacks `NESTJS_MCP_IMAGE`, and stop.
- `WORKSPACE_READY`: go to Step 2.

The MCP client starts the server per session with this command. `docker run` pulls the image automatically if it is missing. Pass it as the server command in the MCP client configuration. Do not run it as a plain shell step, because it blocks on stdin:

    docker run -i --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$(pwd)/../mcp_workspace:/workspace" "$NESTJS_MCP_IMAGE"

`--user` runs the server as the host UID, so generated files are owned by the host user and the `projects` folder needs no `chown`. `HOME=/tmp` gives npm a writable home. No container is kept between sessions: stdio servers exit when their client closes stdin, and `docker exec` is never used for this server.

If the session closes immediately, report the error output of that `docker run` command and stop.

## Step 2: Collect the parameters
Ask the user for the value before calling the tool if it was not given:
- `project_name` (optional): letters, digits, `-`, `_`. Default `hello-nestjs`. The server adds a timestamp to the folder name.

## Step 3: Invoke the tool
Call `create_nestjs_project` with `project_name` through the stdio session from Step 1. The tool writes the project to `/workspace/projects/<project_name>-<timestamp>`, which is `mcp_workspace/projects/<project_name>-<timestamp>` on the host.

## Step 4: Report the result
- `PROJECT READY` in the response: tell the user the project is ready, give the path under `mcp_workspace/projects`, and the run command `npm install && npm run start:dev`.
- Error in the response: report the error text. Do not retry with the same parameters.
- Session ends without a response: report the stderr from the `docker run` output.
