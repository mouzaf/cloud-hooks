# Plan: cloud-hooks (`!!` en git-label van de huidige beurt)

Doel: in **alle** cloud-sessies, project of niet:

1. `!! <commando>` draait het commando zelf en toont de uitvoer;
2. de git-status van de **huidige** beurt is zichtbaar (`stop-hook: <label>`).

Laptop/VPS/TUI blijven ongemoeid: alle hooks doen niets als `CLAUDE_CODE_REMOTE != true`.

## Getest gedrag van de harness (2026-10-04)

| Wat | Resultaat |
|---|---|
| Project-sessie herkennen | `CLAUDE_CODE_PROJECTS_SESSION=1` (ook `CLAUDE_CODE_ENTRYPOINT=remote_projects`) |
| Prompt in een project | `<wake …>`-wrapper; het bericht staat in `<message trigger="true" from="human" …>…</message>` |
| Escaping in de wrapper | echte regeleindes; `'`→`&#39;`, `"`→`&#34;`, `&`→`&amp;`, `>`→`&gt;` |
| Spawn-bericht | ook `trigger="true"`, maar `from="system"` |
| Bewerkt bericht | `<wake reason="message-edited">`, `edited="true"`, `trust="peer"`, geen oude tekst |
| Hook-uitvoer in een project | onzichtbaar voor de gebruiker; `additionalContext` bereikt Claude wel |
| PreToolUse `updatedInput` op `mcp__hearthbot__reply` | werkt, maar **vervangt de hele input** (alleen `text` teruggeven gooide `attached_outputs` weg) |
| Stop-hook `systemMessage` buiten een project | zichtbaar in de app |
| Block-`reason` van UserPromptSubmit buiten een project | zichtbaar onder "Prompt blocked by a hook" |
| Hook-wijziging in `.claude/settings.json` | wordt midden in een sessie opgepikt |

## Bestanden

| Bestand | Status |
|---|---|
| `.claude/hooks/hooks.py` | **nieuw**: alle logica, alleen stdlib, systeem-`python3` (niet de venv) |
| `.claude/hooks/session-start.sh` | **bestaat**, ongewijzigd (sed `exit 2`→`exit 1` in de CCR Stop-hook) |
| `.claude/hooks/user-prompt-submit.sh` | **vervalt**, gaat op in `hooks.py` |
| `.claude/settings.json` | **bestaat**, aangepast |
| `test/test_hooks.py` | **nieuw**: `unittest`-tests, ook door pytest op te pakken |

## `hooks.py`

Aanroep: `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/hooks.py <event>` met `<event>` = `user-prompt-submit`, `pre-reply` of `stop`. Eén functie per event plus gedeelde helpers:

- `in_project()`: `CLAUDE_CODE_PROJECTS_SESSION == "1"`.
- `git_label()`: draait `/root/.claude/stop-hook-git-check.sh`, zet stderr om naar `uncommitted` / `untracked` / `unverified` / `unpushed`, of niets als alles schoon is.
- `bang_command(prompt)`: geeft het `!!`-commando terug of `None`. In een project: body uit `<message trigger="true" from="human">` halen, alleen als niet `edited="true"`, daarna `html.unescape`. Geen wrapper gevonden: terugvallen op de kale prompt.
- `run_bang(cmd)`: `bash -c` in de bewaarde cwd (`/tmp/bang-cwd`), max 25 s, laatste 50 regels; gedrag als in het huidige `user-prompt-submit.sh`.

### Gedrag per event

| Event | Buiten een project | In een project |
|---|---|---|
| UserPromptSubmit | `!!`: uitvoeren, blokkeren, uitvoer als `reason` (zoals nu) | `!!`: uitvoeren, niet blokkeren, uitvoer als `additionalContext` met de opdracht hem letterlijk als reply in een codeblok te zetten |
| PreToolUse, matcher `mcp__hearthbot__reply` | n.v.t. | volledige `tool_input` teruggeven met `stop-hook: <label>` onder `text` |
| Stop | `{"systemMessage": "git <label>"}` (de app toont "Stop says: git <label>") | niets |

### Zelfcontrole

Bij elke aanroep controleert `hooks.py` de aannames hierboven. Klopt er een niet, dan komt er een waarschuwing `⚠ cloud-hooks: <wat> — zie doc/cloud_hooks_plan.md`. Buiten een project verschijnt die via `systemMessage`, in een project onder de volgende reply: `user-prompt-submit` zet hem in `/tmp/cloud-hooks-warnings` en `pre-reply` neemt hem mee. Ook een crash van `hooks.py` zelf wordt zo gemeld. Controles:

- project-sessie, `!!` in de prompt, maar geen `<message trigger="true">` (niet elke prompt in een project heeft er een, bv. relays van de coordinator; daarom alleen bij `!!`);
- `/root/.claude/stop-hook-git-check.sh` ontbreekt, bevat weer `exit 2` (sed in `session-start.sh` werkt niet meer), of geeft stderr zonder bekend label;
- reply-input zonder `text`.

## `.claude/settings.json`

- `SessionStart`: `session-start.sh` (ongewijzigd).
- `UserPromptSubmit`: `hooks.py user-prompt-submit` (vervangt `user-prompt-submit.sh`).
- `PreToolUse`, matcher `mcp__hearthbot__reply`: `hooks.py pre-reply`.
- `Stop`: `hooks.py stop`.

## Tests

`test/test_hooks.py` met `unittest` (de systeem-`python3` heeft geen pytest, de venv is er niet altijd; `python3 -m unittest test.test_hooks` werkt niet omdat de stdlib zelf een package `test` heeft):

```
python3 test/test_hooks.py      # overal
venv/bin/python -m pytest test/test_hooks.py   # waar de venv er is
```

Gedekt: wrapper-parsing (meerregelig, entities, `from="system"`, `edited="true"`, geen wrapper), label-mapping vanuit voorbeeld-stderr, `pre-reply` behoudt overige velden, waarschuwingen.

## Bekende beperkingen

- In een project kost `!!` een kleine model-call; de uitvoer is zo letterlijk als Claude hem overneemt.
- Het label hangt aan `reply`: twee replies in één beurt geven twee labels, `no_reply_needed` geeft er geen.
- Een commit of push na de laatste reply telt pas in de volgende beurt mee.
- `!!` buiten het permissiesysteem om, geen tty, max 25 s (zoals nu).

## Opruiming

- `.claude/hooks/hooktest.sh` verwijderen.
- De `hooktest`-registraties uit `.claude/settings.json` halen.
- `.claude/hooks/user-prompt-submit.sh` verwijderen.
- `/tmp/hooktest/` verdwijnt met de container; niets te doen.

## Teststappen voor Wanda

Na de implementatie, op de branch:

**Buiten een project** (nieuwe cloud-sessie op de branch):

1. `!! pwd` → geblokkeerd, uitvoer zichtbaar onder "Prompt blocked by a hook".
2. `!! cd /tmp` en daarna `!! pwd` → `/tmp`.
3. Laat Claude een bestand aanpassen zonder te committen → na het antwoord de notice `Stop says: git uncommitted`.
4. Laat Claude committen en pushen → in de beurt daarna geen label. Doe je in een beurt niets met git terwijl er nog werk openstaat, dan blijft het label staan: het toont de staat van de repo, niet wat er die beurt gebeurde.

**In een project** (thread op de branch):

5. `!! echo 'a' && echo b > /tmp/x; cat /tmp/x` → reply met `$ echo 'a' && …` en daaronder `a` en `b`, in een codeblok.
6. Bewerk dat bericht → het commando draait niet opnieuw.
7. Laat Claude een bestand aanpassen zonder te committen → `stop-hook: uncommitted` onder de reply, in dezelfde beurt.
8. Vraag om een reply met een bijlage of link → de linkkaart staat er nog.

**Overal:**

9. `python3 test/test_hooks.py` → alles groen.
10. Geen `⚠ cloud-hooks`-waarschuwing tijdens stap 1 t/m 8.
