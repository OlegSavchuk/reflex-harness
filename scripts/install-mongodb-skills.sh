#!/usr/bin/env bash
# Installs the official MongoDB Agent Skills into .claude/skills (project scope, gitignored).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
git clone --depth 1 https://github.com/mongodb/agent-skills.git "$TMP/agent-skills"
mkdir -p "$ROOT/.claude/skills"
for d in "$TMP"/agent-skills/skills/*/; do
  name="$(basename "$d")"
  [ "$name" = "mongodb-atlas-stream-processing" ] && continue
  rm -rf "$ROOT/.claude/skills/$name"
  cp -R "$d" "$ROOT/.claude/skills/"
done
cp "$TMP/agent-skills/LICENSE" "$ROOT/.claude/skills/LICENSE-mongodb-agent-skills"
( cd "$TMP/agent-skills" && git log -1 --format='mongodb/agent-skills @ %h (%cd)' ) > "$ROOT/.claude/skills/SOURCE.txt"
rm -rf "$TMP"
echo "Installed: $(ls "$ROOT/.claude/skills" | grep ^mongodb | tr '\n' ' ')"
