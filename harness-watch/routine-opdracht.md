Wekelijkse harness-check voor mouzaf/cloud-hooks (hooks/hooks.py, zie doc/cloud_hooks_plan.md), op verzoek van Wanda. Elke run is een eigen draad in dit project; de stand van eerdere runs staat in /mnt/project-files/harness-watch/.

1. Haal de nieuwste cloud-hooks op en draai het script uit die repo, met de stand in de projectmap:
   ```
   git clone --depth 1 https://github.com/mouzaf/cloud-hooks /tmp/cloud-hooks 2>/dev/null || git -C /tmp/cloud-hooks pull -q
   python3 /tmp/cloud-hooks/harness-watch/harness_check.py /mnt/project-files/harness-watch
   ```
   Het script geeft een JSON-rapport: `problems` (container- en harness-afwijkingen), `changelog.new_entries` (Claude Code changelog-items sinds de vorige run), `docs` (gewijzigde regels in de doc-pagina's hooks, claude-projects en claude-code-on-the-web) en `container`. Het werkt zelf de stand bij in /mnt/project-files/harness-watch/ (state.json, docs/).
2. Controleer ook zelf: staat `mcp__hearthbot__reply` nog in je eigen toollijst, en is `container.projects_session_env` nog "1"?
3. Beoordeel de nieuwe changelog-items en doc-wijzigingen inhoudelijk op deze punten:
   Code kan eenvoudiger: (1) hook-uitvoer (systemMessage/block-reason) zichtbaar in project-sessies; (2) een eigen `!`-shell/bash mode in cloud- of desktop-sessies; (3) de app toont zelf de git-status per beurt; (4) de CCR git-check (stop-hook-git-check.sh) blokkeert standaard niet meer; (5) PreToolUse updatedInput voegt samen i.p.v. te vervangen; (6) hook-timeout hoger dan 30 s.
   Stil kapot: (7) CLAUDE_CODE_PROJECTS_SESSION verdwijnt of wordt hernoemd; (8) de reply-tool heet niet meer mcp__hearthbot__reply; (9) het veld `prompt` in de UserPromptSubmit-input wordt hernoemd; (10) het attribuut edited="true" in project-berichten wordt hernoemd; (11) python3 verdwijnt uit de container.
4. Stuur één reply in je draad aan Wanda, in het Nederlands. Is er iets (een item in `problems`, een fout in stap 1 of 2, of een changelog-/doc-wijziging die een van de punten raakt): per bevinding het puntnummer, wat er veranderd is (met versie of bron) en wat dat voor hooks.py betekent. Is er niets relevants: één regel dat de check niets relevants vond, met de Claude Code-versie. Verander zelf niets aan code of hooks. Zet de draad daarna op voltooid als er niets relevants was.
