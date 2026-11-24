"""Where an X-ray lives on disk.

The output folder mirrors the project, and every X-ray has a folder of its own:

    <out>/<module path>/<name>/<name>.xray.json   the data
    <out>/<module path>/<name>/<name>.html        the page
    <out>/<module path>/<name>/runs/              one record per run
    <out>/index.html                              a map of every page

So a page is found where its code is found, whatever the project is — an
Android module, a web app or library, a backend service — and nothing of one
X-ray is mixed with another.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from xray_schema import Report

DEFAULT_OUT = "xrayDocs"
DATA_SUFFIX = ".xray.json"
DATA_RE = re.compile(r'<script id="xray-data" type="application/json">(.*?)</script>', re.S)
# A folder holding one of these is a module, package, app or service of its own.
BUILD_FILES = ("build.gradle", "build.gradle.kts", "package.json", "project.json", "pom.xml", "go.mod",
               "Cargo.toml", "pubspec.yaml", "Package.swift", "pyproject.toml", "composer.json", "Gemfile")
BUILD_SUFFIXES = (".csproj", ".fsproj", ".vbproj")


def stem(data_path: Path) -> str:
    name = data_path.name
    return name[: -len(DATA_SUFFIX)] if name.endswith(DATA_SUFFIX) else data_path.stem


def module_parts(doc: dict) -> list[str]:
    """`meta.modulePath` as path segments, or [] when it is absent."""
    raw = str((doc.get("meta") or {}).get("modulePath") or "").replace("\\", "/")
    return [part for part in raw.split("/") if part and part != "."]


def out_root(data_path: Path, doc: dict) -> Path | None:
    """The output folder, when the data file sits where the layout puts it; otherwise None."""
    tail = [*module_parts(doc), stem(data_path)]
    folder = data_path.parent
    if len(tail) < 2 or len(folder.parts) <= len(tail) or list(folder.parts[-len(tail):]) != tail:
        return None
    return folder.parents[len(tail) - 1]


def index_href(doc: dict) -> str:
    """Relative link from a page to the index of its output folder."""
    return "../" * (len(module_parts(doc)) + 1) + "index.html"


def read_page(page_path: Path) -> dict | None:
    """The document embedded in an X-ray page, or None when the file is not one."""
    try:
        match = DATA_RE.search(page_path.read_text(encoding="utf-8", errors="replace"))
        return json.loads(match.group(1).replace("<\\/", "</")) if match else None
    except (OSError, json.JSONDecodeError):
        return None


def _is_module(folder: Path) -> bool:
    try:
        return any(entry.name in BUILD_FILES or entry.name.endswith(BUILD_SUFFIXES) for entry in folder.iterdir())
    except OSError:
        return False


def _module_of(root: Path, rel_file: str, cache: dict[Path, str | None]) -> str | None:
    """The nearest folder above a file that holds a build file; None when only the repository root does."""
    folder = (root / rel_file).parent
    walked = []
    found: str | None = None
    while folder != root and root in folder.parents:
        if folder in cache:
            found = cache[folder]
            break
        walked.append(folder)
        if _is_module(folder):
            found = folder.relative_to(root).as_posix()
            break
        folder = folder.parent
    for seen in walked:
        cache[seen] = found
    return found


def _main_module(root: Path, files: list[str]) -> str | None:
    """The module most of the cited files belong to, if one holds a majority."""
    cache: dict[Path, str | None] = {}
    counts = Counter(m for m in (_module_of(root, f, cache) for f in files) if m)
    if not counts:
        return None
    module, cited = counts.most_common(1)[0]
    return module if cited * 2 > len(files) else None


def _suggested(data_path: Path, parts: list[str], root: Path) -> str:
    named = next((p for p in data_path.parents if p.name == DEFAULT_OUT), None)
    out = named or (data_path.parent if data_path.parent != root else root / DEFAULT_OUT)
    name = stem(data_path)
    wanted = out.joinpath(*parts, name, name + DATA_SUFFIX)
    try:
        return wanted.relative_to(root).as_posix()
    except ValueError:
        return str(wanted)


def check(doc: dict, data_path: Path, root: Path, files: list[str], report: Report) -> None:
    """Checks that `meta.modulePath` is a real module folder and the data file is filed under it."""
    parts = module_parts(doc)
    if not parts:
        return  # the schema check already asked for it
    declared = "/".join(parts)
    if ".." in parts or not (root / declared).is_dir():
        report.error("meta.modulePath", f"no such folder in the repository: {declared}")
        return
    main = _main_module(root, files)
    if main and declared.startswith(main + "/"):
        report.warn("meta.modulePath", f"{declared} is a folder inside the module {main}; "
                                       f"use the module's own folder so the page is filed with it")
        parts = main.split("/")
    elif main and main.startswith(declared + "/"):
        report.warn("meta.modulePath", f"most cited files belong to {main}; name that folder, not its parent")
        parts = main.split("/")
    elif main and files and not any(f.startswith(declared + "/") for f in files):
        report.warn("meta.modulePath", f"no cited file is under {declared}; most belong to {main}")
        return  # which of the two is meant is the author's call; the place follows from it
    if parts != module_parts(doc) or out_root(data_path, doc) is None:
        report.warn("location", f"file this X-ray at {_suggested(data_path, parts, root)} — "
                                f"the module's path, then a folder of its own")
