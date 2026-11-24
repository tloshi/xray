"""Updates the skill in place from the repository it was cloned from.

    xray.py update --check     is there a newer version? changes nothing
    xray.py update             fetch it and move this clone forward

This is the one command that talks to the network, and it runs only when
asked. It fast-forwards and does nothing else: local changes or local commits
stop it, so an update never overwrites anybody's work. A skill that was
installed as a copy has no history to move forward and is told how to update.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Callable

SKILL_DIR = Path(__file__).resolve().parent.parent
# Where released versions are tagged; XRAY_REPOSITORY points a copy at an internal mirror instead.
REPOSITORY = os.environ.get("XRAY_REPOSITORY") or "https://github.com/tloshi/xray.git"
VERSION_RE = re.compile(r'^SKILL_VERSION\s*=\s*"([^"]+)"', re.M)
TAG_RE = re.compile(r"refs/tags/v(\d+(?:\.\d+)*)$")
UPSTREAM = "@{u}"
GIT_TIMEOUT_SECONDS = 90
MAX_LISTED = 12
EXIT_OK, EXIT_FAILED = 0, 1


def _git(*args: str) -> tuple[bool, str]:
    """Runs git in the skill folder; returns (succeeded, output or error text)."""
    try:
        done = subprocess.run(["git", "-C", str(SKILL_DIR), *args], capture_output=True, text=True,
                              timeout=GIT_TIMEOUT_SECONDS, check=False)
    except FileNotFoundError:
        return False, "git is not installed"
    except subprocess.TimeoutExpired:
        return False, "git did not answer in time"
    return done.returncode == 0, (done.stdout.strip() if done.returncode == 0 else (done.stderr.strip() or done.stdout.strip()))


def _count(revisions: str) -> int:
    ok, out = _git("rev-list", "--count", revisions)
    return int(out) if ok and out.isdigit() else 0


def _is_own_clone() -> bool:
    """True when the skill folder is itself a git clone, not a copy that sits inside some other repository."""
    ok, top = _git("rev-parse", "--show-toplevel")
    return ok and Path(top).resolve() == SKILL_DIR


def _number(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def _latest_release() -> tuple[str | None, str]:
    """The highest released version tag in the repository, or (None, why it could not be read)."""
    ok, out = _git("ls-remote", "--tags", "--refs", REPOSITORY)
    if not ok:
        return None, _last_line(out)
    versions = [m.group(1) for m in (TAG_RE.search(line) for line in out.splitlines()) if m]
    return (max(versions, key=_number), "") if versions else (None, "no version has been tagged yet")


def _report_copy(installed: str, say: Callable[[str], None]) -> int:
    """A copy cannot move itself forward, but it can still say whether a newer version exists."""
    latest, problem = _latest_release()
    if latest is None:
        say(f"xray {installed} at {SKILL_DIR} is a copy. The latest version could not be looked up: {problem}")
        return EXIT_FAILED
    if _number(latest) <= _number(installed):
        say(f"xray {installed} is the latest released version.")
        return EXIT_OK
    say(f"xray {installed} is installed; {latest} is available.")
    say(f"The skill at {SKILL_DIR} is a copy, not a git clone, so it cannot update itself.")
    say("Update the clone it was installed from, then install again:")
    say("  git pull && ./install.sh        (add --project <repo> if that is how it was installed)")
    return EXIT_OK


def _last_line(text: str) -> str:
    """The line of git's answer that says what went wrong."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    stated = [line for line in lines if line.startswith(("fatal:", "error:"))]
    return (stated or lines or ["no details given"])[0]


def run(installed: str, check_only: bool, say: Callable[[str], None]) -> int:
    if not _is_own_clone():
        return _report_copy(installed, say)
    ok, out = _git("fetch", "--quiet")
    if not ok:
        say(f"Could not reach the repository: {_last_line(out)}")
        return EXIT_FAILED
    ok, upstream = _git("rev-parse", "--abbrev-ref", UPSTREAM)
    if not ok:
        say(f"The clone at {SKILL_DIR} follows no remote branch; update it with git by hand.")
        return EXIT_FAILED

    behind, ahead = _count(f"HEAD..{UPSTREAM}"), _count(f"{UPSTREAM}..HEAD")
    if behind == 0:
        note = f" ({ahead} local commit(s) not pushed)" if ahead else ""
        say(f"xray {installed} is up to date with {upstream}{note}.")
        return EXIT_OK

    found = VERSION_RE.search(_git("show", f"{UPSTREAM}:scripts/xray.py")[1])
    latest = found.group(1) if found else installed
    what = f"{latest} is available" if latest != installed else "newer changes are available"
    say(f"xray {installed} is installed; {what} ({behind} change(s) behind {upstream}):")
    for subject in _git("log", "--format=%s", f"-{MAX_LISTED}", f"HEAD..{UPSTREAM}")[1].splitlines():
        say(f"  - {subject}")
    if behind > MAX_LISTED:
        say(f"  … and {behind - MAX_LISTED} more")
    if check_only:
        say("Get it with: xray.py update")
        return EXIT_OK

    if ahead:
        say(f"Not updated: the clone at {SKILL_DIR} has {ahead} local commit(s). Merge or rebase it by hand.")
        return EXIT_FAILED
    if _git("status", "--porcelain", "--untracked-files=no")[1]:
        say(f"Not updated: files in {SKILL_DIR} were changed locally. Commit, stash or discard them first.")
        return EXIT_FAILED
    ok, out = _git("merge", "--ff-only", "--quiet", UPSTREAM)
    if not ok:
        say(f"Update failed: {_last_line(out)}")
        return EXIT_FAILED
    say(f"Updated to xray {latest}. Open a new session so the new instructions are loaded.")
    return EXIT_OK
