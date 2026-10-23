#!/usr/bin/env bash
# Make the 11 APtrade skills available in every project, for Claude Code, Codex and Grok.
# It links (not copies) the skills, so `git pull` in this repo updates them everywhere.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
for dir in "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.grok/skills"; do
  mkdir -p "$dir"
  for skill in "$REPO"/skills/aptrade-*; do
    ln -sfn "$skill" "$dir/$(basename "$skill")"
  done
  echo "linked the APtrade skills into $dir"
done
echo "Restart Claude Code, Codex or Grok to see them. Remove with: rm ~/.{claude,agents,grok}/skills/aptrade-*"
