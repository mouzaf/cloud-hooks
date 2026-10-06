Harness-check voor mouzaf/cloud-hooks (hooks/hooks.py, zie doc/cloud_hooks_plan.md), op verzoek van Wanda. Je draait als routine in een verse sessie buiten een project, met deze repo als werkmap. De stand van eerdere runs staat in harness-watch/state/ op main.

1. Draai vanuit de root van de repo, op de laatste main:
   ```
   git pull --rebase origin main
   python3 harness-watch/harness_check.py harness-watch/state
   ```
   Het script geeft een JSON-rapport: `problems` (container- en harness-afwijkingen), `changelog.new_entries` (per nieuwe Claude Code-versie de changelog-regels die op trefwoorden matchen, plus het aantal overige regels), `docs` (per gewijzigde doc-pagina, van hooks, claude-projects en claude-code-on-the-web, de nieuwe en verdwenen regels met trefwoorden) en `container`. Het werkt zelf de stand bij in harness-watch/state/ (state.json, docs/).
2. Commit en push de bijgewerkte stand direct naar main (Wanda heeft daar toestemming voor gegeven; alleen deze map):
   ```
   git add harness-watch/state
   git commit -m "harness-check: stand dd-mm-jjjj"
   git push origin HEAD:main
   ```
   Gebruik als datum vandaag in Europe/Amsterdam. Is er niets veranderd, sla de commit over.
3. Beoordeel de nieuwe changelog-regels en doc-wijzigingen inhoudelijk op deze punten:
   Code kan eenvoudiger: (1) hook-uitvoer (systemMessage/block-reason) zichtbaar in project-sessies; (2) een eigen `!`-shell/bash mode in cloud- of desktop-sessies; (3) de app toont zelf de git-status per beurt; (4) de CCR git-check (stop-hook-git-check.sh) blokkeert standaard niet meer; (5) PreToolUse updatedInput voegt samen i.p.v. te vervangen; (6) hook-timeout hoger dan 30 s.
   Stil kapot: (7) CLAUDE_CODE_PROJECTS_SESSION verdwijnt of wordt hernoemd; (8) de reply-tool heet niet meer mcp__hearthbot__reply; (9) het veld `prompt` in de UserPromptSubmit-input wordt hernoemd; (10) het attribuut edited="true" in project-berichten wordt hernoemd; (11) python3 verdwijnt uit de container.
   Punt 7 en 8 kun je hier alleen via changelog en docs volgen: buiten een project bestaan die variabele en tool niet, dus een lege `projects_session_env` is geen probleem.
4. Sluit af met een korte samenvatting in het Nederlands, voor Wanda. Is er iets (een item in `problems`, een fout in stap 1 of 2, of een changelog-/doc-wijziging die een van de punten raakt): per bevinding het puntnummer, wat er veranderd is (met versie of bron) en wat dat voor hooks.py betekent. Anders één regel dat er niets relevants was, met de Claude Code-versie. Verander zelf niets aan code of hooks.
