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

| Bestand | Inhoud |
|---|---|
| `hooks/hooks.py` | alle logica, alleen stdlib, systeem-`python3` |
| `hooks/session-start.sh` | kopie van de CCR Stop-hook voor `hooks.py`, daarna die hook stil zetten (elke niet-nul `exit` → `exit 0`) |
| `install.sh` | zet de hooks in `~/.claude/settings.json` van de container |
| `test/test_hooks.py` | `unittest`-tests, ook door pytest op te pakken |
| `harness-watch/` | wekelijkse harness-check, zie de README |
| `.claude/settings.json` | alleen toestemmingen voor de harness-check, geen hooks |

## `hooks.py`

Aanroep: `python3 ~/.claude/cloud-hooks/hooks/hooks.py <event>` (pad zoals `install.sh` het zet) met `<event>` = `user-prompt-submit`, `pre-reply` of `stop`. Eén functie per event plus gedeelde helpers:

- `in_project()`: `CLAUDE_CODE_PROJECTS_SESSION == "1"`.
- `git_label()`: draait `/root/.claude/stop-hook-git-check.orig.sh` (ongewijzigde kopie van de CCR-check, zie hieronder), zet stderr om naar `uncommitted` / `untracked` / `unverified` / `unpushed`, of niets als alles schoon is.
  Kijkt vanuit de startmap van de sessie (`$CLAUDE_PROJECT_DIR`), niet vanuit Claude's huidige cwd. Is die startmap geen git-repo (project met meerdere repo's), dan draait de check per directe submap met `.git` en wordt het label bijvoorbeeld `qpino: unpushed · microdosing: untracked`, alleen met repo's waar iets openstaat.
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
- de kopie `/root/.claude/stop-hook-git-check.orig.sh` ontbreekt of geeft stderr zonder bekend label;
- `/root/.claude/stop-hook-git-check.sh` heeft weer een niet-nul `exit` (sed in `session-start.sh` werkt niet meer);
- reply-input zonder `text`.

## De CCR Stop-hook stil zetten (`session-start.sh`)

De harness registreert zelf `/root/.claude/stop-hook-git-check.sh` als Stop-hook (in `/root/.claude/launcher-settings.json`) en schrijft dat script bij elke start opnieuw.

- Met `exit 2` dwingt die hook Claude te committen en pushen.
- Met `exit 1` blokkeert hij niet, maar toont de app zijn stderr als hook-fout. Die komt een beurt te laat, naast ons eigen `Stop says: git <label>`, en gaf zo dubbele, achterlopende meldingen buiten projecten (2026-10-10).

Daarom kopieert `session-start.sh` het script eerst ongewijzigd naar `stop-hook-git-check.orig.sh` en zet daarna in het origineel elke niet-nul `exit` op `exit 0`, met een markeerregel onderaan. De markering voorkomt dat een tweede SessionStart (`clear`, `compact`) de kopie overschrijft met het gepatchte script. Herschrijft de harness het script, dan ontbreekt de markering en wordt de kopie ververst. `launcher-settings.json` blijft onaangeroerd: die laadt vóór onze SessionStart en wordt bij elke start opnieuw geschreven.

## Registratie (`install.sh`)

`install.sh` zet de hooks in de gebruikersinstellingen (`~/.claude/settings.json`), niet in die van een repo: die laden niet in projecten met meerdere repo's. Eerdere regels van deze repo worden vervangen, andere hooks blijven staan.

- `SessionStart`: `session-start.sh`.
- `UserPromptSubmit`: `hooks.py user-prompt-submit`.
- `PreToolUse`, matcher `mcp__hearthbot__reply`: `hooks.py pre-reply`.
- `Stop`: `hooks.py stop`.

## Tests

`test/test_hooks.py` met `unittest` (de systeem-`python3` heeft geen pytest; `python3 -m unittest test.test_hooks` werkt niet omdat de stdlib zelf een package `test` heeft):

```
python3 test/test_hooks.py
```

Gedekt: wrapper-parsing (meerregelig, entities, `from="system"`, `edited="true"`, geen wrapper), label-mapping vanuit voorbeeld-stderr, `pre-reply` behoudt overige velden, waarschuwingen.

## Bekende beperkingen

- In een project kost `!!` een kleine model-call; de uitvoer is zo letterlijk als Claude hem overneemt.
- Het label hangt aan `reply`: twee replies in één beurt geven twee labels, `no_reply_needed` geeft er geen.
- Een commit of push na de laatste reply telt pas in de volgende beurt mee.
- `!!` buiten het permissiesysteem om, geen tty, max 25 s (zoals nu).

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
