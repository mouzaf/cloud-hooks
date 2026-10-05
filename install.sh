#!/bin/bash
# Zet de cloud-hooks in ~/.claude/settings.json van de container.
#
# Bedoeld voor het setup-script van een cloud environment, na een clone van
# deze repo:
#     git clone --depth 1 https://github.com/mouzaf/cloud-hooks ~/.claude/cloud-hooks
#     ~/.claude/cloud-hooks/install.sh
#
# Gebruikersinstellingen, niet de .claude/settings.json van een repo: die
# laatste laadt niet in projecten met meerdere repo's (getest 2026-10-05).
# Nogmaals draaien is veilig: eerdere regels van deze repo worden vervangen,
# instellingen van anderen blijven staan.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="${HOME}/.claude/settings.json"

mkdir -p "$(dirname "$SETTINGS")"
python3 - "$HERE" "$SETTINGS" <<'EOF'
import json, sys
from pathlib import Path

here, settings = sys.argv[1], Path(sys.argv[2])
hooks_py = f'python3 "{here}/hooks/hooks.py"'


def entry(command, matcher=None):
    e = {'hooks': [{'type': 'command', 'command': command}]}
    if matcher:
        e['matcher'] = matcher
    return e


ours = {
    'SessionStart': [entry(f'"{here}/hooks/session-start.sh"')],
    'UserPromptSubmit': [entry(f'{hooks_py} user-prompt-submit')],
    'PreToolUse': [entry(f'{hooks_py} pre-reply', 'mcp__hearthbot__reply')],
    'Stop': [entry(f'{hooks_py} stop')],
}


def is_ours(e):
    return any(here in h.get('command', '') for h in e.get('hooks', []))


s = json.loads(settings.read_text()) if settings.exists() else {}
hooks = s.setdefault('hooks', {})
for event, entries in ours.items():
    hooks[event] = [e for e in hooks.get(event, []) if not is_ours(e)] + entries
settings.write_text(json.dumps(s, indent=2) + '\n')
print(f'cloud-hooks: {len(ours)} hooks gezet in {settings}')
EOF
