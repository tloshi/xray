# Changelog

What each version of the skill changed. The version is `SKILL_VERSION` in
`scripts/xray.py`; `xray.py --version` prints it, every page shows it in its
footer and every run record stores it.

## 1.4 — 2026-11-24

- Walk through can play by itself: a play/pause button and a speed control
  (1×, 2×, 0.5×) in the step bar, space to toggle. Each step stays for its
  reading time, the view glides to it and the arrow leading into it is
  animated. Stepping by hand or touching the diagram pauses it; it stops at
  the last step. Motion is off for readers who ask for reduced motion.

## 1.3 — 2026-11-24

- `xray.py update` (or `/xray update`) moves the installed skill to the latest
  version; `update --check` only reports whether one exists. It contacts the
  git remote and runs only when asked.
- Every page states the version it was built with.
- Versions are tagged in the repository (`v1.2`, `v1.3`, …), so a copied
  installation can also tell whether it is the latest.

## 1.2 — 2026-11-24

- The output folder mirrors the project: `xrayDocs/<module path>/<name>/`
  holds one X-ray — its page, its data and its run records.
  `meta.modulePath` names the module's folder and the build checks it.
- `xrayDocs/index.html` maps every page by area and module; each build
  rewrites it and each page links back to it.
- `check` accepts a folder and reports every page under it.
- Pages from 1.1 keep working; the README explains how to file them.

## 1.1 — 2026-11-19

First published version.

- Three depths with budgets the build checks; `quick` is the default.
- Token accounting: `usage start` / `usage stop` write a run record per run;
  `runs` compares them.
- Staleness: a page records the commit and a fingerprint of each cited file;
  `check` names the steps whose code changed.
- Runs only on an explicit `/xray …`; pages go to `xrayDocs/`.
