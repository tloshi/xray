"""Renders the map of an output folder: every X-ray page, laid out like the project.

`xray.py build` rewrites `<out>/index.html` after each page, and
`xray.py index <folder>` does it on demand. Pages are grouped by the top-level
area of the repository and then by module, so the index reads like the
project tree.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

import xray_layout
from xray_report import CSS
from xray_usage import human

INDEX_NAME = "index.html"
GENERATOR = '<meta name="generator" content="xray-index">'
UNFILED = ""
SUMMARY_WIDTH = 170

EXTRA_CSS = """
.bar-top{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:22px}
#q{flex:1;min-width:220px;padding:10px 14px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);font:inherit}
#q:focus-visible,a:focus-visible{outline:2px solid var(--out);outline-offset:2px}
h2{font:700 12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--soft);margin:30px 0 10px}
h2 span{font-weight:400;letter-spacing:0;text-transform:none}
.mod{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:12px;overflow:hidden}
.mod>header{padding:10px 16px;border-bottom:1px solid var(--line);font:600 13.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all}
.mod>header i{font-style:normal;color:var(--soft);font-weight:400}
.row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 18px;padding:12px 16px;border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:0}.row:hover{background:color-mix(in srgb,var(--chip) 45%,transparent)}
.row a{font-size:15.5px}.row .facts{text-align:right;white-space:nowrap}
.chip.a{background:var(--cache);color:var(--card)}.chip+.chip{margin-left:4px}
.empty{color:var(--soft);padding:26px 0}[hidden]{display:none!important}
@media (max-width:640px){.row{grid-template-columns:1fr}.row .facts{text-align:left;white-space:normal}}
"""

SCRIPT = """
const q=document.getElementById('q');
q.addEventListener('input',()=>{const s=q.value.trim().toLowerCase();
document.querySelectorAll('.row').forEach(r=>{r.hidden=!!s&&!r.dataset.text.includes(s)});
document.querySelectorAll('.mod').forEach(m=>{m.hidden=!m.querySelector('.row:not([hidden])')});
document.querySelectorAll('section').forEach(a=>{a.hidden=!a.querySelector('.mod:not([hidden])')});
document.getElementById('none').hidden=!!document.querySelector('.row:not([hidden])')});
"""


def _clip(text: object, width: int) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= width else flat[: width - 1].rstrip() + "…"


def collect(out: Path) -> list[dict]:
    """One entry per X-ray page under the output folder."""
    entries = []
    for page in sorted(out.rglob("*.html")):
        doc = xray_layout.read_page(page)
        if doc is None:
            continue
        meta = doc.get("meta") or {}
        build = doc.get("_build") or {}
        folder = page.parent.parent.relative_to(out).as_posix() if page.parent != out else UNFILED
        entries.append({
            "href": os.path.relpath(page, out).replace(os.sep, "/"),
            "group": UNFILED if folder == "." else folder,
            "title": str(meta.get("title") or page.stem),
            "summary": _clip(meta.get("summary"), SUMMARY_WIDTH),
            "module": doc.get("kind") == "module",
            "depth": str(meta.get("depth") or "quick"),
            "generated": str(build.get("generatedAt") or ""),
            "commit": str(build.get("commit") or ""),
            "refs": build.get("refsVerified") if build.get("verified") else None,
            "output": ((build.get("usage") or {}).get("tokens") or {}).get("output"),
            "findings": len(doc.get("findings") or []),
        })
    return entries


def _row(entry: dict) -> str:
    esc = html.escape
    facts = [esc(entry["generated"])] if entry["generated"] else []
    if entry["commit"]:
        facts.append(f"commit {esc(entry['commit'])}")
    numbers = [f"{entry['refs']} reference{'' if entry['refs'] == 1 else 's'} verified" if entry["refs"] is not None else "not verified"]
    if entry["findings"]:
        numbers.append(f"{entry['findings']} finding{'' if entry['findings'] == 1 else 's'}")
    if entry["output"]:
        numbers.append(f"{human(entry['output'])} output tokens")
    kind = "<span class='chip a'>Anatomy</span>" if entry["module"] else "<span class='chip'>X-Ray</span>"
    text = esc(f"{entry['title']} {entry['summary']} {entry['group']}".lower(), quote=True)
    return (f"<div class='row' data-text=\"{text}\"><div><a href=\"{esc(entry['href'], quote=True)}\">{esc(entry['title'])}</a>"
            f"<div class='sub'>{esc(entry['summary'])}</div></div>"
            f"<div class='facts'>{kind}<span class='chip'>{esc(entry['depth'])}</span>"
            f"<div class='sub'>{' · '.join(facts)}</div><div class='sub'>{esc(' · '.join(numbers))}</div></div></div>")


def _areas(entries: list[dict]) -> str:
    """Top-level area of the repository, then module, then its pages (the module's own page first)."""
    groups: dict[str, list[dict]] = {}
    for entry in entries:
        groups.setdefault(entry["group"], []).append(entry)
    areas: dict[str, list[str]] = {}
    for group in sorted(groups, key=lambda g: (g == UNFILED, g.lower())):
        area, _, rest = group.partition("/")
        rows = sorted(groups[group], key=lambda e: (not e["module"], e["title"].lower()))
        label = (f"<i>{html.escape(area)} / </i>{html.escape(rest)}" if rest else html.escape(area)) if group else "Not filed under a module yet"
        areas.setdefault(area, []).append(
            f"<article class='mod'><header>{label}</header>{''.join(_row(e) for e in rows)}</article>")
    parts = []
    for area, modules in areas.items():
        count = sum(len(groups[g]) for g in groups if g.partition("/")[0] == area)
        parts.append(f"<section><h2>{html.escape(area) or 'Other'} <span>· {count}</span></h2>{''.join(modules)}</section>")
    return "".join(parts)


def writable(out: Path) -> bool:
    """False when `<out>/index.html` exists and is somebody else's file."""
    target = out / INDEX_NAME
    try:
        return not target.exists() or GENERATOR in target.read_text(encoding="utf-8", errors="replace")[:600]
    except OSError:
        return False


def render(out: Path) -> tuple[Path, int] | None:
    """Writes `<out>/index.html`; returns (path, pages), or None when a file that is not ours is in the way."""
    target = out / INDEX_NAME
    if not writable(out):
        return None
    entries = collect(out)
    modules = {e["group"] for e in entries if e["group"]}
    latest = max((e["generated"] for e in entries), default="") or "–"
    cards = [("Pages", str(len(entries))), ("Modules covered", str(len(modules))),
             ("Module overviews", str(sum(e["module"] for e in entries))), ("Latest page", latest)]
    body = _areas(entries) if entries else "<p class='empty'>No X-ray pages here yet.</p>"
    page = (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>{GENERATOR}"
        "<meta name='viewport' content='width=device-width, initial-scale=1'><title>X-Ray index</title>"
        f"<style>{CSS}{EXTRA_CSS}</style></head><body><main><h1>X-Ray index</h1>"
        "<p class='lede'>Every X-ray page of this project, filed the way the project itself is laid out: "
        "the area of the repository, the module, then the features traced in it.</p><div class='cards'>"
        + "".join(f"<div class='card'><div class='k'>{html.escape(k)}</div><div class='v'>{html.escape(v)}</div></div>" for k, v in cards)
        + "</div><div class='bar-top'><input id='q' type='search' placeholder='Filter by feature, module or word…' "
          "aria-label='Filter pages' autocomplete='off'></div>"
        + body + "<p class='empty' id='none' hidden>Nothing matches that filter.</p>"
        "<footer>Rewritten by every <code>xray.py build</code>. Regenerate by hand with "
        "<code>xray.py index &lt;folder&gt;</code>; find pages whose code has changed with "
        f"<code>xray.py check &lt;folder&gt;</code>.</footer></main><script>{SCRIPT}</script></body></html>")
    out.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return target, len(entries)
