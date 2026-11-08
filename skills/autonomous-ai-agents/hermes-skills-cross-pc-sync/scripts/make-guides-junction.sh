#!/usr/bin/env bash
# Recreate the guides junction on a second Windows PC (Plan A2).
# A junction is NOT carried by git — it must be created on EACH machine after clone.
# Requires NO admin / NO Developer Mode. Works cross-drive (C: -> G:).
#
# Usage: edit REPO_GUIDES and LINK to match this machine, then run in git-bash.
set -euo pipefail

# Absolute path to the cloned repo's guides folder (native Windows form, fwd slashes ok):
REPO_GUIDES='G:/_My_Programming/HERMES-AGENT/guides'
# Where the junction should appear (the path the skill+memory expect):
LINK="$HOME/hermes-guides"

# mklink needs backslashes; convert.
REPO_GUIDES_WIN=$(printf '%s' "$REPO_GUIDES" | sed 's#/#\\#g')
LINK_WIN=$(printf '%s' "$LINK" | sed 's#/#\\#g')

if [ -e "$LINK" ]; then
  echo "Path already exists: $LINK  (remove or rename it first if it's not the junction)"
  ls -la "$LINK"
  exit 1
fi

cmd //c "mklink /J \"$LINK_WIN\" \"$REPO_GUIDES_WIN\""
echo "--- verify ---"
ls -la "$LINK"
# Sanity: read a known guide through the junction.
[ -f "$LINK/Guide-to-Hermes.md" ] && echo "OK: Guide-to-Hermes.md reachable via junction." \
  || echo "NOTE: Guide-to-Hermes.md not found under junction — check REPO_GUIDES path."
