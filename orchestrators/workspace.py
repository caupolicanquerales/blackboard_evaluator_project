"""Seed and project-root resolution (the mutable part of the layout).

``PROJECT_ROOT`` is the generated project folder chosen once per orchestrator run;
domain projects live under ``<PROJECT_ROOT>/services/<slug>``.
"""
import re
from pathlib import Path

import settings


def slugify(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()


def resolve_seed(seed_arg):
    if seed_arg:
        path = Path(seed_arg).expanduser()
        if not path.is_absolute():
            path = settings.ROOT / path
        return path.resolve()
    if not settings.SEED_DIR.is_dir():
        return None
    candidates = sorted(settings.SEED_DIR.glob("*_description.md"))
    if not candidates:
        candidates = sorted(settings.SEED_DIR.glob("*.md"))
    return candidates[0].resolve() if candidates else None


def project_name_from_description(description_path):
    try:
        text = Path(description_path).read_text(encoding="utf-8")
    except OSError:
        text = ""
    for line in text.splitlines():
        if line.startswith("# "):
            slug = slugify(line[2:].strip())
            if slug:
                return slug
    stem = Path(description_path).stem
    if stem.endswith("_description"):
        stem = stem[: -len("_description")]
    return slugify(stem) or "app"


def resolve_output_path(output, description_path):
    if output:
        candidate = Path(output).expanduser()
        return candidate if candidate.is_absolute() else (settings.ROOT / candidate)
    return settings.PROJECTS_DIR / project_name_from_description(description_path)


_PROJECT_ROOT = settings.ROOT


def set_project_root(path):
    # Only records the path; the folder is created when a task actually runs.
    global _PROJECT_ROOT
    _PROJECT_ROOT = Path(path).expanduser().resolve()
    return _PROJECT_ROOT


def get_project_root():
    return _PROJECT_ROOT


def project_root_for(project):
    """Root folder of one domain project: <generated root>/services/<project>."""
    return get_project_root() / settings.PROJECTS_SUBDIR / project
