#!/bin/bash
# Maakt de CCR (Claude Code Remote) Stop hook niet-blokkerend
# (exit 2 -> exit 1), zodat Claude niet gedwongen wordt te committen/pushen
# (zie CLAUDE.md: geen commit/push zonder expliciete toestemming). Alleen in
# Claude Code on the web.
#
# Aangeroepen vanuit .claude/settings.json (SessionStart). Daar staat geen
# "matcher", dus deze hook draait bij alle vier de bronnen. Mogelijke waarden
# voor "matcher" (combineerbaar als regex, bijv. "startup|resume"):
#   startup  - nieuwe sessie
#   resume   - hervatte sessie (--resume, --continue, /resume)
#   clear    - na /clear
#   compact  - na (auto-)compact van de context

target=/root/.claude/stop-hook-git-check.sh

[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
[ -f "$target" ] || exit 0

sed -i 's/exit 2/exit 1/' "$target"
