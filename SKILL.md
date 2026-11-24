---
name: xray
description: >-
  Produce a verified, interactive X-ray page of how a feature or a whole module
  works in this codebase: UML-style diagrams (flow, sequence, state,
  components), a symptom-to-code troubleshooting map, configuration switches and
  every step traced to file:line. Use ONLY when the user explicitly invokes it
  — `/xray ...` or `@xray ...` — or asks in so many words for an X-ray or an
  anatomy page. Do not use it for an ordinary "how does X work?" question;
  answer those in the conversation as usual.
---

# X-Ray

Turn *"how does checkout work?"* into a page a developer,
a product owner and a manager can all read: the flow as diagrams, each
step in plain language and traced to the code, and a table that leads from
"what I see is wrong" to "the step to look at".

Two things make the page worth having, and both shape how you work:

- **It must be true.** You describe steps as data and attach the file and
  symbol each comes from; a script checks every one against the working tree
  and refuses to build the page otherwise. You never write HTML or diagram
  syntax — the bundled viewer draws from your data.
- **It must be cheap.** Every file you read and every sentence you write is
  paid for again on each later step of the run. Work to the depth that was
  asked for and no further.

This is read-only analysis: never change production code, resources, build
files or tests. Write only inside the output folder — `xrayDocs/` at the
repository root unless the user names another.

## Where the page goes

The output folder mirrors the project, and every X-ray has a folder of its
own, so a page is found where its code is found:

```
xrayDocs/
  index.html             map of every page — the build rewrites it
  profile.md
  <module path>/         the module's folder, exactly as in the repository
    <name>/              one X-ray: <name>.xray.json, <name>.html, runs/
```

- **`<module path>`** is the folder, relative to the repository root, of the
  module, package, app or service the feature starts in — the one holding its
  build file (`build.gradle`, `package.json`, `project.json`, `pom.xml`,
  `*.csproj`, `go.mod` …): `android/checkout`, `web/libs/cart`,
  `services/billing`. Never a source folder inside it. A repository that is a
  single package has no such folders; use the feature's own source folder
  (`src/app/checkout`). Record it in `meta.modulePath`.
- **`<name>`** is the feature in two to four lower-case words joined by
  hyphens (`discount-code`). A module page is always named `anatomy`.

Below, `<x>` stands for `xrayDocs/<module path>/<name>/<name>`. Running the
same feature again updates its folder; it does not make a second one.

## When this runs

Only on an explicit request: `/xray ...`, `@xray ...`, or the user asking in so
many words for an X-ray or an anatomy page. An ordinary question is answered in
the conversation as usual and does not start this skill.

Once invoked, it always produces a page:

- With no depth word, use **quick** — the cheapest. The user writes
  "standard" or "deep" when they want more; never go deeper on your own.
- "anatomy", "overview" or "the whole module" means a module page.
- If the request names nothing to trace (a bare `/xray`), ask what feature or
  module is meant, then go.

## Depth — decide it first

The depth sets what you produce and how much you may spend. Take it from the
request; when it says nothing, use **quick**. Record it in `meta.depth`;
the build warns when the data exceeds its budget.

| | **quick** | **standard** | **deep** |
|---|---|---|---|
| Asked as | no qualifier (the default), "quick" | "standard", "with the call sequence", "more detail" | "deep", "full", "everything" |
| Diagrams | flow | flow + sequence, one more if it earns its place | flows with drill-downs, sequence, components, state |
| Flow nodes | up to 14 | up to 22 | up to 26 per flow |
| Troubleshooting / findings | 5 / 4 | 8 / 8 | 18 / 20 |
| Text per field, refs per item | 170 chars, 1 | 300 chars, 2 | 520 chars, 3 |
| Also | switches | switches, data, glossary | tests, caveats, everything |

A module overview ("anatomy", "the whole module") is `"kind": "module"`; the
page is headed **Anatomy** instead of X-Ray, and its lists may be twice as
long. A quick anatomy is the architecture diagram and the screen map;
standard and deep add the data flow, the lifecycle and the journey. Its recipe is in `references/craft.md` section 6.

## Workflow

**0. Start the meter.** First command of the run:

```bash
python3 <skill-dir>/scripts/xray.py usage start
```

**1. Scope.** Module, feature, depth, language (the user's; default English).
If two features fit the request, name them and ask once; if nobody can
answer, take the closest and say so in `meta.scope`. Look in
`xrayDocs/<module path>/` for X-rays of the same module: `xray.py outline
<file>` prints one in a few dozen lines, and steps already traced there need
no re-tracing.

**2. Read `references/quickref.md`, then the project profile.** The quick
reference is the whole format and the tracing method on one page. The profile
tells you how *this* project is laid out, so you do not rediscover it: use
`profile.md` in the output folder if there is one, otherwise the file in the
skill's `profiles/` that matches the repository (see `profiles/README.md`).
With no profile, discover the layout yourself and, before you finish, save
what you learned as `profile.md` in the output folder (under 40 lines: where
things live, the call chain, where switches are read) for the next run.
Open `schema.md`, `craft.md` or `tracing.md` only at the section that answers
a specific doubt.

**3. Trace, spending deliberately.**

- Search before you read. If a code-graph tool is available (for example
  `tokensave_context`, `tokensave_call_chain`, `tokensave_callees`,
  `tokensave_body`), follow the call chain with it instead of opening files.
  Try it once; if it returns nothing for this module, fall back to searching
  and do not retry it.
- Read functions, not files: list a large file's signatures, then read only
  the methods on the path. Issue independent searches and reads together in
  one step rather than one per step.
- Follow the path from trigger to outcome and stop when it closes. Do not
  explore neighbouring features.
- Keep terse evidence notes: `claim → path#symbol`. No evidence, no fact.
- Walk the path once more for how it breaks: items dropped silently, errors
  swallowed, behaviour gated by a parameter. Those become troubleshooting
  rows and findings — the reason people open the page.

**4. Write the data file once.** Compose the whole `<x>.xray.json` in a single
write, within the depth budget. Fix later problems with small edits, never by
rewriting the file.

**5. Build, fix, check.**

```bash
python3 <skill-dir>/scripts/xray.py build <x>.xray.json
python3 <skill-dir>/scripts/xray.py render-check <x>.html
```

A reference that fails means the claim or the file is wrong: go back to the
code. `--fix-refs` repairs a line number that drifted. Never delete a
reference or pass `--no-verify` to get a build through. Resolve warnings or
have a reason not to. Look at a diagram (`render-check --diagram <id>
--screenshot <png>`) only at deep depth or when the build warned about size
or layout.

**6. Stop the meter and report.**

```bash
python3 <skill-dir>/scripts/xray.py usage stop <x>.xray.json
```

It saves a run record in the X-ray's `runs/` and prints what the run spent. Report in
at most a dozen lines. **Begin with `X-ray page: <absolute path>`** and the
command that opens it (`open <path>` on macOS, `start <path>` on Windows,
`xdg-open <path>` on Linux), so there is no doubt that a page was produced and
where it is. Then the flow in three to five bullets, the findings, the open
questions, the verification result, and **the token line exactly as
printed**.

## Updating an existing X-ray

Regenerating costs as much as the first time; updating costs a fraction.

```bash
python3 <skill-dir>/scripts/xray.py check <x>.html     # one page
python3 <skill-dir>/scripts/xray.py check xrayDocs     # every page
```

It lists the cited files that changed and the steps that cite them. Re-read
only those functions, edit those steps in the data file, rebuild.

## Honesty

- A step you concluded but did not see in code gets `"confidence":
  "inferred"`. What you could not determine goes in `openQuestions`; what the
  checkout did not contain (resources, backend, tests) goes in `caveats`.
- Where a path leaves the code you can read, end it with an `unknown` node
  instead of drawing an ending you did not see.
- Something in the code that looks wrong is a `findings` entry, with its
  reference, even when no user would notice yet.
- Reference symbols must be text that is really in the file. `tech` names are
  checked loosely, so getting them right is on you.

## Files

| Path | Use |
|---|---|
| `references/quickref.md` | read every run |
| `references/schema.md` | every field, by section — on demand |
| `references/craft.md` | readable diagrams, two audiences, module recipe — on demand |
| `references/tracing.md` | the tracing method in detail — on demand |
| `profiles/<project>.md` | a project's layout and conventions — read the one that matches |
| `examples/template.xray.json` | a full skeleton, if you want one to copy |
| `scripts/xray.py` | `usage start/stop`, `build`, `check`, `outline`, `render-check`, `runs`, `index` |
