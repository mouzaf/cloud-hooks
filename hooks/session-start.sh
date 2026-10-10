#!/bin/bash
# Zet de CCR (Claude Code Remote) Stop hook stil: elke niet-nul `exit` wordt
# `exit 0`. Alleen in Claude Code on the web.
#
# Waarom stil en niet alleen niet-blokkerend: met `exit 2` dwingt de hook
# Claude te committen/pushen (zie CLAUDE.md: geen commit/push zonder
# expliciete toestemming). Met `exit 1` blokkeert hij niet meer, maar toont de
# app zijn stderr als hook-fout, een beurt te laat en naast ons eigen label.
# Het git-label komt nu alleen van hooks.py, dat een ongewijzigde kopie van
# het script draait (die moet nog wel met een niet-nul code eindigen).
#
# Aangeroepen vanuit ~/.claude/settings.json (SessionStart, gezet door
# install.sh). Daar staat geen "matcher", dus deze hook draait bij alle vier
# de bronnen. Mogelijke waarden voor "matcher" (combineerbaar als regex,
# bijv. "startup|resume"):
#   startup  - nieuwe sessie
#   resume   - hervatte sessie (--resume, --continue, /resume)
#   clear    - na /clear
#   compact  - na (auto-)compact van de context
# Bij clear en compact is het script al gepatcht; de markeerregel voorkomt dat
# de kopie dan door de gepatchte versie wordt overschreven. Herschrijft de
# harness het script (bv. bij resume), dan ontbreekt de markering en wordt
# de kopie ververst.

# Overschrijfbaar voor test/test_hooks.py.
target=${CLOUD_HOOKS_GIT_CHECK:-/root/.claude/stop-hook-git-check.sh}
copy=${CLOUD_HOOKS_GIT_CHECK_COPY:-/root/.claude/stop-hook-git-check.orig.sh}
marker='# cloud-hooks: alle exits op 0 gezet door session-start.sh'

[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
[ -f "$target" ] || exit 0
grep -qxF "$marker" "$target" && exit 0

cp "$target" "$copy"
sed -i -E 's/\bexit +[1-9][0-9]*\b/exit 0/g' "$target"
echo "$marker" >> "$target"
