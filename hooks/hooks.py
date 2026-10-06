#!/usr/bin/env python3
"""Hooks voor cloud-sessies: `!! <commando>` en het git-label van de huidige
beurt, in project- en niet-project-sessies. Zie doc/cloud_hooks_plan.md.

Aanroep vanuit .claude/settings.json:
    python3 hooks.py user-prompt-submit | pre-reply | stop

Alleen stdlib en de systeem-python3: hooks draaien ook als de venv er (nog)
niet is. Buiten cloud-sessies doet dit script niets; laptop/VPS/TUI hebben
een echte shell met `!` bash mode.

De harness-formaten waar dit op leunt (prompt-wrapper in projecten, stderr
van de CCR Stop-hook) zijn niet gedocumenteerd en kunnen veranderen. Elke
afwijking wordt daarom zichtbaar gemeld als waarschuwing in plaats van stil
genegeerd: anders merkt niemand dat een hook niet meer werkt.
"""
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

GIT_CHECK = Path('/root/.claude/stop-hook-git-check.sh')
# /tmp: buiten de repo, verdwijnt met de container.
CWD_FILE = Path('/tmp/bang-cwd')
# Waarschuwingen uit hooks waarvan de uitvoer in een project onzichtbaar is,
# tot de volgende reply ze meeneemt.
PENDING_FILE = Path('/tmp/cloud-hooks-warnings')

BANG_TIMEOUT = 25  # hook-timeout is 30 s; daarboven gooit CC de uitvoer weg
BANG_MAX_LINES = 50

# Volgorde = volgorde van de checks in stop-hook-git-check.sh.
LABELS = [
    ('uncommitted changes', 'uncommitted'),
    ('untracked files', 'untracked'),
    ('Unverified', 'unverified'),
    ('unpushed commit', 'unpushed'),
]

MESSAGE_RE = re.compile(r'<message\b([^>]*)>(.*?)</message>', re.DOTALL)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def warning(what):
    return f'⚠ cloud-hooks: {what} — zie doc/cloud_hooks_plan.md'


def in_project():
    return os.environ.get('CLAUDE_CODE_PROJECTS_SESSION') == '1'


# --- git-label --------------------------------------------------------------

def label_from_stderr(stderr):
    for needle, label in LABELS:
        if needle in stderr:
            return label
    return None


def git_label(cwd=None):
    """(label of None, waarschuwingen). Hergebruikt de CCR-check, zodat het
    label altijd overeenkomt met wat de harness zelf als openstaand ziet.

    Een project met meerdere repo's start boven de clones, waar de CCR-check
    niets ziet; dan draait hij per repo eronder en noemt het label alleen de
    repo's met iets open."""
    if not GIT_CHECK.is_file():
        return None, [warning(f'{GIT_CHECK} ontbreekt, geen git-label')]
    warnings = []
    if re.search(r'\bexit 2\b', GIT_CHECK.read_text()):
        warnings.append(warning(
            f'{GIT_CHECK.name} bevat weer `exit 2` en blokkeert dus; '
            'de sed in session-start.sh werkt niet meer'))
    cwd = Path(cwd or os.getcwd())
    if in_repo(cwd):
        label, more = repo_label(cwd)
        return label, warnings + more
    parts = []
    for repo in sub_repos(cwd):
        label, more = repo_label(repo)
        warnings += more
        if label:
            parts.append(f'{repo.name}: {label}')
    return (' · '.join(parts) or None), warnings


def label_root(data):
    """Waar het label naar kijkt. De startmap van de sessie, niet de cwd
    van de hook-input: die volgt Claude's `cd` en zou na een `cd /tmp` een
    schoon label geven, of in een project met meerdere repo's alleen de repo
    waar Claude toevallig staat."""
    return os.environ.get('CLAUDE_PROJECT_DIR') or data.get('cwd')


def in_repo(path):
    proc = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'],
                          cwd=path, capture_output=True, text=True, timeout=10)
    return proc.returncode == 0 and proc.stdout.strip() == 'true'


def sub_repos(path):
    # `.git` kan ook een bestand zijn (worktree, submodule).
    try:
        return sorted(d for d in path.iterdir()
                      if d.is_dir() and (d / '.git').exists())
    except OSError:
        return []


def repo_label(cwd):
    proc = subprocess.run(['bash', str(GIT_CHECK)], input='{}', cwd=cwd,
                          capture_output=True, text=True, timeout=10)
    if proc.returncode == 0:
        return None, []
    label = label_from_stderr(proc.stderr)
    if label is None:
        first = (proc.stderr.strip().splitlines() or ['(geen stderr)'])[0]
        return None, [warning(f'onbekende uitvoer van {GIT_CHECK.name} in '
                              f'{cwd.name}: {first[:120]}')]
    return label, []


# --- `!!` -------------------------------------------------------------------

def trigger_message(prompt):
    """(attributen, body) van de <message trigger="true"> in een project-
    wrapper, of None. Body is ge-unescaped."""
    for m in MESSAGE_RE.finditer(prompt):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        if attrs.get('trigger') == 'true':
            return attrs, html.unescape(m.group(2))
    return None


def bang_command(prompt, project):
    """(commando of None, waarschuwingen). Een leeg commando betekent `!!`
    zonder argument."""
    text = prompt
    if project:
        found = trigger_message(prompt)
        if found is None:
            # Niet elke prompt in een project heeft een trigger-message
            # (relays, cross-session-berichten); alleen waarschuwen als het
            # er op lijkt dat iemand een `!!` bedoelde.
            if '!!' not in prompt:
                return None, []
            return None, [warning('`!!` gezien, maar geen '
                                  '<message trigger="true"> in de prompt')]
        attrs, text = found
        # Een bewerking zou het commando opnieuw draaien.
        if attrs.get('from') != 'human' or attrs.get('edited') == 'true':
            return None, []
    if text != '!!' and not text.startswith('!! '):
        return None, []
    cmd = text[3:]
    return (cmd if cmd.strip() else ''), []


def run_bang(cmd):
    """Uitvoer zoals die getoond wordt: `$ cmd`, laatste regels, status."""
    try:
        cwd = CWD_FILE.read_text().strip()
    except OSError:
        cwd = ''
    if not os.path.isdir(cwd):
        cwd = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()
    # pwd via EXIT-trap, zodat ook een `exit` in het commando de cwd bewaart.
    script = 'trap "pwd > \\"$CWDFILE\\"" EXIT; eval "$1"'
    proc = subprocess.run(
        ['timeout', '-k', '2', str(BANG_TIMEOUT), 'bash', '-c', script, '_', cmd],
        cwd=cwd, env={**os.environ, 'CWDFILE': str(CWD_FILE)},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    lines = proc.stdout.decode(errors='replace').splitlines()
    msg = [f'$ {cmd}'] + lines[-BANG_MAX_LINES:]
    if len(lines) > BANG_MAX_LINES:
        msg.append(f'[… {len(lines) - BANG_MAX_LINES} regels afgekapt, '
                   f'laatste {BANG_MAX_LINES} getoond]')
    if proc.returncode == 124:
        msg.append(f'[timeout na {BANG_TIMEOUT} s]')
    if proc.returncode != 0:
        msg.append(f'[exit {proc.returncode}]')
    return '\n'.join(msg)


USAGE = (f'gebruik: !! <commando>   (shell in cwd van vorige !!, geen tty, '
         f'max {BANG_TIMEOUT} s, laatste {BANG_MAX_LINES} regels)')


# --- pending waarschuwingen -------------------------------------------------

def push_pending(warnings):
    if warnings:
        with PENDING_FILE.open('a') as f:
            f.writelines(w + '\n' for w in warnings)


def pop_pending():
    try:
        lines = PENDING_FILE.read_text().splitlines()
        PENDING_FILE.unlink()
    except OSError:
        return []
    return list(dict.fromkeys(lines))  # dedup, volgorde behouden


# --- events -----------------------------------------------------------------

def user_prompt_submit(data):
    project = in_project()
    cmd, warnings = bang_command(data.get('prompt') or '', project)
    if project:
        # Hook-uitvoer is in een project onzichtbaar: alleen wat Claude met
        # de berichttools post, komt bij de gebruiker.
        push_pending(warnings)
        if cmd is None:
            return None
        out = run_bang(cmd) if cmd else USAGE
        return {'hookSpecificOutput': {
            'hookEventName': 'UserPromptSubmit',
            'additionalContext': (
                'Dit bericht is een `!!`-commando; de hook heeft het al '
                'uitgevoerd. Plaats de uitvoer hieronder letterlijk als reply '
                'in één codeblok (met een fence die niet in de uitvoer '
                'voorkomt), zonder verdere tekst en zonder verder iets te '
                'doen.\n\n' + out)}}
    result = {}
    if warnings:
        result['systemMessage'] = '\n'.join(warnings)
    if cmd is not None:
        # Blokkeren: geen model-call, en `reason` toont de app uitklapbaar
        # onder "Prompt blocked by a hook".
        result.update({
            'decision': 'block',
            'reason': run_bang(cmd) if cmd else USAGE,
            'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit',
                                   'suppressOriginalPrompt': True}})
    return result or None


def pre_reply(data):
    if not in_project():
        return None
    tool_input = data.get('tool_input')
    if not isinstance(tool_input, dict) or not isinstance(
            tool_input.get('text'), str):
        push_pending([warning('reply-input zonder `text`, geen git-label')])
        return None
    label, warnings = git_label(label_root(data))
    lines = ([f'stop-hook: {label}'] if label else []) + pop_pending() + warnings
    if not lines:
        return None
    # updatedInput vervangt de hele input (getest): alles teruggeven, anders
    # verdwijnen o.a. attached_outputs.
    new_input = {**tool_input,
                 'text': tool_input['text'] + '\n\n' + '\n'.join(lines)}
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                   'permissionDecision': 'allow',
                                   'updatedInput': new_input}}


def stop(data):
    # In een project ziet de gebruiker dit niet; daar doet pre-reply het.
    if in_project():
        return None
    label, warnings = git_label(label_root(data))
    # De app zet er zelf "Stop says:" voor; "stop-hook:" zou dubbel zijn.
    lines = ([f'git {label}'] if label else []) + warnings
    return {'systemMessage': '\n'.join(lines)} if lines else None


EVENTS = {
    'user-prompt-submit': user_prompt_submit,
    'pre-reply': pre_reply,
    'stop': stop,
}


def main():
    if os.environ.get('CLAUDE_CODE_REMOTE') != 'true':
        return
    event = sys.argv[1] if len(sys.argv) > 1 else ''
    try:
        data = json.load(sys.stdin)
        result = EVENTS[event](data)
    except Exception as e:  # noqa: BLE001 - een hook mag nooit stil falen
        what = warning(f'{event or "?"}: {type(e).__name__}: {e}')
        if in_project():
            push_pending([what])
            return
        result = {'systemMessage': what}
    if result:
        json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
