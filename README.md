# cloud-hooks

Hooks voor Claude Code cloud-sessies, met en zonder project: `!! <commando>` en het git-label van de huidige beurt.
Ontwerp en achtergrond: [doc/cloud_hooks_plan.md](doc/cloud_hooks_plan.md).

## Gebruik

Zet in het setup-script van de cloud environment (claude.ai/code, environment-instellingen):

```bash
{ git clone --depth 1 https://github.com/mouzaf/cloud-hooks ~/.claude/cloud-hooks && ~/.claude/cloud-hooks/install.sh; } || echo "cloud-hooks: installatie mislukt" >&2
```

Een setup-script dat niet met 0 eindigt, laat de sessie niet starten; de `||` zorgt dat een mislukte installatie alleen de hooks kost.

Elke nieuwe cloud-sessie met die environment heeft dan de hooks: één of meer repo's, met of zonder project. Een project kiest zijn environment onder Project settings > Environment.

Het resultaat van het setup-script wordt gecachet. Het script draait opnieuw als je het setup-script of de netwerk-instellingen van de environment wijzigt, en verder ongeveer eens per zeven dagen. Pas dan komt een nieuwe versie van de hooks binnen.

## Het commando `url`

`install.sh` zet naast de hooks ook het commando `url` in `/usr/local/bin`. Het print de claude.ai-link van de huidige sessie.

## Wekelijkse harness-check

De hooks leunen op details van de harness die zonder aankondiging kunnen veranderen. Daarom kijkt er twee keer per week een Claude-routine naar:

- De routine "Harness-check cloud-hooks" staat buiten een project en start elke maandag en woensdag om 06:52 een verse sessie in deze repo.
- Die sessie voert [harness-watch/routine-opdracht.md](harness-watch/routine-opdracht.md) uit. Hij draait [harness-watch/harness_check.py](harness-watch/harness_check.py) en beoordeelt het rapport.
- De stand tussen runs (`state.json`, `docs/`) staat in [harness-watch/state/](harness-watch/state/). De run commit die na afloop naar main.
- [.claude/settings.json](.claude/settings.json) staat de commando's van die run toe, zodat auto mode ze niet weigert.
- Punt 7 en 8 (de projectvariabele en de reply-tool) kan die routine buiten een project niet zelf zien. Die controleer je in een projectdraad met [harness-watch/project_check.py](harness-watch/project_check.py), met de eigen toollijst als `--tools`.

De samenvatting van elke run staat in de sessie van die run.
