#!/usr/bin/env bash
# Installs the security-audit skill into ~/.claude/skills/
# Usage: ./install.sh          copy (default)
#        ./install.sh --link   symlink, so git pull updates the skill
set -euo pipefail

src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/security-audit"
skills_dir="$HOME/.claude/skills"
target="$skills_dir/security-audit"

[ -d "$src" ] || { echo "security-audit/ not found next to this script. Run it from the repo root." >&2; exit 1; }

mkdir -p "$skills_dir"
[ -e "$target" ] && { echo "Removing existing $target"; rm -rf "$target"; }

if [ "${1:-}" = "--link" ]; then
  ln -s "$src" "$target"
  echo "Linked $target -> $src"
else
  cp -r "$src" "$target"
  echo "Copied skill to $target"
fi

echo
echo "Installed. Restart Claude Code, then run: /security-audit"
