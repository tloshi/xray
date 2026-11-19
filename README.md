# Feature X-Ray

Ask how something works; get a page you can trust.

Feature X-Ray is an agent skill that reads the code and produces one
self-contained HTML page per feature or module: UML-style diagrams, a
plain-language explanation of every step, a symptom-to-code troubleshooting
table, and the configuration switches that change the behaviour. Every step is
traced to `file:line`, and a script verifies each reference against the
working tree before the page is written.

## What you get

| | |
|---|---|
| **Diagrams** | flow (with decisions and error exits), sequence (who calls whom), components (by layer), state (lifecycles) |
| **Two lenses** | *Business* — plain language. *Developer* — class and method names, code references |
| **Click a step** | what it does, how, what can go wrong there, which switches affect it, where it is in the code |
| **Troubleshooting** | start from a symptom; "Show on diagram" highlights the steps to inspect |
| **Code findings** | defects noticed while tracing — an inverted condition, a swallowed error — each with its reference |
| **Limits of this analysis** | what the checkout did not contain, stated at the top instead of hidden |
| **Diagram options** | happy-path / problems / decisions focus, layout direction, step-by-step walkthrough, legend filter, search, PNG and SVG export, full-screen, dark and light theme |
| **For tickets** | "Copy for ticket" on any step gives a precise reference a developer can act on; "Copy link to step" deep-links to it |
| **Trust** | references verified at build time; the page shows the commit it was built from; `check` reports when the cited code has changed |

## Install

For yourself, in every project (works for Claude Code and OpenCode, which both
read `~/.claude/skills/`):

```bash
git clone https://github.com/tloshi/feature-xray.git ~/.claude/skills/feature-xray
```

Update later with `git -C ~/.claude/skills/feature-xray pull`.

For a whole team, put it in the project so everyone gets it with the code:

```bash
git clone https://github.com/tloshi/feature-xray.git && ./feature-xray/install.sh --project /path/to/your/repo
```

That copies the skill to `<your repo>/.claude/skills/feature-xray`; commit it
there. `./install.sh --link` symlinks instead of copying, so a `git pull` in
the clone updates the installed skill. On Windows, clone into
`%USERPROFILE%\.claude\skills\feature-xray`.

Requirements: Python 3.9+ (standard library only). Chrome, Edge or Chromium is
optional and enables the render check. Open a new session after installing —
skills are loaded when a session starts.

## Use

Just ask. For example:

- *How does applying a discount code work in checkout? Some items get no discount — show me where it can break.*
- *I need a flow of the refund process for a meeting with the product owners.*
- *Make an overview of the whole checkout module for a new colleague.*
- *… in German* / *… auf Deutsch* — the page and the viewer follow the language you ask for (English, German and Albanian viewer labels are built in).

Pages are written to `tempDocs/xray/` unless you name another folder.

## Commands

```bash
python3 scripts/xray.py build tempDocs/xray/<name>.xray.json          # validate, verify references, write the page
python3 scripts/xray.py build tempDocs/xray/<name>.xray.json --fix-refs   # snap drifted line numbers to their symbol
python3 scripts/xray.py render-check tempDocs/xray/<name>.html        # confirm every diagram draws (headless Chrome)
python3 scripts/xray.py check tempDocs/xray/<name>.html               # has the cited code changed? exits 2 if stale
```

`check` is CI-friendly: run it over the committed pages to learn which X-rays
need regenerating after a change.

## How the trust model works

The agent never writes HTML or diagram syntax. It writes a data file — steps,
edges, explanations — and attaches to each step the file and symbol it comes
from. `xray.py build` then:

1. validates the structure (edges point at real nodes, decisions really
   branch, every path ends, "show on diagram" targets exist);
2. opens every cited file and confirms the symbol is at the cited line;
3. refuses to write the page if anything fails.

A reference that was guessed or has drifted is a build error, not a page.
Steps the agent concluded but could not see in code are marked *inferred* and
drawn dashed; a path that leaves the code it could read ends in a *Not traced*
node; what it could not determine is listed under *Open questions*.

The build also lints for readability: labels that read like code, flows too
large to follow, a feature flow with no failure exits, class names that do not
occur in the cited files, references that could mean two overloads.

## Depth and cost

Every request has a depth, and the depth is a budget the build checks.

| Depth | You get | Ask for it with |
|---|---|---|
| **quick** | the flow, a few troubleshooting rows, the switches | "quick", "just the flow" |
| **standard** (default) | flow + call sequence, troubleshooting, findings, switches, data | no qualifier |
| **deep** | drill-down flows, components, state, tests, everything | "deep", "full", "where exactly can it break" |

Measured on a large Android codebase with the same model (first pass of each run):

| Run | Output tokens | Cached input | Model calls | Minutes |
|---|---|---|---|---|
| v1.0, unbudgeted — feature A | 131k | 14.7M | 54 | 20 |
| v1.0, unbudgeted — module overview | 136k | 20.0M | 53 | 20 |
| v1.1, standard — feature B (a larger one) | 45k | 3.2M | 23 | 7 |

Three habits keep it cheap:

- **Start a fresh session.** Every model call re-reads the whole conversation;
  at the end of a long session that alone can cost more than the X-ray.
- **Ask for the depth you need.** Deep is several times the price of quick.
- **Update, do not regenerate.** `xray.py check` names the steps whose code
  changed; re-tracing only those costs a fraction of a new run.

## Measuring and comparing runs

Each run brackets itself with `usage start` and `usage stop`. The stop writes
a run record — `runs/<timestamp>-<name>.run.json` next to the page — with the
tokens by kind, model calls, what was read, the model, the commit, the depth
and the size of the result. The page footer shows the same numbers.

```bash
python3 scripts/xray.py runs tempDocs/xray          # table of all runs
python3 scripts/xray.py runs tempDocs/xray --json   # the full records
python3 scripts/xray.py runs tempDocs/xray --html tempDocs/xray/runs.html   # an overview page with links
```

Set `XRAY_PRICES="in=…,out=…,cache_read=…,cache_write=…"` (per million tokens)
to have each record carry a cost in your own prices.

Token counts are read from the session transcript. That is tested with Claude
Code; a reader for OpenCode's storage is included but not yet verified against
a real installation. Where usage cannot be read, the record is still written,
with the tokens marked as not measured.

## Other projects, other models

**Any project.** The viewer, the verifier and the format know nothing about
any one codebase. What is project-specific lives in a profile: a short file saying where
things are and how a call travels. See `profiles/README.md`. In
a repository without one the first run discovers the layout and saves `profile.md`
in the output folder; later runs start from it. Reference checking recognises
declarations in Kotlin, Java, TypeScript and Python, and falls back to plain
text matching for anything else.

**Any model.** The skill is Markdown and Python; the tool that runs it picks
the model. In OpenCode, switch with `/models`, set a default in
`opencode.json`, or pin a model to an agent with `model: provider/model` in
`.opencode/agents/<name>.md` — Anthropic, OpenAI and Google models are all
available there. Claude Code runs Claude models. So far the skill has been
exercised with Claude only: the verifier stops invented references whatever
the model, but depth of analysis and cost will differ, and `xray.py runs` is
the way to compare them — every record names its model.

## Offline use

By default the page loads Mermaid from a CDN. To make pages fully
self-contained, put `mermaid.min.js` (v11) in `assets/vendor/`; the build
embeds it automatically.

## Layout

```
feature-xray/
├── SKILL.md            the workflow the agent follows
├── references/         tracing guide, data format, craft guide
├── examples/           a skeleton to copy and a complete real X-ray to learn from
├── scripts/xray.py     build · check · render-check
├── assets/             the viewer (HTML, CSS, JS) — shared by every page
└── evals/              test prompts for the skill itself
```
