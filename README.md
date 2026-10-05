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
