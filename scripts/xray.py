#!/usr/bin/env python3
"""X-Ray command line: build, check and render-check an X-ray page.

    xray.py build <data.xray.json> [-o page.html] [--fix-refs] [--no-verify]
    xray.py check <page.html | folder>   # has the cited code changed since, and which steps?
    xray.py index [folder]               # rewrite the map of every page in the output folder
    xray.py outline <data.xray.json>     # compact text view: cheap to read, good for diffs
    xray.py render-check <page.html>     # does every diagram render? (needs Chrome)
    xray.py usage start                  # begin measuring the tokens this run spends
    xray.py usage stop <data.xray.json>  # save the run record and show what was spent
    xray.py runs [folder] [--html FILE]  # compare saved runs, as a table or an overview page
    xray.py update [--check]             # is there a newer version of the skill? get it

Standard library only, so it runs anywhere Python 3.9+ is installed.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))

import xray_refs  # noqa: E402
import xray_schema  # noqa: E402
import xray_layout  # noqa: E402
import xray_index  # noqa: E402
import xray_report  # noqa: E402
import xray_update  # noqa: E402
import xray_usage  # noqa: E402

SKILL_VERSION = "1.4"

ASSETS = Path(__file__).resolve().parent.parent / "assets"
JS_FILES = ["viewer-i18n.js", "viewer-core.js", "viewer-diagrams.js", "viewer-panzoom.js",
            "viewer-sections.js", "viewer-options.js", "viewer-app.js"]
MERMAID_CDN = "https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.4.0/mermaid.min.js"
VENDORED_MERMAID = ASSETS / "vendor" / "mermaid.min.js"
BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge", "chrome",
]
RENDER_TIMEOUT_SECONDS = 90
EXIT_OK, EXIT_INVALID, EXIT_STALE = 0, 1, 2


def say(text: str = "") -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def fail(text: str) -> None:
    """Errors go to stdout too, so they stay in order with the rest of the report."""
    say(text)


def git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def find_root(explicit: str | None, near: Path) -> Path:
    """The repository root that code references are relative to."""
    if explicit:
        return Path(explicit).resolve()
    top = git(near if near.is_dir() else near.parent, "rev-parse", "--show-toplevel")
    return Path(top) if top else Path.cwd()


def load_document(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise SystemExit(f"{path}: not valid JSON at line {err.lineno}, column {err.colno}: {err.msg}") from err
    except OSError as err:
        raise SystemExit(f"cannot read {path}: {err}") from err


def print_report(report: xray_schema.Report) -> None:
    for message in report.errors:
        fail(f"  ERROR    {message}")
    for message in report.warnings:
        say(f"  warning  {message}")


def verify_tests(doc: dict, tree: xray_refs.SourceTree, report: xray_schema.Report, files: dict[str, str]) -> None:
    """Test files are evidence too: each listed path must exist."""
    for i, item in enumerate(doc.get("tests") or []):
        rel = tree.resolve(str(item.get("path", "")))
        if rel is None:
            hint = tree.suggest(str(item.get("path", "")))
            report.error(f"tests[{i}]", f"file not found: {item.get('path')}" + (f" (did you mean: {', '.join(hint)})" if hint else ""))
        else:
            item["path"] = rel
            files.setdefault(rel, tree.digest(rel))


def mermaid_tag(inline: str | None) -> str:
    source = Path(inline) if inline else (VENDORED_MERMAID if VENDORED_MERMAID.is_file() else None)
    if source is None:
        return f'<script src="{MERMAID_CDN}"></script>'
    code = source.read_text(encoding="utf-8").replace("</script", "<\\/script")
    return f"<script>\n{code}\n</script>"


def render_page(document: dict, inline_mermaid: str | None, fragment: bool) -> str:
    template = (ASSETS / "viewer.html").read_text(encoding="utf-8")
    css = (ASSETS / "viewer.css").read_text(encoding="utf-8")
    scripts = "\n".join((ASSETS / name).read_text(encoding="utf-8") for name in JS_FILES)
    meta = document.get("meta") or {}
    title = str(meta.get("title", "X-Ray")).replace("<", "&lt;").replace(">", "&gt;")
    payload = json.dumps(document, ensure_ascii=False).replace("</", "<\\/")
    page = template
    for placeholder, value in (
        ("__XRAY_LANG__", re.sub(r"[^a-zA-Z-]", "", str(meta.get("lang", "en"))) or "en"),
        ("__XRAY_TITLE__", title),
        ("__XRAY_CSS__", css),
        ("__XRAY_MERMAID__", mermaid_tag(inline_mermaid)),
        ("__XRAY_JS__", scripts.replace("</script", "<\\/script")),
        ("__XRAY_DATA__", payload),
    ):
        page = page.replace(placeholder, value, 1)
    if fragment:
        page = re.sub(r"<!DOCTYPE html>\s*|</?html[^>]*>\s*|</?head>\s*|</?body[^>]*>\s*|<meta [^>]*>\s*", "", page)
    return page


def cmd_build(args: argparse.Namespace) -> int:
    data_path = Path(args.data).resolve()
    doc = load_document(data_path)
    root = find_root(args.root, data_path)
    report = xray_schema.Report()
    # Size is measured on compact JSON, so indentation does not count against the budget.
    xray_schema.validate(doc, report, len(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))

    document, stats = xray_refs.verify(doc, root, report, fix=args.fix_refs, check=not args.no_verify)
    tree = xray_refs.SourceTree(root, (doc.get("meta") or {}).get("sourceRoot"))
    if not args.no_verify:
        verify_tests(document, tree, report, stats.files)
    xray_layout.check(doc, data_path, root, sorted(stats.files), report)

    quiet = getattr(args, "quiet", False)
    if not quiet:
        say(f"X-ray: {data_path.name}   repo root: {root}")
        print_report(report)
    if report.errors:
        fail(f"\nBuild stopped: {len(report.errors)} error(s). Nothing was written.")
        return EXIT_INVALID

    if args.verbose:
        say("\nResolved references:")
        for line in stats.resolved:
            say(f"  {line}")

    if args.fix_refs and stats.fixed:
        data_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        say(f"  fixed    {stats.fixed} reference line(s) snapped to their symbol in {data_path.name}")

    document["_build"] = {
        "verified": not args.no_verify,
        "refsTotal": stats.total,
        "refsVerified": stats.total - stats.failed,
        "refsWithSymbol": stats.with_symbol,
        "commit": git(root, "rev-parse", "--short", "HEAD"),
        "generatedAt": datetime.date.today().isoformat(),
        "skillVersion": SKILL_VERSION,
        "files": stats.files,
        "warnings": len(report.warnings),
    }
    last_run = xray_usage.latest_for(data_path)
    if last_run and last_run.get("tokens"):
        document["_build"]["usage"] = {k: last_run.get(k) for k in ("tokens", "apiCalls", "models", "durationSeconds")}
    out_path = Path(args.output).resolve() if args.output else data_path.with_name(
        data_path.name.replace(".xray.json", "").replace(".json", "") + ".html")
    # Filed where the layout puts it, the page links back to the map of its output folder.
    out = None if args.output else xray_layout.out_root(data_path, doc)
    if out and not xray_index.writable(out):
        out = None
    if out:
        document["_build"]["index"] = xray_layout.index_href(doc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_page(document, args.inline_mermaid, args.fragment), encoding="utf-8")
    index = xray_index.render(out) if out else None

    verified = "not verified (--no-verify)" if args.no_verify else (
        f"{stats.total} verified, {stats.with_symbol} with a symbol check")
    if not quiet:
        say(f"\nBuilt {out_path}")
        say(f"  references: {verified}   files tracked: {len(stats.files)}   warnings: {len(report.warnings)}")
        if index:
            say(f"  index: {index[0]} ({index[1]} page{'' if index[1] == 1 else 's'})")
    return EXIT_OK


def check_page(page_path: Path, document: dict, root: Path, label: str, brief: bool) -> int:
    """Reports one page; with `brief`, a fresh page takes a single line."""
    build = document.get("_build") or {}
    recorded = build.get("files") or {}
    now = xray_refs.current_digests(root, sorted(recorded))
    changed = [p for p in sorted(recorded) if now[p] is not None and now[p] != recorded[p]]
    missing = [p for p in sorted(recorded) if now[p] is None]
    if brief and not (changed or missing):
        say(f"  fresh  {label}")
        return EXIT_OK
    say(f"{label}: generated {build.get('generatedAt', '?')} at commit {build.get('commit', '?')}, "
        f"{len(recorded)} source files tracked")
    for path in changed:
        say(f"  changed  {path}")
    for path in missing:
        say(f"  missing  {path}")
    if changed or missing:
        say("\nSteps that cite a changed file (re-read only these, then edit the data and rebuild):")
        for where, path in citing(document, set(changed) | set(missing)):
            say(f"  {where:<58} {Path(path).name}")
        say(f"\nSTALE: {len(changed)} changed, {len(missing)} missing.")
        return EXIT_STALE
    say("\nFresh: none of the cited source files has changed.")
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    target = Path(args.page).resolve()
    root = find_root(args.root, target)
    if not target.is_dir():
        document = xray_layout.read_page(target)
        if document is None:
            fail(f"{target}: not an X-ray page (no embedded data)")
            return EXIT_INVALID
        return check_page(target, document, root, target.name, brief=False)
    pages = stale = 0
    for page in sorted(target.rglob("*.html")):
        document = xray_layout.read_page(page)
        if document is None:
            continue
        pages += 1
        if check_page(page, document, root, page.relative_to(target).as_posix(), brief=True) == EXIT_STALE:
            stale += 1
            say()
    if not pages:
        say(f"No X-ray pages under {target}.")
        return EXIT_OK
    say(f"\n{pages} page(s) checked: {pages - stale} fresh, {stale} stale.")
    return EXIT_STALE if stale else EXIT_OK


def cmd_index(args: argparse.Namespace) -> int:
    folder = Path(args.folder or (xray_layout.DEFAULT_OUT if Path(xray_layout.DEFAULT_OUT).is_dir() else ".")).resolve()
    if not folder.is_dir():
        fail(f"{folder}: no such folder")
        return EXIT_INVALID
    written = xray_index.render(folder)
    if written is None:
        fail(f"{folder / xray_index.INDEX_NAME} exists and was not written by X-Ray; it was left untouched.")
        return EXIT_INVALID
    say(f"Wrote {written[0]} ({written[1]} page{'' if written[1] == 1 else 's'})")
    return EXIT_OK


def citing(document: dict, paths: set[str]) -> list[tuple[str, str]]:
    """Where in the document each of the given files is cited."""
    found: list[tuple[str, str]] = []

    def walk(value: object, where: str) -> None:
        if isinstance(value, list):
            for i, item in enumerate(value):
                label = item["id"] if isinstance(item, dict) and isinstance(item.get("id"), str) else str(i)
                walk(item, f"{where}[{label}]")
        elif isinstance(value, dict):
            for ref in value.get("refs") or []:
                if isinstance(ref, dict) and ref.get("path") in paths and (where, ref["path"]) not in found:
                    found.append((where, ref["path"]))
            for key, item in value.items():
                if key not in {"refs", "_build"}:
                    walk(item, f"{where}.{key}" if where else key)

    walk(document, "")
    return found


def _short(text: object, width: int) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def _first_ref(item: dict) -> str:
    refs = item.get("refs") or []
    if not refs:
        return ""
    ref = refs[0]
    return ref if isinstance(ref, str) else f"{ref.get('path')}#{ref.get('symbol', '')}"


def cmd_outline(args: argparse.Namespace) -> int:
    """Prints an X-ray as a few dozen lines: far cheaper to read than the JSON."""
    doc = load_document(Path(args.data).resolve())
    meta = doc.get("meta") or {}
    say(f"{meta.get('title')}  [{doc.get('kind')}, {meta.get('depth', 'quick')}]  module: {meta.get('module')}")
    say(_short(meta.get("summary"), 300))
    for d in doc.get("diagrams") or []:
        items = d.get("nodes") or d.get("components") or d.get("states") or []
        say(f"\n== {d.get('kind')} {d.get('id')!r}: {d.get('title')} ({len(items) or len(d.get('participants') or [])} items)")
        for n in items:
            say(f"  {n.get('id', ''):<22} {n.get('type') or n.get('layer') or '':<9} {_short(n.get('label'), 52):<52} "
                f"| {_short(n.get('tech'), 46)} | {_short(_first_ref(n), 70)}")
        if d.get("kind") == "sequence":
            say("  participants: " + ", ".join(f"{p.get('id')}={p.get('tech') or p.get('label')}" for p in d.get("participants") or []))
    for key, title in (("troubleshooting", "symptom"), ("findings", "title")):
        rows = doc.get(key) or []
        if rows:
            say(f"\n== {key} ({len(rows)})")
            for r in rows:
                say(f"  [{r.get('severity', 'medium'):<6}] {_short(r.get(title), 84)}  -> {', '.join(r.get('nodes') or [])}")
    if doc.get("switches"):
        say(f"\n== switches ({len(doc['switches'])})")
        for s in doc["switches"]:
            say(f"  {s.get('key'):<34} {_short(s.get('effect'), 90)}")
    for key in ("caveats", "openQuestions"):
        if doc.get(key):
            say(f"\n== {key} ({len(doc[key])})")
            for c in doc[key]:
                say(f"  - {_short(c.get('text') if isinstance(c, dict) else c, 130)}")
    return EXIT_OK


def cmd_usage(args: argparse.Namespace) -> int:
    if args.action == "start":
        say(xray_usage.start())
        say("Measuring from here. Finish with: xray.py usage stop <data.xray.json>")
        return EXIT_OK
    if not args.data:
        fail("usage stop needs the path of the .xray.json that was produced")
        return EXIT_INVALID
    data_path = Path(args.data).resolve()
    doc = load_document(data_path)
    root = find_root(args.root, data_path)
    record, path = xray_usage.stop(data_path, doc, git(root, "rev-parse", "--short", "HEAD"), SKILL_VERSION, args.transcript)
    say(f"Run record: {path}")
    say("  " + xray_usage.summary_line(record))
    if record.get("tokens"):
        # Rebuild quietly so the page itself shows what it cost to produce.
        cmd_build(argparse.Namespace(data=str(data_path), output=None, root=args.root, fix_refs=False, no_verify=False,
                                     inline_mermaid=None, fragment=False, verbose=False, quiet=True))
    return EXIT_OK


def cmd_runs(args: argparse.Namespace) -> int:
    if args.html:
        count = xray_report.render(Path(args.folder).resolve(), Path(args.html).resolve())
        say(f"Wrote {Path(args.html).resolve()} ({count} runs)")
        return EXIT_OK
    runs = xray_usage.load_runs(Path(args.folder).resolve())
    if args.json:
        say(json.dumps(runs, indent=2, ensure_ascii=False))
        return EXIT_OK
    if not runs:
        say("No run records found. They are written by `xray.py usage stop`.")
        return EXIT_OK
    h = xray_usage.human
    say(f"{'finished':<17}{'x-ray':<44}{'depth':<10}{'output':>8}{'cached in':>11}{'cache wr':>10}{'calls':>7}{'min':>6}{'KB':>6}{'refs':>6}  model")
    for r in runs:
        t = r.get("tokens") or {}
        x = r.get("xray") or {}
        label = "/".join(str(part) for part in (r.get("modulePath"), r.get("name")) if part)
        label = label if len(label) <= 42 else "…" + label[-41:]
        say(f"{str(r.get('finishedAt', ''))[:16]:<17}{label:<44}{str(r.get('depth', ''))[:9]:<10}"
            f"{h(t.get('output')):>8}{h(t.get('cacheRead')):>11}{h(t.get('cacheWrite')):>10}{str(r.get('apiCalls') or '–'):>7}"
            f"{round((r.get('durationSeconds') or 0) / 60):>6}{str(x.get('dataKB', '–')):>6}{str(x.get('references', '–')):>6}"
            f"  {', '.join(r.get('models') or [])}")
    return EXIT_OK


def cmd_update(args: argparse.Namespace) -> int:
    return xray_update.run(SKILL_VERSION, args.check, say)


def find_browser() -> str | None:
    for candidate in BROWSERS:
        if Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def cmd_render_check(args: argparse.Namespace) -> int:
    page_path = Path(args.page).resolve()
    browser = args.browser or find_browser()
    if not browser:
        say("render-check skipped: no Chrome/Edge/Chromium found (pass --browser PATH to enable).")
        return EXIT_OK
    with tempfile.TemporaryDirectory() as profile:
        base = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                f"--user-data-dir={profile}", "--window-size=1600,1200", "--virtual-time-budget=25000"]
        fragment = f"d={args.diagram}&full=1" if args.diagram else args.hash
        url = page_path.as_uri() + (f"#{fragment}" if fragment else "")
        try:
            dom = subprocess.run([*base, "--dump-dom", url], capture_output=True, text=True,
                                 timeout=RENDER_TIMEOUT_SECONDS, check=False).stdout
            if args.screenshot:
                subprocess.run([*base, f"--screenshot={Path(args.screenshot).resolve()}", url],
                               capture_output=True, text=True, timeout=RENDER_TIMEOUT_SECONDS, check=False)
        except (OSError, subprocess.TimeoutExpired) as err:
            fail(f"render-check could not run the browser: {err}")
            return EXIT_INVALID

    def attr(name: str) -> str:
        found = re.search(rf'data-{name}="([^"]*)"', dom)
        return found.group(1) if found else ""

    status = attr("xray-status")
    if status == "ok":
        say(f"render-check OK: every diagram rendered ({attr('xray-bound')} nodes clickable).")
        return EXIT_OK
    fail(f"render-check FAILED: status={status or 'page did not finish loading'}")
    if attr("xray-errors"):
        fail("  " + attr("xray-errors").replace("&quot;", '"').replace("&amp;", "&"))
    return EXIT_INVALID


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xray.py", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"xray {SKILL_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="validate the data, verify code references and write the page")
    build.add_argument("data", help="path to the .xray.json data file")
    build.add_argument("-o", "--output", help="output .html path (default: next to the data file)")
    build.add_argument("--root", help="repository root (default: git toplevel)")
    build.add_argument("--fix-refs", action="store_true", help="snap wrong line numbers to the symbol they name")
    build.add_argument("--no-verify", action="store_true", help="skip reference verification (page is marked unverified)")
    build.add_argument("--inline-mermaid", metavar="FILE", help="embed this mermaid.min.js so the page works offline")
    build.add_argument("--verbose", action="store_true", help="list every reference with the line it resolved to")
    build.add_argument("--fragment", action="store_true", help="omit html/head/body wrappers (for hosts that add their own)")
    build.set_defaults(run=cmd_build)

    check = sub.add_parser("check", help="report whether cited source files changed since the page was built")
    check.add_argument("page", help="one page, or a folder to check every page under it")
    check.add_argument("--root")
    check.set_defaults(run=cmd_check)

    index = sub.add_parser("index", help="rewrite index.html, the map of every page in the output folder")
    index.add_argument("folder", nargs="?", help="the output folder (default: xrayDocs, else the current folder)")
    index.set_defaults(run=cmd_index)

    usage = sub.add_parser("usage", help="measure the tokens an X-ray run spends and save a run record")
    usage.add_argument("action", choices=["start", "stop"])
    usage.add_argument("data", nargs="?", help="for stop: the .xray.json that was produced")
    usage.add_argument("--transcript", help="session transcript to read, if it cannot be found automatically")
    usage.add_argument("--root")
    usage.set_defaults(run=cmd_usage)

    runs = sub.add_parser("runs", help="list saved run records to compare token spend over time")
    runs.add_argument("folder", nargs="?", default=".")
    runs.add_argument("--json", action="store_true", help="print the full records as JSON")
    runs.add_argument("--html", metavar="FILE", help="write an overview page of all runs, with links to the X-rays")
    runs.set_defaults(run=cmd_runs)

    update = sub.add_parser("update", help="update the skill from the repository it was cloned from")
    update.add_argument("--check", action="store_true", help="only report whether a newer version exists")
    update.set_defaults(run=cmd_update)

    outline = sub.add_parser("outline", help="print a compact text view of an X-ray data file")
    outline.add_argument("data")
    outline.set_defaults(run=cmd_outline)

    render = sub.add_parser("render-check", help="open the page in headless Chrome and confirm diagrams render")
    render.add_argument("page")
    render.add_argument("--browser", help="path to a Chromium-based browser")
    render.add_argument("--screenshot", metavar="PNG", help="also save a screenshot")
    render.add_argument("--diagram", metavar="ID", help="show only this diagram, filling the window (for --screenshot)")
    render.add_argument("--hash", help="URL fragment to open, e.g. d=flow&n=n_scan")
    render.set_defaults(run=cmd_render_check)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except BrokenPipeError:
        # Output was piped into something that stopped reading (e.g. `| head`).
        sys.stderr.close()
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
