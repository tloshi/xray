# The `.xray.json` format

Everything the page shows comes from one JSON file. This is the reference for
every field. `scripts/xray.py build` validates all of it and tells you exactly
what is wrong, so when in doubt, build and read the output.

## Contents

1. Top level
2. Code references (`refs`)
3. Text formatting
4. Diagram kind: `flow`
5. Diagram kind: `sequence`
6. Diagram kind: `components`
7. Diagram kind: `state`
8. Diagram kind: `raw`
9. `troubleshooting`, `switches`, `data`, `tests`, `glossary`, `openQuestions`
10. Narrative `sections`

## 1. Top level

```json
{
  "xray": 1,
  "kind": "feature",
  "meta": {
    "title": "Applying a discount code",
    "module": "checkout",
    "modulePath": "app/checkout",
    "package": "com.example.shop.checkout",
    "summary": "One short paragraph in plain language: what this does and for whom.",
    "scope": "Covers … Does not cover …",
    "sourceRoot": "app/checkout/src/main",
    "depth": "standard",
    "lang": "en",
    "lens": "business"
  },
  "glance": [{ "label": "Trigger", "value": "User taps **Apply**" }],
  "caveats": [],
  "diagrams": [],
  "troubleshooting": [],
  "findings": [],
  "switches": [],
  "sections": [],
  "data": [],
  "tests": [],
  "glossary": [],
  "openQuestions": []
}
```

| Field | Required | Meaning |
|---|---|---|
| `xray` | yes | schema version, always `1` |
| `kind` | yes | `"feature"` or `"module"` |
| `meta.title` | yes | the page title — a name, not a sentence |
| `meta.module` | yes | module name |
| `meta.modulePath` | yes | the module's folder, relative to the repository root — the folder holding its build file, never a source folder inside it. It decides where the page is filed: `<output folder>/<modulePath>/<name>/<name>.xray.json`. The build stops if the folder does not exist and warns if the cited files belong to another module. A data file from before version 1.2 that lacks it still builds, with a warning |
| `meta.summary` | yes | plain-language paragraph; the first thing a manager reads |
| `meta.scope` | feature | what is covered and what is not |
| `meta.depth` | yes | `quick`, `standard` or `deep` — how far this X-ray goes. It is shown on the page and sets the budget the build checks (node counts, rows, text length, file size); see the table in SKILL.md |
| `meta.package` | no | shown next to the module |
| `meta.sourceRoot` | no | folder that `refs` paths may be relative to; usually deeper than `modulePath` |
| `meta.lang` | no | `en` (default), `de` or `sq` — the language of the viewer's own labels; write your content in the same language |
| `meta.lens` | no | lens shown first: `business` (default) or `developer` |
| `glance` | no | 2–4 key facts shown as cards. Counts (steps, decisions, failure points, switches) are added automatically |
| `caveats` | no | sentences about what this checkout did not let you see; shown at the top as "Limits of this analysis". An entry may be `{ "text": "…", "refs": […] }` when code shows the gap (a call whose target is missing) |
| `diagrams` | yes | at least one |

Ids everywhere: letters, digits, `_` and `-`, starting with a letter or digit.
Diagram ids are unique in the document; node, component, state and
participant ids are unique within their diagram, so the same id may be reused
in another diagram. Use meaningful ids (`match_items`, not `n7`) — they
appear in error messages and in links to a step.

## 2. Code references (`refs`)

Any object may carry `"refs": [...]`. Every one is checked against the working
tree when you build. Four equivalent forms:

```json
"refs": [
  "domain/service/DiscountService.kt#applyDiscount",
  "domain/service/DiscountService.kt:22#applyDiscount",
  "domain/service/DiscountService.kt:22",
  { "path": "domain/service/DiscountService.kt", "line": 22, "symbol": "applyDiscount" }
]
```

- **Path** is relative to the repository root or to `meta.sourceRoot` (the
  repository root is tried first).
- **`#symbol`** is text that must appear at that place. Usually a function,
  class, property or constant name, but any literal text on the line works,
  spaces and punctuation included — a log message (`#Could not get any
  price data`) or an expression (`#readTimeoutInSeconds = 180`) is fine evidence.
  Always give one. With a symbol the build confirms that this text is at that
  place in the file; without one it can only check that the file exists.
- **Line** is optional when a symbol is given — the build finds it. That is the
  safest form: write `path#symbol` and never type a line number from memory.
- A symbol more than a few lines from the stated line fails the build and
  prints where it really is; `--fix-refs` corrects the line in your file.
- A symbol that is nowhere in the file fails the build. That means the claim
  is wrong, not the line.
- **How a symbol is matched.** It is a plain substring search, so pick text
  specific enough to mean one thing: `#printBatch`, not `#print` (which also
  matches `printer` and `printData`). When no line is given and the text
  occurs several times, the line that *declares* it (`fun`, `class`, `val`,
  `object`, …) wins, then the first occurrence. To see where every reference
  landed, build with `--verbose`.

## 3. Text formatting

Descriptive text accepts two inline marks only: `` `code` `` and `**bold**`,
and a blank line starts a new paragraph. That covers `summary`, `scope`,
`what`, `how`, `risks`, `cause`, `check`, `effect`, `default`, `detail`,
`caveats`, `openQuestions`, `glance` values, table cells and section text.

Names are shown exactly as written, with no formatting: `title`, `label`,
`tech`, `ui`, `term`, `key`, `kind`, `scope`, `boundary`.

Everything else appears literally, so do not write italics (`*like this*`),
links, headings, HTML or Mermaid syntax anywhere except in a `raw` diagram.
The build warns when it sees markdown it will not render.

## 4. Diagram kind: `flow`

The end-to-end path with decisions. Clicking a node opens its details.

```json
{
  "id": "flow", "kind": "flow", "title": "End-to-end flow",
  "subtitle": "From entering the code to the new total",
  "direction": "TB",
  "groups": [{ "id": "entry", "title": "1 · Entry" }],
  "nodes": [
    { "id": "start", "type": "start", "group": "entry", "label": "User is on the checkout screen" },
    {
      "id": "check_enabled", "type": "decision", "group": "entry",
      "label": "Are discount codes switched on?",
      "tech": "CheckoutSettingsService.isDiscountEnabled",
      "what": "The code field only exists when discounts are switched on.",
      "how": "Reads `DISCOUNTS_ENABLED` per region, falling back to the global value.",
      "refs": ["domain/service/CheckoutSettingsService.kt#isDiscountEnabled"],
      "switches": ["DISCOUNTS_ENABLED"],
      "risks": ["If the parameter is missing the button is silently hidden"]
    }
  ],
  "edges": [
    { "from": "start", "to": "check_enabled", "kind": "main" },
    { "from": "check_enabled", "to": "hidden", "label": "No" }
  ]
}
```

**Node fields**

| Field | Required | Meaning |
|---|---|---|
| `id`, `type`, `label` | yes | `label` is the plain-language text in the box |
| `group` | no | id of a group (phase box) |
| `tech` | no | the code identifier, shown in the Developer lens: `Class.method` |
| `what` | recommended | what happens, in business terms |
| `how` | no | how the code does it (Developer lens) |
| `refs` | recommended | evidence |
| `switches` | no | keys from the top-level `switches` that affect this step |
| `risks` | no | what can go wrong at this step |
| `confidence` | no | `"inferred"` when you concluded it but could not see it in code |
| `ui` | no | the text the user sees for this step, exactly as the app shows it (a button label, a dialog title), in the language you found it — only when you read it from the resources or a translation file, never paraphrased |
| `detail` | no | id of another diagram in this document that zooms into this step or continues from it; the reader gets a button to open it. It points at a whole diagram, not at a node inside it |

`confidence: "inferred"` is accepted wherever a claim is made: flow nodes,
components, states, sequence messages, troubleshooting rows and findings. It
marks the whole item, so if one part is evidenced and another is not, say
which in `how` (or, for a row or a finding, in `cause` / `detail`). An edge, link or transition has no `confidence`; if
one is assumed, say so in its label ("probably, via background sync").

Steps that state a fact about the code (everything except `start`, `end` and
`unknown`) should carry `refs`; the build warns about each one that does not.

**Node types** — each has its own shape and colour:

| Type | Use for |
|---|---|
| `start` | where the flow begins (required, at least one) |
| `action` | something the **user** does |
| `process` | something the **system** does |
| `screen` | a screen or dialog being shown |
| `decision` | a branch — needs two or more labelled outgoing edges |
| `external` | another system: backend, REST API, third-party service |
| `store` | a database, document or file being read or written |
| `end` | a successful end |
| `error` | a failure, rejection or dead end |
| `unknown` | the path continues somewhere you could not read (a backend missing from the checkout); drawn dashed. Use it instead of inventing an ending |

**Edge fields:** `from`, `to`, optional `label`, optional `kind`:
`"main"` (the normal path, drawn thick — mark it, it powers the "Happy path"
view), `"optional"` (dotted, a side path) or `"error"` (red; applied
automatically to any edge into an `error` node).

`direction` is `TB` (default) or `LR`. The reader can flip it.

## 5. Diagram kind: `sequence`

Who calls whom, across the layers, in order. Messages are numbered
automatically and listed in a step table under the diagram.

```json
{
  "id": "seq", "kind": "sequence", "title": "Who calls whom",
  "participants": [
    { "id": "user", "label": "User", "type": "actor", "layer": "user" },
    { "id": "vm", "label": "Checkout logic", "tech": "CheckoutViewModel", "layer": "viewmodel" },
    { "id": "svc", "label": "Discount service", "tech": "DiscountService", "layer": "domain" }
  ],
  "steps": [
    { "from": "user", "to": "vm", "label": "Taps Apply" },
    { "alt": [
      { "when": "discounts enabled", "steps": [
        { "from": "vm", "to": "svc", "label": "Ask to apply the code", "tech": "applyDiscount()",
          "what": "Hands the code to the discount service.",
          "refs": ["domain/service/DiscountService.kt#applyDiscount"] },
        { "from": "svc", "to": "vm", "label": "New total", "kind": "reply" }
      ]},
      { "when": "discounts disabled", "steps": [ { "from": "vm", "to": "vm", "label": "Nothing happens" } ] }
    ]},
    { "opt":  { "when": "the code is valid", "steps": [] } },
    { "loop": { "when": "for each basket item", "steps": [] } },
    { "note": { "over": ["svc"], "text": "Items the code does not cover are skipped here" } }
  ]
}
```

- **Participant:** `id`, `label` (business name), optional `tech` (class name),
  `type: "actor"` for a person, and `layer`: `user`, `ui`, `viewmodel`,
  `domain`, `data`, `shared`, `device`, `backend`, `external`. Consecutive
  participants in the same layer are drawn in one coloured box, so **declare
  them in layer order** (user → ui → viewmodel → domain → data → backend →
  external).
- **Message:** `from`, `to`, `label`, optional `tech`, `what`, `how`, `refs`,
  and `kind`: `sync` (default), `reply` (dashed return), `async` (fire and
  continue), `fail` (the call fails).
- **Blocks:** `alt` (a list of branches, each with `when` and `steps`), `opt`
  and `loop` (one `when` and `steps`), `note` (`over` one or two participants,
  and `text`). Blocks nest.

## 6. Diagram kind: `components`

The classes involved, grouped by layer. Clickable like flow nodes.

```json
{
  "id": "components", "kind": "components", "title": "Building blocks",
  "components": [
    { "id": "fragment", "layer": "ui", "kind": "fragment", "label": "Checkout screen",
      "tech": "CheckoutScreen", "what": "Shows the basket and the code field.",
      "refs": ["view/CheckoutScreen.kt#CheckoutScreen"] },
    { "id": "pricing_api", "layer": "backend", "kind": "external", "label": "Pricing endpoint" }
  ],
  "links": [{ "from": "fragment", "to": "pricing_api", "label": "REST", "kind": "optional" }]
}
```

One component may stand for a family of small classes: name it for the role
("Pricing rules") and list the classes in `what`. Components take the same
`what`, `how`, `refs`, `risks` and `confidence` as flow nodes.

`direction` (`TB` by default) stacks the layers; avoid links between two
components of the same layer, which break the stack (the build warns).

`layer` is one of the standard layers above (or declare your own with
`"layers": [{ "id": "…", "title": "…" }]`). `kind` picks the shape:
`fragment`, `activity`, `screen`, `dialog` (screen shape); `store`, `database`
(cylinder); `external`, `api`, `backend` (double border); anything else
(`viewmodel`, `service`, `repository`, `model`, …) is a box.

## 7. Diagram kind: `state`

A lifecycle: a document's states, a screen mode.

```json
{
  "id": "order_state", "kind": "state", "title": "Order lifecycle", "direction": "LR",
  "states": [
    { "id": "draft", "label": "DRAFT", "initial": true, "color": "blue", "what": "Still being edited." },
    { "id": "placed", "label": "PLACED", "color": "green", "final": true, "what": "Submitted; sent to the backend." }
  ],
  "transitions": [
    { "from": "draft", "to": "placed", "label": "customer confirms", "tech": "placeOrder" }
  ]
}
```

| Field | On | Meaning |
|---|---|---|
| `id`, `label` | state | required; `label` is the name people use for the state |
| `initial`, `final` | state | where the lifecycle starts and may end; mark at least one `initial` |
| `color` | state | `green`, `blue`, `slate`, `amber`, `rose`, `violet` or `teal` |
| `tech`, `what`, `how`, `refs`, `risks` | state | same meaning as on a flow node; shown when the state is clicked |
| `from`, `to` | transition | state ids |
| `label`, `tech`, `refs` | transition | what triggers the change; `tech` is shown in the Developer lens |

A transition from a state to itself is allowed but draws as a long loop; if a
state has several, describe them in its `what` instead. `"direction": "LR"`
suits up to about four states; use `"TB"` for more.

## 8. Diagram kind: `raw`

An escape hatch for diagrams the structured kinds do not cover (a class
diagram of a data model, an ER diagram). You write Mermaid yourself, so this
is the one place a syntax error is possible — keep it simple and always run
`render-check`.

```json
{ "id": "model", "kind": "raw", "title": "Basket model",
  "mermaid": "classDiagram\n  class Basket {\n    +String currency\n  }" }
```

## 9. Lists

```json
"troubleshooting": [
  { "symptom": "Some items get no discount",
    "cause": "Items whose category the code does not cover are skipped without a message.",
    "check": "Compare the item categories with the categories the code is valid for.",
    "severity": "high",
    "nodes": ["match_items", "components:discount_service"],
    "refs": ["domain/service/DiscountService.kt#toDiscountedItems"] }
],
"findings": [
  { "title": "Log message contradicts its condition",
    "detail": "`isExpired` logs \"code expired\" when the code is **still valid**, and nothing when it has expired.",
    "severity": "low",
    "nodes": ["check_code"],
    "refs": ["domain/service/DiscountService.kt#isExpired"] }
],
"switches": [
  { "key": "DISCOUNTS_ENABLED", "effect": "Shows the discount code field.", "default": "off",
    "kind": "parameter", "scope": "region, then global",
    "nodes": ["check_enabled"],
    "refs": ["domain/repository/CheckoutSettingsRepository.kt#DISCOUNTS_ENABLED"] }
],
"data": [
  { "name": "Order record", "kind": "document", "direction": "write",
    "what": "`discount_code` records which code was applied.", "refs": [] }
],
"tests": [
  { "path": "app/checkout/src/test/…/DiscountServiceTest.kt", "covers": "which items a code applies to" }
],
"glossary": [{ "term": "Backorder", "meaning": "An order line that will be delivered later." }],
"openQuestions": ["Which pricing service is active in production cannot be seen from the code."]
```

- **`troubleshooting`** — `symptom` and `cause` required; `check` and `nodes`
  strongly recommended; `severity` is `high`, `medium` (default) or `low`.
  Add `"confidence": "inferred"` to a row you reasoned out but could not
  observe in code.
- **`findings`** — something in the code that looks wrong: `title` and `detail`
  required, `refs` expected, `severity` and `nodes` as above. Unlike a
  troubleshooting row it needs no user-visible symptom.
- **`nodes`** (in troubleshooting, findings and switches) names what "Show on
  diagram" highlights: the id of a flow node, a component or a state,
  optionally prefixed with its diagram id (`"flow:match_items"`). Ids must
  exist. Sequence participants cannot be highlighted.
- **`switches`** — `key` and `effect` required; `default`, `kind` (free text:
  `parameter`, `feature flag`, `master data`, `role`, `code constant`) and `scope` (where it is
  evaluated: `global`, `region`, `tenant`, `item`) are optional. Any key
  used in a node's `switches` must be listed here.
- **`data.direction`** — `read`, `write` or `read-write`. `kind` is free text
  (`document`, `rest`, `parameter`, `memory`, `file`). Add `boundary` when the
  data crosses one — `"leaves the device"`, `"leaves the company"` — it is
  shown as a marker, and people who care about data protection look for it.
- **Switch keys** — one parameter per row, written exactly as in the code, so
  a search for the key finds it. A family that always acts together may share
  a row under a pattern such as `ORDER_LIMIT_*`; then spell out every member in
  `effect`, so the search still finds each one.
- **`tests`** — each `path` must exist. Use `[]` when the test sources are in
  the checkout and nothing covers this path (the page then says so); leave the
  field out, with a caveat, when the checkout has no tests to look at. When
  one side has tests and the other is missing (backend present, Android
  absent), list what exists and add a caveat for the rest. If you listed a
  test by its name without reading it, say so in `covers`.

## 10. Narrative `sections`

Free-form blocks for explanation that is not a diagram. Mostly for module
X-rays; a feature X-ray may use one or two. Each has a `type`, a `title`, an
optional `subtitle`, and `placement`: `"top"` (before the diagrams) or
`"bottom"` (default). A section may carry `refs` of its own; they are listed
under it in the Developer lens.

| `type` | Content |
|---|---|
| `prose` | `text` — paragraphs |
| `callout` | `text`, `tone`: `info`, `warn`, `ok`, `danger` (the section `title` is its heading) |
| `cards` | `items`: `{ title, text, tone?, refs? }` — key concepts |
| `layers` | `items`: `{ name, text, layer?, refs? }` — an architecture stack |
| `steps` | `items`: `{ title, text, meta?, bullets?, refs? }` — a numbered journey; `meta` is a class name shown to developers |
| `table` | `columns`: `[…]`, `rows`: `[[…], …]` — every row as long as `columns` |
| `links` | `items`: `{ title, text, href? }` — links to other X-ray pages; leave `href` out for a feature that deserves an X-ray but has none yet, and it is shown as planned |

Card `tone` is `blue`, `green`, `amber`, `rose`, `violet` or `teal`.
