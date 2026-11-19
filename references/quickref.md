# Quick reference

Everything needed to write a valid X-ray, on one page. Open `schema.md`,
`craft.md` or `tracing.md` only for the section you are stuck on.

## Shape of the file

```json
{
  "xray": 1, "kind": "feature",
  "meta": { "title": "…", "module": "…", "summary": "plain language, no class names",
            "scope": "Covers … Does not cover …", "sourceRoot": "app/<module>",
            "depth": "standard", "lang": "en" },
  "glance":  [{ "label": "Trigger", "value": "…" }],
  "caveats": ["what this checkout did not let you see"],
  "diagrams": [
    { "id": "flow", "kind": "flow", "title": "End-to-end flow",
      "groups": [{ "id": "entry", "title": "1 · Entry" }],
      "nodes": [
        { "id": "start", "type": "start", "group": "entry", "label": "Where it begins" },
        { "id": "is_on", "type": "decision", "group": "entry", "label": "A yes/no question?",
          "tech": "Class.method", "what": "business meaning", "how": "what the code does",
          "refs": ["path/File.kt#symbol"], "switches": ["KEY"], "risks": ["what goes wrong here"] }
      ],
      "edges": [{ "from": "start", "to": "is_on", "kind": "main" },
                { "from": "is_on", "to": "hidden", "label": "No" }] },
    { "id": "sequence", "kind": "sequence", "title": "Who calls whom",
      "participants": [{ "id": "user", "label": "User", "type": "actor", "layer": "user" },
                       { "id": "vm", "label": "Screen logic", "tech": "SomeViewModel", "layer": "viewmodel" }],
      "steps": [{ "from": "user", "to": "vm", "label": "Taps Save", "tech": "onSave()", "refs": ["…#onSave"] },
                { "alt": [{ "when": "valid", "steps": [] }, { "when": "invalid", "steps": [] }] }] }
  ],
  "troubleshooting": [{ "symptom": "what the user sees", "cause": "the mechanism", "check": "how to confirm",
                        "severity": "high", "nodes": ["is_on"], "refs": ["…"] }],
  "findings": [{ "title": "what looks wrong in the code", "detail": "…", "severity": "medium", "nodes": ["…"], "refs": ["…"] }],
  "switches": [{ "key": "KEY", "effect": "…", "default": "…", "kind": "parameter", "scope": "store" }],
  "data": [{ "name": "…", "kind": "document", "direction": "write", "what": "…", "boundary": "leaves the device" }],
  "glossary": [{ "term": "…", "meaning": "…" }],
  "openQuestions": ["what the code did not tell you"]
}
```

## Budget by depth (the build warns past these)

| | quick | standard | deep |
|---|---|---|---|
| flow nodes | 14 | 22 | 26 per flow |
| sequence messages | no sequence | 16 | 30 |
| extra diagrams (components / state) | 0 | 1 | as needed |
| troubleshooting rows / findings | 5 / 4 | 8 / 8 | 18 / 20 |
| chars per `what` / `how` / `cause` / `check` / `detail` / `effect` | 170 | 300 | 520 |
| refs per item | 1 | 2 | 3 |
| data size | 14 KB | 40 KB | 120 KB |

## Values

| Field | Allowed |
|---|---|
| flow node `type` | `start` · `action` (user does) · `process` (system does) · `screen` · `decision` · `external` (other system) · `store` (read/write) · `end` · `error` · `unknown` (path leaves what you could read) |
| edge `kind` | `main` (normal path, mark it) · `optional` (side path, background) · `error` (red; automatic into an `error` node) |
| participant / component `layer` | `user` · `ui` (screens, templates) · `viewmodel` (presentation logic: view model, component class, controller) · `domain` (business rules, services) · `data` (repositories, API and database clients) · `shared` · `device` · `backend` · `external` — declare participants in this order |
| sequence step `kind` | `sync` · `reply` · `async` · `fail`; blocks: `alt` (branches with `when`), `opt`, `loop`, `note` |
| other diagram kinds | `components` (`components` + `links`), `state` (`states` + `transitions`), `raw` (Mermaid text) |
| `severity` | `high` · `medium` · `low` |
| on switches, findings, troubleshooting, data | optional `refs`; `nodes` (ids to highlight) on the first three. `tests` only at deep depth |
| switch `kind` / `scope` | free text: `parameter`, `feature flag`, `master data`, `code constant` / `global`, `region`, `tenant`, `item` |
| data `direction` / `boundary` | `read` · `write` · `read-write` / free text when it crosses one: `leaves the device`, `leaves the company` |
| `confidence` | `"inferred"` on anything you concluded but did not see in code |
| text formatting | `` `code` `` and `**bold**` only |

## References

Write `"path/File.kt#symbol"` and let the build find the line. `symbol` is any
literal text on that line — a function name, a constant, a log message; it
may itself contain `#`. The
path is relative to the repository root or to `meta.sourceRoot` — point
`sourceRoot` at the deepest folder the feature's files share and every
reference gets shorter. Pick text
that means one thing (`#printBatch`, not `#print`). One reference per step is
enough; two when a step joins two places. Every identifier you put in `tech`
should occur in a file that step cites, or the build warns.

## Rules the build enforces

- every edge points at a real node; a decision has two or more labelled exits
- at least one `start`; every branch reaches `end`, `error` or `unknown`
- every `nodes` target in troubleshooting / findings / switches exists
- a reference whose symbol is not in the file **fails the build**
- warnings: a step without evidence, a label that reads like code, more nodes
  or longer text than the declared `depth` allows

## Writing

- `label`: what happens, in words a user of the product would use — no identifiers, under 60 characters
- every step except `start`, `end` and `unknown` needs a `what` and a reference
- `tech`: the real `Class.method`; `what`: business meaning; `how`: the code's logic
- a decision is a question; its exits are the answers
- a `symptom` is what the user sees, never the internal cause
- `action` is only for what the user does; `process` for what the system does

## Tracing in five moves

1. **Find the entry**: the class or screen name, a parameter key, or the UI
   text. Search first; read second.
2. **Follow the call chain** one hop at a time, from the UI or entry point
   through the business logic to storage, the network and the backend. The
   project profile names this project's layers and where they live.
3. **Read functions, not files.** List a large file's signatures, then read
   only the methods on the path.
4. **Note each branch and its condition**: `if`, `when` / `switch`, early
   return, validation, `catch`, parameter check, and the success and error
   arms of an asynchronous call (`subscribe({next, error})`, `then` / `catch`).
   In a UI template, follow an event binding to its handler.
5. **Look for silent failure**: `filter` / `mapNotNull` / `firstOrNull`
   dropping items, `…OrNull` parsing, `.valueOrNull` + `filterNotNull()`,
   `catch` or an error callback that only logs, an unguarded `.find(...)`
   result, duplicates collapsed into a map, a loading state nobody observes on
   error, a parameter that hides a control.
