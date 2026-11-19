# Project profiles

A profile tells the skill how one codebase is laid out, so a run does not
spend tokens rediscovering it. Keep it under 40 lines.

The skill looks for `profile.md` in the output folder first (default
`tempDocs/xray/profile.md` in the repository), then for a file here whose name
matches the repository. With no profile, the first run discovers the layout
and writes `profile.md` to the output folder.

## What to put in one

```markdown
# Project profile: <name>

| Area | What lives there |
|---|---|
| `app/<module>/` | one module per business process |
| `shared/` | models and helpers used by every module |
| `backend/<service>/` | backend services |

- **Call chain:** screen -> view model -> service -> repository -> database / REST -> backend.
- **Dependency injection:** how a class gets its collaborators, so callers can be found.
- **Navigation:** where screen transitions are declared.
- **Switches:** where parameters and feature flags are read, and their naming pattern.
- **Storage:** which stores exist and how data reaches the backend.
- **Tests:** where they live and how they are named.
```
