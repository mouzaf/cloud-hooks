#!/usr/bin/env python3
"""Wekelijkse check of de harness (Claude Code, cloud-omgeving, Projects) is
veranderd op punten waar de cloud-hooks (hooks/hooks.py) op
leunen. Draait vanuit de routine "Harness-check cloud-hooks".

Deterministisch deel: haalt nieuwe changelog-items op, controleert de
container en diff't relevante doc-pagina's. Het beoordelen of een item echt
raakt aan onze hooks doet de routine (Claude) daarna met het rapport.

Stand tussen runs: state.json en docs/ naast dit script. Alleen stdlib.
Gebruik:  python3 harness_check.py          # rapport (JSON) + stand bijwerken
          python3 harness_check.py --dry    # rapport, stand niet bijwerken
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / 'state.json'
DOCS_DIR = HERE / 'docs'

CHANGELOG = 'https://code.claude.com/docs/en/changelog.md'
DOC_PAGES = ['hooks', 'claude-projects', 'claude-code-on-the-web']
DOC_URL = 'https://code.claude.com/docs/en/{}.md'

GIT_CHECK = Path('/root/.claude/stop-hook-git-check.sh')
LAUNCHER = Path.home() / '.claude' / 'launcher-settings.json'
# stderr-teksten waar hooks.py (LABELS) op matcht
GIT_CHECK_NEEDLES = ['uncommitted changes', 'untracked files', 'Unverified',
                     'unpushed commit']

KEYWORDS = re.compile(
    r'hook|systemMessage|updatedInput|additionalContext|UserPromptSubmit|'
    r'PreToolUse|Stop\b|timeout|bash mode|`!`|git status|cloud|web|remote|'
    r'project|CLAUDE_CODE_|hearth|python|edited', re.IGNORECASE)


def fetch(url):
    # Met de standaard Python-urllib-User-Agent geeft de site 403.
    req = urllib.request.Request(url, headers={'User-Agent': 'curl/8'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8', errors='replace')


def vkey(v):
    return tuple(int(x) for x in re.findall(r'\d+', v))


def changelog_entries(text):
    """[(versie, datum, tekst)], nieuwste eerst."""
    parts = re.split(r'(<Update label="([^"]+)" description="([^"]*)">)', text)
    out = []
    # split geeft: pre, tag, label, desc, body, tag, label, desc, body, ...
    for i in range(1, len(parts) - 3, 4):
        body = parts[i + 3].split('</Update>')[0].strip()
        out.append((parts[i + 1], parts[i + 2], body))
    return out


def check_changelog(state, report):
    try:
        entries = changelog_entries(fetch(CHANGELOG))
    except Exception as e:  # noqa: BLE001
        report['problems'].append(f'changelog niet op te halen: {e}')
        return
    if not entries:
        report['problems'].append('changelog-formaat onbekend: geen '
                                  '<Update label=...>-items gevonden')
        return
    last = state.get('last_seen_version')
    new = [e for e in entries if last is None or vkey(e[0]) > vkey(last)]
    report['changelog'] = {
        'last_seen_version': last,
        'latest_version': entries[0][0],
        'new_entries': [
            {'version': v, 'date': d,
             'keyword_lines': [ln for ln in body.splitlines()
                               if KEYWORDS.search(ln)],
             'text': body}
            for v, d, body in new],
    }
    state['last_seen_version'] = entries[0][0]


def check_container(state, report):
    c = {}
    try:
        c['claude_version'] = subprocess.run(
            ['claude', '--version'], capture_output=True, text=True,
            timeout=30).stdout.strip()
    except Exception as e:  # noqa: BLE001
        c['claude_version'] = f'fout: {e}'
    c['python3'] = sys.version.split()[0]
    for tool in ('bash', 'timeout'):
        if not shutil.which(tool):
            report['problems'].append(f'`{tool}` ontbreekt in de container')

    if not GIT_CHECK.is_file():
        report['problems'].append(f'{GIT_CHECK} ontbreekt')
    else:
        src = GIT_CHECK.read_text()
        missing = [n for n in GIT_CHECK_NEEDLES if n not in src]
        if missing:
            report['problems'].append(
                f'{GIT_CHECK.name} bevat niet meer: {missing} '
                '(labels in hooks.py matchen daar op)')
        if not re.search(r'\bexit [12]\b', src):
            report['problems'].append(
                f'{GIT_CHECK.name} heeft geen `exit 1`/`exit 2` meer; '
                'de sed in session-start.sh doet dan mogelijk niets')

    try:
        hooks = json.loads(LAUNCHER.read_text()).get('hooks', {})
        cur = sorted(f'{ev}: {h.get("command")}' for ev, groups in hooks.items()
                     for g in groups for h in g.get('hooks', []))
    except Exception as e:  # noqa: BLE001
        cur = [f'fout bij lezen: {e}']
    prev = state.get('launcher_hooks')
    if prev is not None and cur != prev:
        report['problems'].append(
            'harness-hooks in launcher-settings.json gewijzigd: '
            f'erbij {sorted(set(cur) - set(prev))}, '
            f'weg {sorted(set(prev) - set(cur))}')
    state['launcher_hooks'] = cur

    c['projects_session_env'] = os.environ.get('CLAUDE_CODE_PROJECTS_SESSION')
    report['container'] = c


def check_docs(state, report):
    DOCS_DIR.mkdir(exist_ok=True)
    hashes = state.setdefault('doc_hashes', {})
    report['docs'] = {}
    for page in DOC_PAGES:
        try:
            text = fetch(DOC_URL.format(page))
        except Exception as e:  # noqa: BLE001
            report['problems'].append(f'doc {page} niet op te halen: {e}')
            continue
        h = hashlib.sha256(text.encode()).hexdigest()
        old_file = DOCS_DIR / f'{page}.md'
        if page in hashes and hashes[page] != h and old_file.is_file():
            diff = [ln for ln in difflib.unified_diff(
                old_file.read_text().splitlines(), text.splitlines(),
                lineterm='', n=0)
                if ln[:1] in '+-' and not ln.startswith(('+++', '---'))]
            report['docs'][page] = {
                'changed_lines': len(diff),
                'keyword_lines': [ln[:300] for ln in diff
                                  if KEYWORDS.search(ln)][:80],
            }
        hashes[page] = h
        report['_new_docs'][page] = text


def main():
    dry = '--dry' in sys.argv
    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    report = {'problems': [], '_new_docs': {}}
    check_changelog(state, report)
    check_container(state, report)
    check_docs(state, report)
    new_docs = report.pop('_new_docs')
    if not dry:
        for page, text in new_docs.items():
            (DOCS_DIR / f'{page}.md').write_text(text)
        STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
