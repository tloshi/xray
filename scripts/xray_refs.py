"""Code-reference verification for a Feature X-Ray document.

A diagram is only worth trusting if every step can be traced to real code.
Each reference names a file, and ideally a line and the symbol expected
there. This module checks all three against the working tree, so a reference
that was guessed or has drifted fails the build instead of reaching a reader.

Accepted forms for a reference:
    "path/File.kt:57"
    "path/File.kt#recognizeDeliveryNote"         (line is looked up)
    "path/File.kt:57#recognizeDeliveryNote"
    {"path": "...", "line": 57, "symbol": "recognizeDeliveryNote"}
"""

from __future__ import annotations

import copy
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from xray_schema import Report

SYMBOL_WINDOW = 8
MAX_SUGGESTIONS = 5
HASH_LENGTH = 12
SKIP_DIRS = {".git", "build", "node_modules", ".gradle", ".idea", "out", "dist", "target", ".tokensave", ".kotlin"}
def _declaration_pattern(name: str) -> re.Pattern[str]:
    """Matches a line that declares `name` (Kotlin, Java, TypeScript, Python)."""
    n = re.escape(name)
    return re.compile(
        rf"\b(?:class|object|interface|typealias|record|def|function|enum)\s+(?:class\s+)?{n}\b"
        rf"|\bfun\s+(?:<[^>]*>\s*)?(?:[\w<>?,.\s]*\.)?{n}\s*[(<]"
        rf"|\b(?:val|var|const)\s+(?:val\s+)?(?:[\w<>?,]+\.)?{n}\b"
    )


IMPORT_LINE = re.compile(r"^\s*(?:import|package)\b")
TECH_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
REF_RE = re.compile(r"^(?P<path>[^#]*?)(?::(?P<line>\d+))?(?:#(?P<symbol>.+))?$")


@dataclass
class RefStats:
    total: int = 0
    with_symbol: int = 0
    fixed: int = 0
    failed: int = 0
    files: dict[str, str] = field(default_factory=dict)
    resolved: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedRef:
    path: str
    line: int | None
    symbol: str | None


class SourceTree:
    """Reads source files once and answers lookups against the repository."""

    def __init__(self, root: Path, source_root: str | None) -> None:
        self.root = root
        self.source_root = source_root
        self._lines: dict[str, list[str]] = {}
        self._by_name: dict[str, list[str]] | None = None

    def resolve(self, path: str) -> str | None:
        """Returns the repo-relative path for a reference, or None if absent."""
        candidates = [path]
        if self.source_root:
            candidates.append(str(Path(self.source_root) / path))
        for candidate in candidates:
            full = (self.root / candidate).resolve()
            if full.is_file() and self._inside_root(full):
                return full.relative_to(self.root.resolve()).as_posix()
        return None

    def _inside_root(self, full: Path) -> bool:
        try:
            full.relative_to(self.root.resolve())
            return True
        except ValueError:
            return False

    def contains(self, rel_path: str, text: str) -> bool:
        return any(text in line for line in self.lines(rel_path))

    def lines(self, rel_path: str) -> list[str]:
        if rel_path not in self._lines:
            text = (self.root / rel_path).read_text(encoding="utf-8", errors="replace")
            self._lines[rel_path] = text.splitlines()
        return self._lines[rel_path]

    def digest(self, rel_path: str) -> str:
        data = (self.root / rel_path).read_bytes()
        return hashlib.sha1(data).hexdigest()[:HASH_LENGTH]

    def suggest(self, path: str) -> list[str]:
        """Finds files with the same name, for a 'did you mean' hint."""
        if self._by_name is None:
            index: dict[str, list[str]] = {}
            for folder, dirs, files in os.walk(self.root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in files:
                    rel = (Path(folder) / name).relative_to(self.root).as_posix()
                    index.setdefault(name, []).append(rel)
            self._by_name = index
        return self._by_name.get(Path(path).name, [])[:MAX_SUGGESTIONS]


def parse_ref(raw: object) -> ParsedRef | None:
    """Normalises a string or dict reference; None when it is unusable."""
    if isinstance(raw, dict):
        path = raw.get("path")
        if not isinstance(path, str) or not path.strip():
            return None
        line = raw.get("line")
        symbol = raw.get("symbol")
        return ParsedRef(path.strip(), int(line) if isinstance(line, int) and line > 0 else None,
                         symbol.strip() if isinstance(symbol, str) and symbol.strip() else None)
    if isinstance(raw, str):
        match = REF_RE.match(raw.strip())
        if not match or not match.group("path"):
            return None
        line = match.group("line")
        symbol = match.group("symbol")
        return ParsedRef(match.group("path"), int(line) if line else None, symbol.strip() if symbol else None)
    return None


def _label(item: object, index: int) -> str:
    """Names a list entry by its id when it has one, so messages match the data."""
    if isinstance(item, dict) and isinstance(item.get("id"), str):
        return item["id"]
    return str(index)


def _occurrences(lines: list[str], symbol: str) -> list[int]:
    """1-based lines containing the symbol (substring match), declarations first.

    A bare '#name' should land on where the name is declared rather than on an
    import or an earlier call, so declaration lines are moved to the front.
    Falls back to the last dotted part of 'Class.method'.
    """
    needle = symbol
    hits = [i + 1 for i, text in enumerate(lines) if needle in text]
    if not hits and "." in symbol:
        needle = symbol.rsplit(".", 1)[1].rstrip("()")
        hits = [i + 1 for i, text in enumerate(lines) if needle and needle in text]
    declared = _declaration_pattern(needle.rstrip("()"))
    first = [h for h in hits if declared.search(lines[h - 1])]
    rest = [h for h in hits if h not in first]
    body = [h for h in rest if not IMPORT_LINE.match(lines[h - 1])]
    return first + body + [h for h in rest if h not in body]


def _declaration_count(lines: list[str], symbol: str, hits: list[int]) -> int:
    needle = symbol.rsplit(".", 1)[-1].rstrip("()") if "." in symbol and symbol not in "".join(lines) else symbol
    declared = _declaration_pattern(needle.rstrip("()"))
    return sum(1 for h in hits if declared.search(lines[h - 1]))


def _with_line(raw: object, line: int) -> object:
    """Returns the reference in its original form, pointing at a new line."""
    if isinstance(raw, dict):
        return {**raw, "line": line}
    parsed = parse_ref(raw)
    if parsed is None:
        return raw
    return f"{parsed.path}:{line}" + (f"#{parsed.symbol}" if parsed.symbol else "")


def _unchecked(raw: object) -> dict | None:
    """Normalises a reference without touching the source tree (--no-verify)."""
    parsed = parse_ref(raw)
    if parsed is None:
        return None
    result: dict = {"path": parsed.path, "name": Path(parsed.path).name, "line": parsed.line}
    if parsed.symbol:
        result["symbol"] = parsed.symbol
    return result


def _check_one(raw: object, where: str, tree: SourceTree, report: Report,
               stats: RefStats, fix: bool) -> tuple[object, dict | None]:
    """Verifies one reference. Returns (possibly corrected source form, normalised dict)."""
    stats.total += 1
    parsed = parse_ref(raw)
    if parsed is None:
        stats.failed += 1
        report.error(where, f"unreadable reference {raw!r}; use \"path:line#symbol\"")
        return raw, None

    rel = tree.resolve(parsed.path)
    if rel is None:
        stats.failed += 1
        hint = tree.suggest(parsed.path)
        report.error(where, f"file not found: {parsed.path}" + (f" (did you mean: {', '.join(hint)})" if hint else ""))
        return raw, None

    lines = tree.lines(rel)
    line = parsed.line
    corrected = raw
    if line is not None and line > len(lines):
        stats.failed += 1
        report.error(where, f"{rel}:{line} is past the end of the file ({len(lines)} lines)")
        return raw, None

    if parsed.symbol:
        hits = _occurrences(lines, parsed.symbol)
        if not hits:
            stats.failed += 1
            report.error(where, f"symbol {parsed.symbol!r} does not appear anywhere in {rel}; "
                                "check the name and the file (was this guessed?)")
            return raw, None
        near = [h for h in hits if line is not None and abs(h - line) <= SYMBOL_WINDOW]
        if line is None:
            line = hits[0]
            corrected = _with_line(raw, line)
            declared = _declaration_count(lines, parsed.symbol, hits)
            if declared > 1:
                shown = ", ".join(str(h) for h in hits[:declared])
                report.warn(where, f"{parsed.symbol!r} is declared {declared} times in {rel} (lines {shown}); "
                                   f"line {line} was used. Write \"{parsed.path}:<line>#{parsed.symbol}\" to pick another")
        elif not near:
            nearest = min(hits, key=lambda h: abs(h - line))
            if not fix:
                stats.failed += 1
                shown = ", ".join(str(h) for h in hits[:8])
                report.error(where, f"symbol {parsed.symbol!r} is not near {rel}:{line}; "
                                    f"it occurs at line(s) {shown}. Correct the line or rerun with --fix-refs")
                return raw, None
            stats.fixed += 1
            line = nearest
            corrected = _with_line(raw, line)
        stats.with_symbol += 1
    elif line is not None:
        report.warn(where, f"{rel}:{line} has no #symbol, so only the file and line range could be checked")

    stats.files.setdefault(rel, tree.digest(rel))
    shown = lines[line - 1].strip()[:90] if line else "(whole file)"
    stats.resolved.append(f"{where}  ->  {rel}{':' + str(line) if line else ''}   {shown}")
    normalised = {"path": rel, "name": Path(rel).name, "line": line}
    if parsed.symbol:
        normalised["symbol"] = parsed.symbol
    return corrected, normalised


def _check_tech(tech: str, refs: list[dict], where: str, tree: SourceTree, report: Report) -> None:
    """A 'tech' label names code; each identifier in it should occur in a cited file."""
    missing = [token for token in dict.fromkeys(TECH_TOKEN.findall(tech))
               if not any(tree.contains(ref["path"], token) for ref in refs)]
    if missing:
        report.warn(where, f"tech mentions {', '.join(repr(m) for m in missing)}, which does not appear in any file "
                           "this step cites; check the name or cite the file that declares it")


def verify(doc: dict, root: Path, report: Report, fix: bool = False, check: bool = True) -> tuple[dict, RefStats]:
    """Verifies every 'refs' list in the document.

    Returns a deep copy whose references are normalised dicts, plus statistics.
    With fix=True the source document is updated in place where a line could be
    snapped to the symbol it names; the caller decides whether to write it back.
    With check=False references are only normalised, never validated.
    """
    stats = RefStats()
    tree = SourceTree(root, (doc.get("meta") or {}).get("sourceRoot"))

    def walk(source: object, where: str) -> object:
        if isinstance(source, list):
            return [walk(item, f"{where}[{_label(item, i)}]") for i, item in enumerate(source)]
        if not isinstance(source, dict):
            return copy.deepcopy(source)
        out: dict = {}
        for key, value in source.items():
            here = f"{where}.{key}" if where else key
            if key == "refs" and isinstance(value, list):
                normalised_list = []
                for i, raw in enumerate(value):
                    if not check:
                        unchecked = _unchecked(raw)
                        if unchecked is not None:
                            stats.total += 1
                            normalised_list.append(unchecked)
                        continue
                    corrected, normalised = _check_one(raw, f"{here}[{i}]", tree, report, stats, fix)
                    if fix and corrected is not raw:
                        value[i] = corrected
                    if normalised is not None:
                        normalised_list.append(normalised)
                out[key] = normalised_list
            elif key == "_build":
                continue
            else:
                out[key] = walk(value, here)
        if check and isinstance(source.get("tech"), str) and out.get("refs"):
            _check_tech(source["tech"], out["refs"], where, tree, report)
        return out

    result = walk(doc, "")
    return result, stats


def current_digests(root: Path, paths: list[str]) -> dict[str, str | None]:
    """Hashes of files as they are now; None for a file that no longer exists."""
    digests: dict[str, str | None] = {}
    for rel in paths:
        full = root / rel
        digests[rel] = hashlib.sha1(full.read_bytes()).hexdigest()[:HASH_LENGTH] if full.is_file() else None
    return digests
