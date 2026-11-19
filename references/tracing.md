# Tracing a feature

How to find where a behaviour starts, follow it to where it ends, and collect
the evidence an X-ray needs. The quick reference has the short version; open
this at the section you need. Project-specific layout belongs in a profile
(`profiles/README.md`).

## Contents

1. Orient yourself
2. Find the entry point
3. Follow the chain, layer by layer
4. Cross the boundaries
5. Find the switches
6. Hunt for failure modes
7. Find the tests
8. Working economically

## 1. Orient yourself

Do not assume paths — discover them. Glob for the module or feature name and
look at what is actually there. Notice what is *missing* too: a checkout may
lack resources, tests or the backend. Each gap limits what you can claim, so
record it in `caveats` rather than working around it silently. The same goes
for a symbol that is used but defined nowhere in the tree: note it and move on.

Shared helpers are part of the path. When the code you follow calls a generic
helper — a list merge, a string or number utility — open it. The behaviour
that surprises people is often inside the helper, not at the call.

## 2. Find the entry point

Pick whichever handle the request gives you.

- **A UI label.** Search the string or translation resources for the text,
  take the resource name, then search for its use; that leads to the screen
  and the handler. If the resources are not in the checkout, start from the
  code and describe what the control does — do not present a paraphrase as
  the exact text on screen, and add a caveat.
- **A class or screen name.** Glob for it.
- **A parameter or flag.** Search for the key, find where it is read, then
  who calls that.
- **A navigation action.** Read where screen transitions are declared, and
  the code that triggers them.
- **An endpoint or a stored document.** Search the client or schema for it,
  then find the code that uses it.

When several things match the request, list them and ask which one is meant.

## 3. Follow the chain, layer by layer

Read each hop; do not infer a hop from a name. At every layer record what
happens, the branch conditions, and `file#symbol` for each.

- **Screen / view.** What the user does, which handler it calls, what it
  observes, which dialogs it can show, how it navigates. In a template-based
  UI, follow the event binding (`(click)="save()"`, `onClick={save}`) from the
  template to the handler.
- **Presentation logic** (view model, presenter, controller). Usually thin:
  it calls services and posts state or one-shot events. Note how errors reach
  the screen — or do not.
- **Business logic** (services, use cases). Where the rules are. Read every
  method on the path and every helper it calls: validations, thresholds,
  mappings, early returns, what is returned on each branch.
- **Data access** (repositories, clients). What is read or written, in which
  store, under which key or query, and what happens when nothing is found.

## 4. Cross the boundaries

A flow that stops at "calls the repository" hides exactly the part people ask
about. Follow it through.

- **Local storage.** Which store, which record or document type, which fields
  this feature sets, which state changes. If data reaches the backend by
  background sync, "saved" and "arrived" are different moments.
- **Network.** The endpoint, what is sent, and how failure surfaces.
- **Backend.** If the backend code is in the repository, find the handler for
  the endpoint and trace far enough to name the external systems it calls and
  the ways it can fail; give those participants `layer: "backend"`. If it is
  not there, end the path with a node of type `unknown` and add a caveat. Do
  not draw an ending you could not read.
- **Devices and other apps.** Scanners, printers, another device working on
  the same record.

## 5. Find the switches

A "bug" is often a setting. For every branch on the path ask what decides it:
a configuration parameter, a feature flag, master data, a role, or a constant
in the code. For each, record the key, what it changes, the default when it
is missing, and the scope it is evaluated at.

## 6. Hunt for failure modes

Walk the path a second time looking only for ways it goes wrong.

- **Silent drops** — `filter`, `mapNotNull`, `firstOrNull`, `orEmpty`,
  `?: return`, `takeIf`: something disappears and nobody is told.
- **Collapsing duplicates** — `associateBy`, `distinctBy`, `toMap`, `find`:
  two items with the same key become one.
- **Parse to null** — `toBigDecimalOrNull`, `toIntOrNull`, date parsing with a
  fallback: a value in an unexpected format quietly becomes empty.
- **Unwrapped results** — a failure with a reason is turned into nothing.
- **Swallowed errors** — `catch` blocks or error callbacks that only log
  (`error: console.error`), a default returned on failure.
- **Unguarded lookups** — `.find(...)`, `[0]`, a map lookup used without
  checking that something was found.
- **Guards** — early returns and validations that block the flow; what does
  the user see when one fires? Nothing at all is a finding.
- **Mismatched gates** — the UI allows something the business check rejects,
  or the two check different fields.
- **Nobody listening** — a loading state with no error observer: the app
  waits forever.
- **Boundaries** — offline, a slow or failed call, sync not yet run, a record
  edited elsewhere, a stale local copy.
- **State left behind** — a flag set and never cleared, a retry that runs the
  step twice.

Turn each into a troubleshooting row and attach the risk to the diagram step
where it happens. Code that is simply wrong — an inverted condition, a log
message that contradicts its branch — goes into `findings`, with its
reference, even when no user would notice yet.

## 7. Find the tests

Look for tests of every class on the path. List the ones that exercise this
behaviour and say what each covers. If the test sources are in the checkout
and nothing covers the path, record `"tests": []`. If the checkout has no
tests at all, leave `tests` out and add a caveat: absent tests and unavailable
tests are different statements.

## 8. Working economically

- **Search before reading.** If a code-graph tool is available, ask it for the
  call chain and for function bodies instead of opening files. Otherwise grep
  for the symbol, list the signatures of a large file, and read only the
  methods on the path.
- **Restrict searches** to source files and leave out build output and test
  fixtures. Quote glob patterns in shell commands.
- **Batch** independent searches and reads into one step.
- **Keep evidence notes** as you go: `claim -> path#symbol`. Writing the data
  file from that list is quick and the references verify.
- **In module mode**, read fully only the entry points, the screens, the
  presentation logic and the services that load, save and complete the
  module's main object; skim the rest by signature.
