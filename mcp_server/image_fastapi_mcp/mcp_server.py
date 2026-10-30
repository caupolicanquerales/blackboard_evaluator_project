import os
import re
import sys
import datetime
import pathlib
import py_compile

from mcp.server.fastmcp import FastMCP

PROJECTS_DIR = pathlib.Path(os.environ.get("MCP_PROJECTS_DIR", "/workspace/projects"))

mcp = FastMCP("fastapi-project-generator")


def log(message: str) -> None:
    # stdout is reserved for the MCP protocol, so logs go to stderr
    print(message, file=sys.stderr, flush=True)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return slug or "fastapi-app"


MAIN_PY = '''from fastapi import FastAPI

app = FastAPI(title="{title}")


@app.get("/health")
def health() -> dict:
    return {{"status": "ok"}}


@app.get("/")
def root() -> dict:
    return {{"message": "Hello from {title}"}}
'''

REQUIREMENTS_TXT = """fastapi>=0.110.0
uvicorn>=0.28.0
"""

README_MD = """# {title}

Generated FastAPI project.

## Run

    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

GITIGNORE = """__pycache__/
*.pyc
.venv/
venv/
.env
"""


@mcp.tool()
def create_fastapi_project(project_name: str = "hello-fastapi") -> str:
    """Generate a FastAPI project skeleton in the shared projects folder, compile it, and report the result."""
    slug = slugify(project_name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder_name = f"{slug}-{timestamp}"
    project_dir = PROJECTS_DIR / folder_name
    title = slug.replace("-", " ").title()

    log(f"Creating FastAPI project at {project_dir}")
    try:
        project_dir.mkdir(parents=True, exist_ok=False)
        (project_dir / "main.py").write_text(MAIN_PY.format(title=title), encoding="utf-8")
        (project_dir / "requirements.txt").write_text(REQUIREMENTS_TXT, encoding="utf-8")
        (project_dir / "README.md").write_text(README_MD.format(title=title), encoding="utf-8")
        (project_dir / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    except OSError as exc:
        return f"PROJECT FAILED: could not write files to {project_dir}: {exc}"

    try:
        py_compile.compile(str(project_dir / "main.py"), doraise=True)
        check = "COMPILE OK"
    except py_compile.PyCompileError as exc:
        return f"PROJECT FAILED: generated main.py does not compile: {exc.msg}"

    log(f"Project ready: {folder_name}")
    return (
        f"PROJECT READY: {folder_name}\n"
        f"Path: {project_dir}\n"
        f"Files: main.py, requirements.txt, README.md, .gitignore\n"
        f"Check: {check}\n"
        f"Run: pip install -r requirements.txt && uvicorn main:app --port 8000"
    )


if __name__ == "__main__":
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    log(f"FastAPI MCP server starting, projects dir: {PROJECTS_DIR}")
    mcp.run(transport="stdio")
