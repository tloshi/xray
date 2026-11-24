"""Renders saved run records as one self-contained HTML page.

`xray.py runs <folder> --html runs.html` — every X-ray that was produced, with
a link to its page, what it cost and what it contains, newest first.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

from xray_usage import human

CSS = """
:root{--bg:#F4F6FB;--card:#fff;--ink:#0E1726;--soft:#5B687D;--line:#DCE2EC;--out:#0B5FD9;--cache:#0F766E;--chip:#E3EDFD}
@media (prefers-color-scheme:dark){:root{--bg:#0C111D;--card:#141A29;--ink:#E7ECF6;--soft:#A8B3C7;--line:#262F45;--out:#7FAAF8;--cache:#4FD1C5;--chip:#18284A}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,"Segoe UI",system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:36px 20px 64px}
h1{font-size:30px;letter-spacing:-.02em;margin:0 0 6px}p.lede{color:var(--soft);margin:0 0 24px;max-width:75ch}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.card .k{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--soft)}
.card .v{font-size:24px;font-weight:800;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:14px}
table{border-collapse:collapse;width:100%;min-width:980px;font-size:13.5px}
th{text-align:left;padding:10px 12px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--soft);border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}
td.n{font-variant-numeric:tabular-nums;white-space:nowrap}a{color:var(--out);font-weight:600;text-decoration:none}a:hover{text-decoration:underline}
.sub{color:var(--soft);font-size:12px}.chip{display:inline-block;background:var(--chip);color:var(--out);border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600}
.bar{height:6px;border-radius:3px;margin-top:5px;min-width:2px}.bar.o{background:var(--out)}.bar.c{background:var(--cache)}
footer{color:var(--soft);font-size:12px;margin-top:18px}
"""


def _load(folder: Path) -> list[tuple[dict, Path]]:
    runs = []
    for path in folder.rglob("*.run.json"):
        try:
            runs.append((json.loads(path.read_text(encoding="utf-8")), path))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(runs, key=lambda pair: str(pair[0].get("finishedAt", "")), reverse=True)


def _bar(value: object, largest: float, kind: str) -> str:
    if not isinstance(value, (int, float)) or not largest:
        return ""
    return f'<div class="bar {kind}" style="width:{max(2, round(100 * value / largest))}%"></div>'


def render(folder: Path, out_path: Path) -> int:
    """Writes the overview page and returns the number of runs listed."""
    runs = _load(folder)
    esc = html.escape
    tokens = [r.get("tokens") or {} for r, _ in runs]
    max_out = max((t.get("output") or 0 for t in tokens), default=0)
    max_cache = max((t.get("cacheRead") or 0 for t in tokens), default=0)
    rows = []
    for record, path in runs:
        t = record.get("tokens") or {}
        x = record.get("xray") or {}
        page = path.parent.parent / f"{record.get('name')}.html"
        title = esc(str(record.get("title") or record.get("name")))
        link = (f'<a href="{esc(os.path.relpath(page, out_path.parent))}">{title}</a>' if page.is_file() else title)
        diagrams = ", ".join(f"{d.get('kind')} {d.get('items')}" for d in x.get("diagrams") or [])
        rows.append(
            f"<tr><td class='n'>{esc(str(record.get('finishedAt', ''))[:16].replace('T', ' '))}</td>"
            f"<td>{link}<div class='sub'>{esc(str(record.get('modulePath') or record.get('module') or ''))} · {esc(str(record.get('kind') or ''))}</div></td>"
            f"<td><span class='chip'>{esc(str(record.get('depth', '')))}</span><div class='sub'>skill {esc(str(record.get('skillVersion', '')))}</div></td>"
            f"<td>{esc(', '.join(record.get('models') or []) or '–')}<div class='sub'>{esc(str(record.get('harness') or ''))}</div></td>"
            f"<td class='n'>{human(t.get('output'))}{_bar(t.get('output'), max_out, 'o')}</td>"
            f"<td class='n'>{human(t.get('cacheRead'))}{_bar(t.get('cacheRead'), max_cache, 'c')}</td>"
            f"<td class='n'>{human(t.get('cacheWrite'))}</td>"
            f"<td class='n'>{record.get('apiCalls') or '–'}</td>"
            f"<td class='n'>{round((record.get('durationSeconds') or 0) / 60)}</td>"
            f"<td class='n'>{x.get('references', '–')} / {x.get('filesCited', '–')}</td>"
            f"<td class='n'>{x.get('findings', '–')} / {x.get('troubleshooting', '–')}</td>"
            f"<td class='sub'>{esc(diagrams)}</td></tr>")
    total_out = sum(t.get("output") or 0 for t in tokens)
    total_cache = sum(t.get("cacheRead") or 0 for t in tokens)
    cards = [("X-rays produced", str(len(runs))), ("Output tokens, total", human(total_out)),
             ("Cached input, total", human(total_cache)),
             ("Models used", str(len({m for r, _ in runs for m in r.get("models") or []})))]
    page = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'><title>X-Ray runs</title>"
        f"<style>{CSS}</style></head><body><main><h1>X-Ray runs</h1>"
        "<p class='lede'>Every X-Ray produced here: what was traced, with which model, what it cost in tokens "
        "and what the page contains. Output tokens are what the model wrote; cached input is the context it re-read "
        "on each call.</p><div class='cards'>"
        + "".join(f"<div class='card'><div class='k'>{esc(k)}</div><div class='v'>{esc(v)}</div></div>" for k, v in cards)
        + "</div><div class='wrap'><table><thead><tr><th>Finished</th><th>X-ray</th><th>Depth</th><th>Model</th>"
          "<th>Output</th><th>Cached input</th><th>Cache write</th><th>Calls</th><th>Min</th><th>Refs / files</th>"
          "<th>Findings / symptoms</th><th>Diagrams</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div><footer>Generated from the run records under "
        + esc(str(folder)) + ". Regenerate with: xray.py runs &lt;folder&gt; --html &lt;file&gt;</footer></main></body></html>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return len(runs)
