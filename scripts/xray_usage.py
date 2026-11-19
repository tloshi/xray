"""Token accounting for an X-ray run.

An agent cannot see what it spends, but the tool it runs in writes every model
call, with its token counts, to a transcript on disk. `usage start` prints a
unique marker, which therefore lands in that transcript; `usage stop` finds
the transcript by the marker and adds up everything after it. The result is
saved as a run record next to the page, so runs can be compared over time.

Transcripts are read as Claude Code writes them. OpenCode's storage is read on
a best-effort basis and has not been verified against a real installation.
"""

from __future__ import annotations

import datetime
import glob
import hashlib
import json
import os
import secrets
import tempfile
import time
from collections import Counter
from pathlib import Path

RUN_SCHEMA = 1
MARKER_PREFIX = "XRAY-RUN-"
TOKEN_KEYS = {"output": "output_tokens", "input": "input_tokens",
              "cacheWrite": "cache_creation_input_tokens", "cacheRead": "cache_read_input_tokens"}
TRANSCRIPT_GLOBS = [
    "~/.claude/projects/*/*.jsonl",
    "~/.claude/projects/*/*/subagents/*.jsonl",
    "/private/tmp/claude-*/*/*/tasks/*.output",
    "/tmp/claude-*/*/*/tasks/*.output",
]
OPENCODE_GLOB = "~/.local/share/opencode/storage/message/*/*.json"
LOOKBACK_SECONDS = 5


def _state_file() -> Path:
    key = hashlib.sha1(str(Path.cwd()).encode()).hexdigest()[:12]
    folder = Path(tempfile.gettempdir()) / "xray-usage"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key}.json"


def start() -> str:
    """Begins a measured run and returns the marker to print."""
    marker = MARKER_PREFIX + secrets.token_hex(4)
    _state_file().write_text(json.dumps({"marker": marker, "started": time.time()}), encoding="utf-8")
    return marker


def _read_state() -> dict | None:
    try:
        return json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _find_transcript(marker: str, since: float, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    needle = marker.encode()
    candidates: list[Path] = []
    for pattern in TRANSCRIPT_GLOBS:
        candidates.extend(Path(p) for p in glob.glob(os.path.expanduser(pattern)))
    recent = [p for p in candidates if p.is_file() and p.stat().st_mtime >= since - LOOKBACK_SECONDS]
    for path in sorted(recent, key=lambda p: -p.stat().st_mtime):
        try:
            if needle in path.read_bytes():
                return path
        except OSError:
            continue
    return None


def _text_len(content: object) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_text_len(c.get("text") or c.get("content") or "") if isinstance(c, dict) else len(str(c))
                   for c in content)
    return 0


def _tool_bucket(name: str, args: dict) -> str:
    path = str(args.get("file_path") or args.get("path") or "")
    if name == "Read":
        if "/feature-xray/" in path:
            return "read skill files"
        return "read source code" if path else "read"
    if name in {"Write", "Edit"}:
        return "write x-ray data"
    if name in {"Bash", "bash", "Grep", "Glob", "grep", "glob"}:
        return "search and shell"
    return name


def _claude_usage(path: Path, marker: str) -> dict:
    """Sums token usage and tool traffic recorded after the marker."""
    tokens: Counter = Counter()
    tools: dict[str, Counter] = {}
    calls: dict[str, tuple[str, dict]] = {}
    models: set[str] = set()
    files: set[str] = set()
    seen_ids: set[str] = set()
    counting = False
    api_calls = 0
    for line in path.open(encoding="utf-8", errors="replace"):
        if not counting:
            counting = marker in line
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message") or {}
        content = message.get("content")
        if entry.get("type") == "assistant":
            usage = message.get("usage") or {}
            ident = message.get("id") or entry.get("uuid")
            if usage and ident not in seen_ids:
                seen_ids.add(ident)
                api_calls += 1
                for name, key in TOKEN_KEYS.items():
                    tokens[name] += int(usage.get(key) or 0)
                if message.get("model"):
                    models.add(message["model"])
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    args = block.get("input") or {}
                    bucket = _tool_bucket(block.get("name", "?"), args)
                    calls[block.get("id")] = (bucket, args)
                    row = tools.setdefault(bucket, Counter())
                    row["calls"] += 1
                    row["charsOut"] += len(json.dumps(args, ensure_ascii=False))
        elif entry.get("type") == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    bucket, args = calls.get(block.get("tool_use_id"), ("?", {}))
                    tools.setdefault(bucket, Counter())["charsIn"] += _text_len(block.get("content"))
                    if bucket == "read source code":
                        files.add(str(args.get("file_path", "")))
    return {"harness": "claude-code", "tokens": dict(tokens), "apiCalls": api_calls, "models": sorted(models),
            "tools": {k: dict(v) for k, v in tools.items()}, "sourceFilesRead": len(files)}


def _opencode_usage(since: float) -> dict | None:
    """Best effort: sums the token fields of OpenCode message files written since the start."""
    tokens: Counter = Counter()
    models: set[str] = set()
    api_calls = 0
    for name in glob.glob(os.path.expanduser(OPENCODE_GLOB)):
        path = Path(name)
        try:
            if path.stat().st_mtime < since:
                continue
            message = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        spent = message.get("tokens")
        if not isinstance(spent, dict):
            continue
        api_calls += 1
        cache = spent.get("cache") or {}
        tokens["output"] += int(spent.get("output") or 0) + int(spent.get("reasoning") or 0)
        tokens["input"] += int(spent.get("input") or 0)
        tokens["cacheWrite"] += int(cache.get("write") or 0)
        tokens["cacheRead"] += int(cache.get("read") or 0)
        if message.get("modelID"):
            models.add(str(message["modelID"]))
    if not api_calls:
        return None
    return {"harness": "opencode (unverified reader)", "tokens": dict(tokens), "apiCalls": api_calls,
            "models": sorted(models), "tools": {}, "sourceFilesRead": None}


def _structure(doc: dict, data_bytes: int) -> dict:
    refs = files = 0
    cited: set[str] = set()

    def walk(value: object) -> None:
        nonlocal refs
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for ref in value.get("refs") or []:
                refs += 1
                cited.add(str(ref if isinstance(ref, str) else ref.get("path")).split("#")[0].split(":")[0])
            for key, item in value.items():
                if key not in {"refs", "_build"}:
                    walk(item)

    walk(doc)
    files = len(cited)
    diagrams = [{"id": d.get("id"), "kind": d.get("kind"),
                 "items": len(d.get("nodes") or d.get("components") or d.get("states") or d.get("participants") or [])}
                for d in doc.get("diagrams") or []]
    return {"diagrams": diagrams, "references": refs, "filesCited": files,
            "troubleshooting": len(doc.get("troubleshooting") or []), "findings": len(doc.get("findings") or []),
            "switches": len(doc.get("switches") or []), "openQuestions": len(doc.get("openQuestions") or []),
            "dataKB": round(data_bytes / 1024, 1)}


def _cost(tokens: dict) -> dict | None:
    """Optional: XRAY_PRICES="in=3,out=15,cache_read=0.3,cache_write=3.75" (per million tokens)."""
    spec = os.environ.get("XRAY_PRICES")
    if not spec or not tokens:
        return None
    try:
        price = {k.strip(): float(v) for k, v in (pair.split("=") for pair in spec.split(","))}
    except ValueError:
        return None
    total = (tokens.get("input", 0) * price.get("in", 0) + tokens.get("output", 0) * price.get("out", 0)
             + tokens.get("cacheRead", 0) * price.get("cache_read", 0)
             + tokens.get("cacheWrite", 0) * price.get("cache_write", 0)) / 1_000_000
    return {"amount": round(total, 4), "pricesPerMillion": price}


def stop(data_path: Path, doc: dict, commit: str, skill_version: str, transcript: str | None) -> tuple[dict, Path]:
    """Closes the measured run, writes its record and returns (record, path)."""
    state = _read_state() or {}
    started = float(state.get("started") or time.time())
    marker = state.get("marker") or ""
    measured: dict | None = None
    note = "Excludes the final step that reports the result."
    source = _find_transcript(marker, started, transcript) if marker or transcript else None
    if source and source.is_file():
        measured = _claude_usage(source, marker)
    else:
        measured = _opencode_usage(started)
    if measured is None:
        measured = {"harness": "unknown", "tokens": None, "apiCalls": None, "models": [], "tools": {},
                    "sourceFilesRead": None}
        note = ("Token usage could not be read: no transcript containing this run's marker was found. "
                "Run `usage start` first, or pass --transcript.")
    tokens = measured["tokens"]
    if tokens:
        tokens["total"] = sum(tokens.get(k, 0) for k in TOKEN_KEYS)
    meta = doc.get("meta") or {}
    now = time.time()
    record = {
        "xrayRun": RUN_SCHEMA,
        "name": data_path.name.replace(".xray.json", ""),
        "title": meta.get("title"), "module": meta.get("module"), "kind": doc.get("kind"),
        "depth": meta.get("depth", "standard"),
        "startedAt": datetime.datetime.fromtimestamp(started).isoformat(timespec="seconds"),
        "finishedAt": datetime.datetime.fromtimestamp(now).isoformat(timespec="seconds"),
        "durationSeconds": round(now - started),
        "commit": commit, "skillVersion": skill_version,
        **{k: measured[k] for k in ("harness", "models", "tokens", "apiCalls", "tools", "sourceFilesRead")},
        "xray": _structure(doc, data_path.stat().st_size),
        "cost": _cost(tokens or {}),
        "note": note,
    }
    folder = data_path.parent / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.fromtimestamp(now).strftime("%Y%m%d-%H%M%S")
    path = folder / f"{stamp}-{record['name']}.run.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record, path


def latest_for(data_path: Path) -> dict | None:
    """The newest run record of this X-ray, if any (embedded in the page on build)."""
    name = data_path.name.replace(".xray.json", "")
    found = sorted((data_path.parent / "runs").glob(f"*-{name}.run.json"))
    if not found:
        return None
    try:
        return json.loads(found[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_runs(folder: Path) -> list[dict]:
    runs = []
    for path in sorted(folder.rglob("*.run.json")):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return runs


def human(n: object) -> str:
    if not isinstance(n, (int, float)):
        return "–"
    for limit, unit in ((1_000_000, "M"), (1_000, "k")):
        if abs(n) >= limit:
            return f"{n / limit:.1f}{unit}"
    return str(int(n))


def summary_line(record: dict) -> str:
    tokens = record.get("tokens")
    if not tokens:
        return "tokens: not measured (" + record.get("note", "") + ")"
    cost = record.get("cost")
    return (f"tokens: {human(tokens.get('output'))} output · {human(tokens.get('cacheRead'))} cached input · "
            f"{human(tokens.get('cacheWrite'))} cache write · {human(tokens.get('input'))} fresh input · "
            f"{record.get('apiCalls')} model calls · {record.get('durationSeconds')}s"
            + (f" · cost {cost['amount']}" if cost else ""))
