# X-Ray

Ask how something works; get a page you can trust.

X-Ray is an agent skill that reads the code and produces one
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
| **Diagram options** | happy-path / problems / decisions focus, layout direction, step-by-step walkthrough with auto-play, legend filter, search, PNG and SVG export, full-screen, dark and light theme |
| **For tickets** | "Copy for ticket" on any step gives a precise reference a developer can act on; "Copy link to step" deep-links to it |
| **Trust** | references verified at build time; the page shows the commit it was built from; `check` reports when the cited code has changed |

## Install

For yourself, in every project (works for Claude Code and OpenCode, which both
read `~/.claude/skills/`):

```bash
git clone https://github.com/tloshi/xray.git ~/.claude/skills/xray
```

For a whole team, put it in the project so everyone gets it with the code:

```bash
git clone https://github.com/tloshi/xray.git && ./xray/install.sh --project /path/to/your/repo
```

That copies the skill to `<your repo>/.claude/skills/xray`; commit it
there. `./install.sh --link` symlinks instead of copying, so a `git pull` in
the clone updates the installed skill. On Windows, clone into
`%USERPROFILE%\.claude\skills\xray`.

Requirements: Python 3.9+ (standard library only). Chrome, Edge or Chromium is
optional and enables the render check. Open a new session after installing —
skills are loaded when a session starts.

## Update

From the AI console, type `/xray update` (or `/xray version` to only look).
From a terminal:

```bash
python3 ~/.claude/skills/xray/scripts/xray.py update --check   # is there a newer version? changes nothing
python3 ~/.claude/skills/xray/scripts/xray.py update           # get it
```

It lists what changed and moves the installed skill forward. It only ever
fast-forwards: if files of the skill were edited locally it stops and says
so. It is the one command that contacts the network — the git remote the
skill was cloned from — and it runs only when you ask; a normal `/xray` run
never does.

This works when the skill is a git clone or linked to one. A copy cannot
update itself, and for a team it should not: the copy in the team's
repository is the version everybody uses, changed by a commit like any other
code.

How you update by hand depends on how you installed:

| Installed with | Update with |
|---|---|
| `git clone … ~/.claude/skills/xray` | `/xray update`, or `git -C ~/.claude/skills/xray pull` |
| `./install.sh --link` | `/xray update`, or `git pull` in the clone — the link already points at it |
| `./install.sh` (a copy) | `git pull` in the clone, then `./install.sh` again |
| `./install.sh --project <repo>` (a copy in the team's repository) | `git pull` in the clone, `./install.sh --project <repo>` again, then commit the changed `.claude/skills/xray` so everyone gets it with their next pull |

Then open a new session; a running one keeps the version it started with.
`python3 ~/.claude/skills/xray/scripts/xray.py --version` shows what is
installed, `update --check` whether it is the latest, and every page states
the version it was built with in its footer. [CHANGELOG.md](CHANGELOG.md)
lists what each version changed.

**Releasing a version** (maintainers): raise `SKILL_VERSION` in
`scripts/xray.py`, add the entry to `CHANGELOG.md`, commit, then
`git tag -a v<version> -m "xray <version>" && git push --follow-tags`. The tag is what a copied
installation is compared against.

**Coming from 1.1.** Pages used to sit side by side in `xrayDocs/`. They keep
working and are listed in the index under "Not filed under a module yet". To
file one where it now belongs, add `meta.modulePath` to its `.xray.json`, move
the data file, the page and its run records into
`xrayDocs/<module path>/<name>/`, and build it again; the build prints the
exact path when a file is in the wrong place. New pages are filed correctly
without any of this.

## Use

Type `/xray` followed by what you want to understand (`@xray` in OpenCode).
That always produces a page; a question without it gets a normal answer.

- `/xray how does login work?` — quick: just the flow, the cheapest (the default)
- `/xray standard: how does applying a discount code work in checkout?` — adds the call sequence, findings, data
- `/xray deep: where exactly can the refund process break?` — everything
- `/xray anatomy of the checkout module` — an overview page of a whole module

Add the language if you want one other than English ("in German"). English,
German and Albanian viewer labels are built in.

The reply always begins with `X-ray page:` and the path, so you know a page
was made and where it is.

## Where pages go

Pages are written to `xrayDocs/` at the root of the project unless you name
another folder. Inside, the folder mirrors the project — a page is found
where its code is found — and every X-ray has a folder of its own:

```
xrayDocs/
├── index.html                    map of every page, rewritten by each build
├── profile.md                    how this project is laid out (written on the first run)
├── android/checkout/             the module's folder, exactly as in the repository
│   ├── anatomy/                  the module overview
│   │   ├── anatomy.html
│   │   ├── anatomy.xray.json
│   │   └── runs/
│   └── discount-code/            one feature
│       ├── discount-code.html    the page — open this
│       ├── discount-code.xray.json   the data it was built from
│       └── runs/                 one record per run: tokens, model, commit
└── web/libs/cart/
    └── add-to-cart/ …
```

The module's folder is the one that holds its build file (`build.gradle`,
`package.json`, `project.json`, `pom.xml`, `*.csproj`, `go.mod` …), so the
same rule fits an Android module, a web app or library and a backend service.
The build checks it: a folder that does not exist stops the build, and a
source folder inside a module, or a page filed in the wrong place, is
reported with the path it should have.

Open `xrayDocs/index.html` to browse everything; each page links back to it.
Running a feature again updates its folder and adds a record under `runs/`.

## Commands

```bash
# <x> = xrayDocs/<module path>/<name>/<name>
python3 scripts/xray.py build <x>.xray.json              # validate, verify references, write the page and the index
python3 scripts/xray.py build <x>.xray.json --fix-refs   # snap drifted line numbers to their symbol
python3 scripts/xray.py render-check <x>.html            # confirm every diagram draws (headless Chrome)
python3 scripts/xray.py check <x>.html                   # has the cited code changed? exits 2 if stale
python3 scripts/xray.py check xrayDocs                   # the same for every page under a folder
python3 scripts/xray.py index xrayDocs                   # rewrite index.html by hand (after moving pages)
```

`check` is CI-friendly: `check xrayDocs` goes through every committed page,
prints one line for each that is still current and the affected steps for
each that is not, and exits 2 if any page is stale.

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
| **quick** (default) | the flow, a few troubleshooting rows, the switches | no qualifier |
| **standard** | flow + call sequence, troubleshooting, findings, switches, data | "standard" |
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
a run record — `runs/<timestamp>-<name>.run.json` in the X-ray's own folder — with the
tokens by kind, model calls, what was read, the model, the commit, the depth
and the size of the result. The page footer shows the same numbers.

```bash
python3 scripts/xray.py runs xrayDocs          # table of all runs
python3 scripts/xray.py runs xrayDocs --json   # the full records
python3 scripts/xray.py runs xrayDocs --html xrayDocs/runs.html   # an overview page with links
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
xray/
├── SKILL.md            the workflow the agent follows
├── references/         tracing guide, data format, craft guide
├── examples/           a skeleton to copy and a complete real X-ray to learn from
├── scripts/xray.py     build · check · index · render-check
├── assets/             the viewer (HTML, CSS, JS) — shared by every page
└── evals/              test prompts for the skill itself
```
