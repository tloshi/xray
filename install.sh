#!/usr/bin/env bash
# Installs the X-Ray skill.
#
#   ./install.sh                  for you, in every project   (~/.claude/skills/xray)
#   ./install.sh --project DIR    for everyone working in DIR (DIR/.claude/skills/xray)
#   ./install.sh --link           symlink instead of copy, so `git pull` here updates the install
#
# Claude Code and OpenCode both discover skills in .claude/skills/.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
target="$HOME/.claude/skills/xray"
link=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project) target="${2:?--project needs a directory}/.claude/skills/xray"; shift 2 ;;
    --link) link=1; shift ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

command -v python3 >/dev/null || { echo "python3 is required (3.9 or newer)" >&2; exit 1; }
mkdir -p "$(dirname "$target")"

if [ "$link" = 1 ]; then
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "$target exists and is not a link; move it away first" >&2
    exit 1
  fi
  ln -sfn "$here" "$target"
else
  mkdir -p "$target"
  for item in SKILL.md README.md references scripts assets examples profiles; do
    cp -R "$here/$item" "$target/"
  done
fi

python3 "$target/scripts/xray.py" --help >/dev/null
echo "X-Ray installed at $target"
echo "Open a new session and type, for example: /xray how does <feature> work in <module>?"
