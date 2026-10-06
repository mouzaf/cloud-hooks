# cloud-hooks

Hooks voor Claude Code cloud-sessies, met en zonder project: `!! <commando>` en het git-label van de huidige beurt.
Ontwerp en achtergrond: [doc/cloud_hooks_plan.md](doc/cloud_hooks_plan.md).

## Gebruik

Zet in het setup-script van de cloud environment (claude.ai/code, environment-instellingen):

```bash
{ git clone --depth 1 https://github.com/mouzaf/cloud-hooks ~/.claude/cloud-hooks &&
  ~/.claude/cloud-hooks/install.sh; } || echo "cloud-hooks: installatie mislukt" >&2
```

Een setup-script dat niet met 0 eindigt, laat de sessie niet starten; de `||` zorgt dat een mislukte installatie alleen de hooks kost.

Elke nieuwe cloud-sessie met die environment heeft dan de hooks: één of meer repo's, met of zonder project. Een project kiest zijn environment onder Project settings > Environment.

Het resultaat van het setup-script wordt gecachet. Het script draait opnieuw als je het setup-script of de netwerk-instellingen van de environment wijzigt, en verder ongeveer eens per zeven dagen. Pas dan komt een nieuwe versie van de hooks binnen.

## Wekelijkse harness-check

De hooks leunen op details van de harness die zonder aankondiging kunnen veranderen. Daarom kijkt er elke week een Claude-draad naar, in het cloud-hooks-project van Wanda:

- De routine "Harness-check cloud-hooks" is alleen een wekker. Elke maandag om 08:52 laat hij een nieuwe draad "Harness-check dd-mm-jjjj" starten.
- Die draad voert [harness-watch/routine-opdracht.md](harness-watch/routine-opdracht.md) uit. Hij draait [harness-watch/harness_check.py](harness-watch/harness_check.py) en beoordeelt het rapport.
- De stand tussen runs (`state.json`, `docs/`) staat in `/mnt/project-files/harness-watch/`, buiten de repo. Het script krijgt die map als argument.
- [.claude/settings.json](.claude/settings.json) staat de commando's van die draad toe, zodat auto mode ze niet weigert.

De draad meldt zich alleen als er iets is dat de hooks raakt.
