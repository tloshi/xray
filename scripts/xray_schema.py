"""Structural validation of a Feature X-Ray data document.

The checks here are the ones that keep a diagram honest and readable:
edges must point at real nodes, a decision must actually branch, a flow must
start somewhere and every path must end somewhere. Problems that would make
the page wrong are errors; problems that make it weaker are warnings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
DIAGRAM_KINDS = {"flow", "sequence", "state", "components", "raw"}
NODE_TYPES = {"start", "end", "action", "process", "decision", "error", "external", "store", "screen", "unknown"}
TERMINAL_TYPES = {"end", "error", "unknown"}
CLOSED_TYPES = {"end", "error"}
# 'start', 'end' and 'unknown' state no fact about the code, so they need no evidence.
EVIDENCED_TYPES = {"action", "process", "decision", "external", "store", "screen", "error"}
EDGE_KINDS = {"", "main", "optional", "error"}
STEP_KINDS = {"sync", "reply", "async", "fail"}
LAYERS = {"user", "ui", "viewmodel", "domain", "data", "shared", "device", "backend", "external"}
SECTION_TYPES = {"cards", "links", "steps", "table", "callout", "prose", "layers"}
SEVERITIES = {"high", "medium", "low"}
MAX_NODE_LABEL = 60
MAX_STEP_LABEL = 72
MAX_GROUP_TITLE = 34
DEFAULT_DEPTH = "standard"
# What each depth may spend. An X-ray costs tokens to write and to read back on
# every later step, so the budget is part of the contract, not a suggestion.
BUDGET = {
    "quick":    {"flow_nodes": 14, "messages": 0,  "rows": 5,  "findings": 4,  "refs": 1, "text": 170, "kb": 14, "extra_diagrams": 0},
    "standard": {"flow_nodes": 22, "messages": 16, "rows": 8,  "findings": 8,  "refs": 2, "text": 300, "kb": 40, "extra_diagrams": 1},
    "deep":     {"flow_nodes": 26, "messages": 30, "rows": 18, "findings": 20, "refs": 3, "text": 520, "kb": 120, "extra_diagrams": 9},
}
MODULE_FACTOR = 2  # a module map covers many features, so its lists may be twice as long
PROSE_KEYS = {"what", "how", "cause", "check", "detail", "effect"}
# A label is read aloud by non-developers: identifiers and calls belong in 'tech'.
CODE_IN_LABEL = re.compile(r"[a-z][A-Z]|\w\(\)|\w\.\w+\(")
# Only `code` and **bold** are rendered; other markdown would show literally.
STRAY_MARKDOWN = re.compile(r"(?<![*\w])\*(?!\*)[^*\n]+?(?<!\*)\*(?![*\w])|(?<!\w)__[^_\n]+__(?!\w)|\[[^\]\n]+\]\([^)\n]+\)|^#{1,6} ", re.M)
PLAIN_KEYS = {"id", "path", "key", "tech", "symbol", "mermaid", "href", "type", "kind", "layer", "group", "from", "to"}


@dataclass
class Report:
    """Collects findings so the author sees everything in one run."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_id(report: Report, where: str, value: object, seen: set[str]) -> bool:
    if not isinstance(value, str) or not ID_RE.match(value):
        report.error(where, f"id {value!r} must match {ID_RE.pattern} (letters, digits, _ and -)")
        return False
    if value in seen:
        report.error(where, f"duplicate id {value!r}")
        return False
    seen.add(value)
    return True


def _validate_flow(d: dict, where: str, report: Report, feature: bool, diagram_ids: set[str]) -> set[str]:
    ids: set[str] = set()
    types: dict[str, str] = {}
    group_ids = {g.get("id") for g in d.get("groups", [])}
    for g in d.get("groups", []):
        if len(str(g.get("title", ""))) > MAX_GROUP_TITLE:
            report.warn(f"{where}.groups[{g.get('id')}]", f"title is {len(g['title'])} chars; a phase box clips long "
                                                          f"titles, keep it under {MAX_GROUP_TITLE}")
    nodes = d.get("nodes") or []
    if not nodes:
        report.error(where, "a flow needs at least one node")
    for i, n in enumerate(nodes):
        at = f"{where}.nodes[{i}]"
        if not _check_id(report, at, n.get("id"), ids):
            continue
        at = f"{where}.nodes[{n['id']}]"
        types[n["id"]] = n.get("type", "")
        if n.get("type") not in NODE_TYPES:
            report.error(at, f"type {n.get('type')!r} is not one of {sorted(NODE_TYPES)}")
        if not _is_text(n.get("label")):
            report.error(at, "label is required")
        elif len(n["label"]) > MAX_NODE_LABEL:
            report.warn(at, f"label is {len(n['label'])} chars; keep it under {MAX_NODE_LABEL} and move detail into 'what'")
        elif CODE_IN_LABEL.search(n["label"]):
            report.warn(at, f"label {n['label']!r} reads like code; say it in plain words and put the identifier in 'tech'")
        if n.get("detail") and n["detail"] not in diagram_ids:
            report.error(at, f"detail {n['detail']!r} is not the id of a diagram in this document")
        if n.get("group") and n["group"] not in group_ids:
            report.error(at, f"group {n['group']!r} is not declared in groups")
        if feature and n.get("type") in EVIDENCED_TYPES:
            if not n.get("refs") and n.get("confidence") != "inferred":
                report.warn(at, "no code reference; add refs or mark confidence: \"inferred\"")
            if not _is_text(n.get("what")):
                report.warn(at, "no 'what' text, so the inspector will be empty for this step")

    outgoing: dict[str, list[dict]] = {i: [] for i in ids}
    incoming: dict[str, int] = {i: 0 for i in ids}
    for i, e in enumerate(d.get("edges") or []):
        at = f"{where}.edges[{i}]"
        ok = True
        for end in ("from", "to"):
            if e.get(end) not in ids:
                report.error(at, f"'{end}' points at unknown node {e.get(end)!r}")
                ok = False
        if e.get("kind", "") not in EDGE_KINDS:
            report.error(at, f"kind {e.get('kind')!r} is not one of {sorted(EDGE_KINDS - {''})}")
        if ok:
            outgoing[e["from"]].append(e)
            incoming[e["to"]] += 1

    if ids and not any(t == "start" for t in types.values()):
        report.error(where, "no node of type 'start'; a reader needs to know where the flow begins")
    for node_id, node_type in types.items():
        at = f"{where}.nodes[{node_id}]"
        outs = outgoing[node_id]
        if node_type == "decision":
            if len(outs) < 2:
                report.error(at, "a decision needs at least two outgoing edges; with one exit it is a plain step")
            if any(not _is_text(e.get("label")) for e in outs):
                report.error(at, "every edge leaving a decision needs a label (Yes / No, or the named case)")
        if node_type != "start" and incoming[node_id] == 0:
            report.warn(at, "nothing leads to this node; it will float unconnected")
        if node_type not in TERMINAL_TYPES and not outs and (feature or node_type != "screen"):
            report.warn(at, "the flow stops here without reaching an 'end', 'error' or 'unknown' node")
        if node_type in CLOSED_TYPES and outs:
            report.warn(at, f"an '{node_type}' node has outgoing edges; use 'process' if the flow continues")
    if feature and ids and not any(t == "error" for t in types.values()):
        report.warn(where, "no 'error' node: a feature flow with no failure exits is usually not fully traced")
    return ids


def _validate_sequence(d: dict, where: str, report: Report) -> None:
    ids: set[str] = set()
    for i, p in enumerate(d.get("participants") or []):
        at = f"{where}.participants[{i}]"
        _check_id(report, at, p.get("id"), ids)
        if not _is_text(p.get("label")):
            report.error(at, "label is required")
        if p.get("layer") and p["layer"] not in LAYERS:
            report.error(at, f"layer {p['layer']!r} is not one of {sorted(LAYERS)}")
    if not ids:
        report.error(where, "a sequence needs participants")

    count = 0

    def walk(steps: list, at: str) -> None:
        nonlocal count
        for i, s in enumerate(steps or []):
            here = f"{at}[{i}]"
            if "alt" in s:
                for k, branch in enumerate(s["alt"] or []):
                    if not _is_text(branch.get("when")):
                        report.error(f"{here}.alt[{k}]", "'when' is required: name the condition of this branch")
                    walk(branch.get("steps"), f"{here}.alt[{k}].steps")
            elif "opt" in s or "loop" in s:
                key = "opt" if "opt" in s else "loop"
                if not _is_text(s[key].get("when")):
                    report.error(f"{here}.{key}", "'when' is required")
                walk(s[key].get("steps"), f"{here}.{key}.steps")
            elif "note" in s:
                for target in s["note"].get("over") or []:
                    if target not in ids:
                        report.error(f"{here}.note", f"'over' names unknown participant {target!r}")
                if not _is_text(s["note"].get("text")):
                    report.error(f"{here}.note", "text is required")
            else:
                count += 1
                for end in ("from", "to"):
                    if s.get(end) not in ids:
                        report.error(here, f"'{end}' names unknown participant {s.get(end)!r}")
                if not _is_text(s.get("label")):
                    report.error(here, "label is required")
                elif len(s["label"]) > MAX_STEP_LABEL:
                    report.warn(here, f"label is {len(s['label'])} chars; keep it under {MAX_STEP_LABEL}")
                if s.get("kind", "sync") not in STEP_KINDS:
                    report.error(here, f"kind {s.get('kind')!r} is not one of {sorted(STEP_KINDS)}")

    walk(d.get("steps"), f"{where}.steps")
    if count == 0:
        report.error(where, "a sequence needs at least one message")


def _validate_state(d: dict, where: str, report: Report) -> set[str]:
    ids: set[str] = set()
    for i, s in enumerate(d.get("states") or []):
        at = f"{where}.states[{i}]"
        _check_id(report, at, s.get("id"), ids)
        if not _is_text(s.get("label")):
            report.error(at, "label is required")
    if not ids:
        report.error(where, "a state diagram needs states")
    elif not any(s.get("initial") for s in d.get("states", [])):
        report.warn(where, "no state is marked initial: true")
    for i, t in enumerate(d.get("transitions") or []):
        for end in ("from", "to"):
            if t.get(end) not in ids:
                report.error(f"{where}.transitions[{i}]", f"'{end}' names unknown state {t.get(end)!r}")
    return ids


def _validate_components(d: dict, where: str, report: Report) -> set[str]:
    ids: set[str] = set()
    declared = {layer.get("id") for layer in d.get("layers", [])}
    for i, c in enumerate(d.get("components") or []):
        at = f"{where}.components[{i}]"
        _check_id(report, at, c.get("id"), ids)
        if not _is_text(c.get("label")):
            report.error(at, "label is required")
        layer = c.get("layer")
        if not layer:
            report.warn(at, "no layer; the component will sit outside the layer boxes")
        elif layer not in LAYERS and layer not in declared:
            report.error(at, f"layer {layer!r} is neither a standard layer {sorted(LAYERS)} nor declared in layers")
    if not ids:
        report.error(where, "a components diagram needs components")
    layer_of = {c.get("id"): c.get("layer") for c in d.get("components") or []}
    inside = 0
    for i, link in enumerate(d.get("links") or []):
        for end in ("from", "to"):
            if link.get(end) not in ids:
                report.error(f"{where}.links[{i}]", f"'{end}' names unknown component {link.get(end)!r}")
        if layer_of.get(link.get("from")) and layer_of.get(link.get("from")) == layer_of.get(link.get("to")):
            inside += 1
    if inside:
        report.warn(where, f"{inside} link(s) join components of the same layer; these make the layer boxes stagger "
                           "diagonally. Drop them, or move stores and external systems into a layer of their own")
    return ids


def _validate_targets(doc: dict, clickable: dict[str, set[str]], report: Report) -> None:
    """Checks that 'show on diagram' targets resolve to something clickable."""
    everything = set().union(*clickable.values()) if clickable else set()
    all_diagrams = {d.get("id") for d in doc.get("diagrams") or []}
    for key in ("troubleshooting", "switches", "findings"):
        for i, item in enumerate(doc.get(key) or []):
            for target in item.get("nodes") or []:
                diagram, _, node = str(target).rpartition(":")
                pool = clickable.get(diagram, set()) if diagram else everything
                if diagram and diagram not in all_diagrams:
                    report.error(f"{key}[{i}].nodes", f"{target!r} names unknown diagram {diagram!r}")
                elif diagram and diagram not in clickable:
                    report.error(f"{key}[{i}].nodes", f"{target!r}: diagram {diagram!r} has nothing to highlight; "
                                                      "only flow, components and state diagrams do")
                elif node not in pool:
                    report.error(f"{key}[{i}].nodes", f"{target!r} does not match any node, component or state id")


def _validate_lists(doc: dict, report: Report, feature: bool) -> None:
    for i, item in enumerate(doc.get("troubleshooting") or []):
        at = f"troubleshooting[{i}]"
        for key in ("symptom", "cause"):
            if not _is_text(item.get(key)):
                report.error(at, f"'{key}' is required")
        if item.get("severity", "medium") not in SEVERITIES:
            report.error(at, f"severity must be one of {sorted(SEVERITIES)}")
        if not _is_text(item.get("check")):
            report.warn(at, "no 'check': say how someone can confirm this cause")
        if feature and not item.get("nodes"):
            report.warn(at, "no 'nodes': link the symptom to the steps to inspect")

    for i, item in enumerate(doc.get("findings") or []):
        at = f"findings[{i}]"
        for key in ("title", "detail"):
            if not _is_text(item.get(key)):
                report.error(at, f"'{key}' is required")
        if item.get("severity", "medium") not in SEVERITIES:
            report.error(at, f"severity must be one of {sorted(SEVERITIES)}")
        if not item.get("refs"):
            report.warn(at, "a code finding without refs cannot be checked by a reader")
    for i, item in enumerate(doc.get("caveats") or []):
        text = item.get("text") if isinstance(item, dict) else item
        if not _is_text(text):
            report.error(f"caveats[{i}]", "must be a sentence, or {\"text\": \"…\", \"refs\": […]}")

    keys: set[str] = set()
    for i, item in enumerate(doc.get("switches") or []):
        at = f"switches[{i}]"
        if not _is_text(item.get("key")):
            report.error(at, "'key' is required")
        elif item["key"] in keys:
            report.error(at, f"duplicate switch {item['key']!r}")
        else:
            keys.add(item["key"])
        if not _is_text(item.get("effect")):
            report.error(at, "'effect' is required")
    for d in doc.get("diagrams") or []:
        for n in d.get("nodes") or []:
            for used in n.get("switches") or []:
                if used not in keys:
                    report.error(f"diagrams[{d.get('id')}].nodes[{n.get('id')}]",
                                 f"switch {used!r} is not described in the top-level 'switches' list")

    for i, s in enumerate(doc.get("sections") or []):
        at = f"sections[{i}]"
        if s.get("type") not in SECTION_TYPES:
            report.error(at, f"type {s.get('type')!r} is not one of {sorted(SECTION_TYPES)}")
        if s.get("placement", "bottom") not in {"top", "bottom"}:
            report.error(at, "placement must be 'top' or 'bottom'")
        if s.get("type") == "table":
            width = len(s.get("columns") or [])
            for k, row in enumerate(s.get("rows") or []):
                if len(row) != width:
                    report.error(f"{at}.rows[{k}]", f"has {len(row)} cells but there are {width} columns")
    for i, item in enumerate(doc.get("glossary") or []):
        if not _is_text(item.get("term")) or not _is_text(item.get("meaning")):
            report.error(f"glossary[{i}]", "'term' and 'meaning' are required")
    for i, item in enumerate(doc.get("tests") or []):
        if not _is_text(item.get("path")):
            report.error(f"tests[{i}]", "'path' is required")


def _lint_text(value: object, where: str, report: Report) -> None:
    """Warns about markdown the page will not render (italics, links, headings)."""
    if isinstance(value, list):
        for i, item in enumerate(value):
            label = item["id"] if isinstance(item, dict) and isinstance(item.get("id"), str) else i
            _lint_text(item, f"{where}[{label}]", report)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in PLAIN_KEYS and key not in {"refs", "_build"}:
                _lint_text(item, f"{where}.{key}" if where else key, report)
    elif isinstance(value, str):
        found = STRAY_MARKDOWN.search(value)
        if found:
            report.warn(where, f"{found.group(0)[:40]!r} will be shown literally; only `code` and **bold** are rendered")


def _count_messages(steps: list) -> int:
    total = 0
    for s in steps or []:
        if "alt" in s:
            total += sum(_count_messages(b.get("steps")) for b in s["alt"] or [])
        elif "opt" in s or "loop" in s:
            total += _count_messages((s.get("opt") or s.get("loop") or {}).get("steps"))
        elif "note" not in s:
            total += 1
    return total


def _walk_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for key, item in value.items():
            if key != "_build":
                yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _check_budget(doc: dict, report: Report, size_bytes: int | None) -> None:
    """Warns where the document spends more than its declared depth allows."""
    depth = (doc.get("meta") or {}).get("depth")
    if depth is None:
        report.warn("meta.depth", f"missing; assuming {DEFAULT_DEPTH!r}. Declare quick, standard or deep")
        depth = DEFAULT_DEPTH
    if depth not in BUDGET:
        report.error("meta.depth", f"{depth!r} is not one of {list(BUDGET)}")
        return
    b = BUDGET[depth]
    factor = MODULE_FACTOR if doc.get("kind") == "module" else 1
    over = lambda what, n, limit, advice: report.warn(  # noqa: E731
        "budget", f"{what}: {n}, but {depth!r} depth allows {limit}. {advice}")
    hint = "Trim, or declare a deeper 'depth' if the user asked for more."

    diagrams = doc.get("diagrams") or []
    for d in diagrams:
        if d.get("kind") == "flow" and len(d.get("nodes") or []) > b["flow_nodes"]:
            over(f"flow {d.get('id')!r} nodes", len(d["nodes"]), b["flow_nodes"],
                 "Merge steps, or split into two flows linked by a node's 'detail'.")
        if d.get("kind") == "sequence":
            n = _count_messages(d.get("steps"))
            if n > b["messages"]:
                over(f"sequence {d.get('id')!r} messages", n, b["messages"],
                     "A quick X-ray has no sequence diagram." if not b["messages"] else hint)
    extra = sum(1 for d in diagrams if d.get("kind") not in {"flow", "sequence"})
    if extra > b["extra_diagrams"] * factor:
        over("components / state / raw diagrams", extra, b["extra_diagrams"] * factor, hint)
    for key, limit in (("troubleshooting", b["rows"]), ("findings", b["findings"])):
        if len(doc.get(key) or []) > limit * factor:
            over(f"{key} rows", len(doc[key]), limit * factor, "Keep the ones a reader would act on.")

    many_refs = sum(1 for item in _walk_dicts(doc) if len(item.get("refs") or []) > b["refs"])
    if many_refs:
        over("items with more references than needed", many_refs, f"{b['refs']} per item",
             "One reference that proves the step is enough.")
    long_text = sum(1 for item in _walk_dicts(doc) for k in PROSE_KEYS
                    if isinstance(item.get(k), str) and len(item[k]) > b["text"])
    if long_text:
        over("texts longer than the budget", long_text, f"{b['text']} characters each", "Say it in fewer words.")
    if size_bytes is not None and size_bytes > b["kb"] * factor * 1024:
        over("data file size", f"{size_bytes // 1024} KB", f"{b['kb'] * factor} KB", hint)


def validate(doc: dict, report: Report, size_bytes: int | None = None) -> None:
    """Validates the whole document, appending findings to the report."""
    if doc.get("xray") != 1:
        report.error("xray", "must be 1 (the schema version)")
    kind = doc.get("kind")
    if kind not in {"feature", "module"}:
        report.error("kind", "must be 'feature' or 'module'")
    feature = kind == "feature"
    meta = doc.get("meta") or {}
    for key in ("title", "module", "summary"):
        if not _is_text(meta.get(key)):
            report.error(f"meta.{key}", "is required")
    if feature and not _is_text(meta.get("scope")):
        report.warn("meta.scope", "say what this X-ray covers and what it leaves out")

    diagrams = doc.get("diagrams") or []
    if not diagrams:
        report.error("diagrams", "at least one diagram is required")
    seen: set[str] = set()
    clickable: dict[str, set[str]] = {}
    kinds: list[str] = []
    for i, d in enumerate(diagrams):
        where = f"diagrams[{i}]"
        if not _check_id(report, where, d.get("id"), seen):
            continue
        where = f"diagrams[{d['id']}]"
        kind_d = d.get("kind")
        kinds.append(kind_d)
        if not _is_text(d.get("title")):
            report.error(where, "title is required")
        if kind_d == "flow":
            clickable[d["id"]] = _validate_flow(d, where, report, feature, {x.get("id") for x in diagrams})
        elif kind_d == "sequence":
            _validate_sequence(d, where, report)
        elif kind_d == "state":
            clickable[d["id"]] = _validate_state(d, where, report)
        elif kind_d == "components":
            clickable[d["id"]] = _validate_components(d, where, report)
        elif kind_d == "raw":
            if not _is_text(d.get("mermaid")):
                report.error(where, "a raw diagram needs Mermaid source in 'mermaid'")
        else:
            report.error(where, f"kind {kind_d!r} is not one of {sorted(DIAGRAM_KINDS)}")

    _validate_lists(doc, report, feature)
    _validate_targets(doc, clickable, report)
    _lint_text(doc, "", report)
    _check_budget(doc, report, size_bytes)

    if feature:
        quick = meta.get("depth") == "quick"
        if "flow" not in kinds:
            report.warn("diagrams", "a feature X-ray should have a 'flow' diagram (the end-to-end path with decisions)")
        if "sequence" not in kinds and not quick:
            report.warn("diagrams", "a feature X-ray should have a 'sequence' diagram (who calls whom across layers)")
        if not doc.get("troubleshooting"):
            report.warn("troubleshooting", "empty; symptom-to-cause rows are what let a reader find a problem from the page")
        explained = any("test" in str(c.get("text") if isinstance(c, dict) else c).lower() for c in doc.get("caveats") or [])
        if "tests" not in doc and not explained and meta.get("depth") == "deep":
            report.warn("tests", "missing; list related test files, [] if the sources are there and nothing covers this, "
                                 "or add a caveat when the checkout has no tests")
