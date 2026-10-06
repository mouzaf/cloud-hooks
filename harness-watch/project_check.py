#!/usr/bin/env python3
"""Punt 7 en 8 van de harness-check, direct gecontroleerd. Sinds de routine
buiten een project draait (6f29e8f) kan die dat niet meer; dit script draai
je daarom zelf in een draad van een project.

  (7) CLAUDE_CODE_PROJECTS_SESSION is nog "1" (hooks.py: in_project()).
  (8) de reply-tool heet nog mcp__hearthbot__reply (matcher in install.sh).

De toollijst van Claude is vanuit de shell niet te zien, dus Claude geeft de
namen van zijn eigen tools mee. Alleen stdlib.
Gebruik:  python3 harness-watch/project_check.py --tools mcp__hearthbot__reply mcp__hearthbot__react ...
          python3 harness-watch/project_check.py        # alleen punt 7
Exitcode 0 als alles klopt, 1 als er iets afwijkt.
"""
import argparse
import json
import os
import sys

ENV = 'CLAUDE_CODE_PROJECTS_SESSION'
REPLY_TOOL = 'mcp__hearthbot__reply'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--tools', nargs='*', default=None,
                    help='namen uit de eigen toollijst van Claude')
    args = ap.parse_args(argv)
    problems = []

    env = os.environ.get(ENV)
    if env != '1':
        hint = [f'{k}={v}' for k, v in sorted(os.environ.items())
                if k.startswith('CLAUDE_CODE_') and 'PROJECT' in k.upper()]
        problems.append(f'(7) {ENV} is {env!r}, verwacht "1"'
                        + (f'; wel gezien: {hint}' if hint else ''))

    if args.tools is None:
        tool = 'niet gecontroleerd: geef --tools mee'
    else:
        tools = [t.strip(',') for t in args.tools]
        if REPLY_TOOL in tools:
            tool = 'aanwezig'
        else:
            tool = 'ontbreekt'
            similar = [t for t in tools if 'reply' in t or 'hearthbot' in t]
            problems.append(f'(8) {REPLY_TOOL} staat niet in de toollijst'
                            + (f'; wel: {similar}' if similar else ''))

    print(json.dumps({'projects_session_env': env, 'reply_tool': tool,
                      'problems': problems}, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
