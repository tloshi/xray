# Craft: making an X-ray people actually use

The build checks that your X-ray is *true*. This file is about making it
*useful*: readable at a glance, clear to someone who has never opened the
code, and pointed at the questions people really ask.

## Contents

1. Write for two readers at once
2. Diagrams that stay readable
3. The sequence diagram
4. Troubleshooting rows that find problems
5. Switches, data, glossary
6. Module mode: the anatomy recipe
7. Before you build: a self-check

## 1. Write for two readers at once

Every step has two faces, and the page lets the reader choose which to see.

| Field | Reader | Write it as |
|---|---|---|
| `label` | everyone | what happens, in the words a user or a product owner would use |
| `what` | business | one or two sentences: what this step means and why it exists |
| `tech` | developer | the real identifier — `Class.method` |
| `how` | developer | what the code does: the condition, the mapping, the edge case |

The test for a `label`: could someone who has never seen the code say it out
loud in a meeting? If it contains a class name, a method name or camelCase, it
belongs in `tech`.

| Instead of | Write |
|---|---|
| `applyDiscount()` | Apply the discount code |
| `isDiscountEnabled == true?` | Are discount codes switched on? |
| `mapNotNull items` | Work out which items the code covers |
| `Post navigationEvent` | Open the order summary |

Name things the way the business does. Use the term from the UI and the
domain (order, invoice, credit note), explain it once in the
`glossary`, and then use the same word every time.

`meta.summary` is read by people who will read nothing else. Say what the
feature does, who uses it and when — no class names, no "this X-ray shows".

## 2. Diagrams that stay readable

A flow diagram is read by following lines with the eyes. It stops working
somewhere past 25 nodes. The rules below are for a feature flow; a module's
screen map is a different animal and follows section 6.

- **Aim for 12–22 nodes in a flow.** Even then a long chain will not fit a
  screen at a readable size — it is read by panning, or step by step with
  "Walk through" — but past that size it stops being followable at all. If the feature needs more, split it: a
  main flow, then a second flow for a sub-process ("Validation", "What happens
  on save"). Two clear diagrams beat one complete unreadable one. A long,
  mostly linear flow reads better with `"direction": "LR"`.
- **Group by phase.** Use `groups` with numbered titles in the order things
  happen: `1 · Entry`, `2 · Validation`, `3 · Applying the result`. Three to
  five groups, titles under about 30 characters (a phase box clips longer
  ones).
- **Mark the main path.** Give the edges of the normal, successful route
  `"kind": "main"`. They are drawn thick and power the "Happy path" view and
  the walkthrough order. One continuous main path from a `start` to an `end`.
- **Every decision is a question** with named answers: `Is the code valid?` →
  `Yes` / `No`. Not `Check code`. For more than two outcomes, name each case.
- **Every path ends.** Each branch should reach an `end`, an `error` or — where
  your view stops — an `unknown` node.
  A branch that just stops makes the reader wonder what happens next — and
  usually means you have not found out yet.
- **Show the failures.** A flow with no `error` nodes is a flow you have not
  finished tracing. The error exits are the reason people open this page.
- **Use the right node type.** `action` only for what the *user* does;
  `process` for what the system does; `external` for anything outside the app;
  `store` for reads and writes. The colours then tell the story by themselves:
  a reader sees at a glance where the user is involved and where the flow
  leaves the device.
- **Keep labels short** (under 60 characters; the build warns past that).
  Detail goes in `what` / `how`, where there is room and where it is
  searchable.
- **Order nodes the way the story goes.** List them roughly in the order
  things happen; the walkthrough follows the edges from `start`, main path
  first.
- **Things that happen in the background.** The main path is what the *user*
  goes through. When a step also triggers something in parallel — a list
  refresh after a save, a background sync — draw that as an `optional` edge
  from the step that causes it, labelled "in the background" or "afterwards",
  leading to its own ending. Do not thread it into the main path just to keep
  one line: the diagram would then claim an order the code does not have.
- **Where your view ends.** If the path leaves what you can read, finish that
  branch with an `unknown` node that says where it goes.
- **A failure the flow survives.** Not every failure is a dead end: a failed
  call may be turned into an empty result and the flow carries on as if
  nothing happened. Draw that with an edge of `"kind": "error"` (red) into a
  normal `process` node that says what the code falls back to ("Continues
  with an empty result — no message"), then continue from there. An `error`
  node would claim the flow stops, which is exactly what it does not do.
- **Follow one item.** When the question is "where do items get lost?" — rows
  dropped, entries missing, records filtered — add a second flow that
  follows a *single item* from where it is read to where it is shown, with one
  decision per filter and an `error` exit for each way it can vanish. Point to
  it from the step in the main flow with `"detail": "<that diagram's id>"`.
  This funnel is usually the diagram people came for.

## 3. The sequence diagram

The flow shows *what* happens; the sequence shows *who does it*. A developer
uses it to find which class to open.

- One participant per class that matters, in layer order: user, UI, ViewModel,
  domain services, repositories, then backend and external systems.
- Six to ten participants. Past that the diagram is too wide to follow, so
  merge: a store goes into the repository that owns it, and several small
  services that are always called together become one participant named for
  what they do ("Pricing rules"), with the real class named in the `tech` of
  each message. A device (printer, scanner) or a backend always keeps its own
  lifeline — the boundary is the point of the diagram.
- Show the boundary crossings explicitly — the REST call out and the reply
  back, the document write. Those are where time and failures hide.
- Use `alt` for a real branch, `opt` for a step that only sometimes happens,
  `loop` for per-item work, and a `note` for the one thing a reader must not
  miss ("uncovered items are skipped here").
- Give each message `refs` — the step table under the diagram turns into a
  clickable index into the code.

## 4. Troubleshooting rows that find problems

This table is what lets someone find a problem by looking at the page. A good
row starts from what a person can observe and ends at a place to look.

- **`symptom`** — what the *user* sees, in their words: "The Apply button
  is missing", "Some items get no discount", "The total is
  overwritten". Never the internal cause.
- **`cause`** — the mechanism, concretely. Name the condition, not the area.
- **`check`** — something a person can actually do: a parameter to look up, a
  field to compare, a log line or document field to inspect.
- **`nodes`** — the steps where it happens, so "Show on diagram" lights them
  up.
- **`severity`** — `high` when data is lost or wrong without anyone noticing;
  `medium` when the user is blocked but can see it; `low` for cosmetic or rare.

Five to ten rows is typical for a real feature; more is fine when each is a
distinct symptom. Rows are shown most severe first, so within a severity put
the likeliest cause first. The most valuable ones are the
*silent* failures — where the app does something reasonable-looking and wrong,
with no message. If you found none, you probably have not finished step 3 of
the workflow.

Attach the same insight to the diagram: put a short line in the `risks` of the
node where it happens, so someone clicking through the flow meets it there
too.

## 5. Switches, data, glossary

- **Switches** — anything that decides this behaviour and that someone will ask
  about changing: configuration parameters, feature flags, master data and
  roles when they gate the flow (an item attribute that makes an option
  disappear is a switch as far as support is concerned), and thresholds
  hard-coded in the code. Give a hard-coded one `"kind": "code constant"` and
  say in `effect` that changing it needs a release — "can we change the 15 %?"
  is the first thing a product owner asks. If the scope cannot be seen from the
  module, write that rather than guessing. State the effect as a consequence
  ("hides the code field"), the `default` when it is unset, its `kind`, and
  the `scope` it is read at. Link each to its `nodes`. Support and product owners
  read this table first.
- **Findings** — what looks wrong in the code itself. A troubleshooting row
  starts from something a user sees; a finding starts from the code and may
  have no visible symptom yet (an inverted condition, a log line that
  contradicts its branch, a retry that writes twice). Say plainly what the
  code does and why that looks unintended, and give the reference. Keep it
  factual — "verify before acting" is printed above the list.
- **Data** — what is read and written and where it ends up: document types and
  the fields this feature sets, REST endpoints, parameters. Say when data
  leaves the device.
- **Glossary** — every domain term and abbreviation a newcomer would stumble
  on. Short, concrete definitions.

## 6. Module mode: the anatomy recipe

A module X-ray answers "what is this module and how does it hang together?".
It is a map; the detail lives in feature X-rays. Set `"kind": "module"` and
build it from these parts, in this order:

1. **What it is** — `meta.summary`, then a `cards` section (placement `top`)
   with the three to five concepts everything else depends on.
2. **Diagrams**
   - `components` — the architecture: screens, ViewModels and state holders,
     the main services, repositories, stores and external systems, by layer.
     Up to about 25 boxes; let one box stand for a family of small classes,
     and draw only the links a newcomer needs. Link *between* layers, not
     within one: links inside a layer make the layer boxes stagger into a
     diagonal staircase. Give stores and external systems a layer of their own
     (declare it in `layers`) so the repository-to-store link crosses layers.
   - `flow` — the screen map: a `start` node ("User opens the app") leading
     to the first screen, then one `screen` node per screen, with every edge
     labelled by what triggers the navigation. A screen map is a network, not
     a story, so its rules differ from a feature flow: use **no `groups`**
     (phase boxes force a layout that tangles a cyclic graph), it needs **no
     `end` node**, and `main` marks the route most users take through the
     screens. A screen people go to and come back from (a search, a picker)
     can be one edge out, labelled with the round trip.
   - `flow` or `sequence` — where the data comes from and where it goes
     (sources → merge → what the user sees → what is saved → how it reaches
     the backend).
   - `state` — the lifecycle of the module's main document or object.
3. **How it is built** — a `layers` section: what each layer is responsible
   for *in this module*, with the classes that matter.
4. **The user journey** — a `steps` section: screen by screen, what the user
   does and what the module does in response (`meta` = the Fragment).
5. **Rules worth knowing** — `table` sections for validation rules, modes,
   business rules that surprise people.
6. **Switches** — the module's full parameter list in `switches`.
7. **Feature index** — a `links` section pointing at the feature X-rays that
   exist (relative `href` to their `.html`), plus items without `href` for
   the features that deserve one and do not have it yet.
8. `troubleshooting` for module-wide symptoms, `glossary`, `openQuestions`.

Keep each diagram to the level of "which box talks to which". When you want
to draw what happens *inside* a box, that is a feature X-ray.

## 7. Before you build: a self-check

For a feature X-ray (a module's screen map is exempt from the path rules):

- Can someone who has never seen the code read every `label` aloud?
- Is there one continuous `main` path from a `start` to an `end`?
- Does every decision ask a question, with every exit labelled?
- Does every branch end in an `end`, an `error` or an `unknown`?
- Does every factual step carry a `refs` entry with a `#symbol`?
- Are there troubleshooting rows for the silent failures, each linked to nodes?
- Is every parameter that changes the behaviour in `switches`?
- Does `openQuestions` list what you could not determine, and `caveats` what the checkout did not contain?
- Did you record anything that looked wrong in the code under `findings`?
- Did the flow cross the boundaries — storage, REST, backend — or stop at
  "calls the repository"?
