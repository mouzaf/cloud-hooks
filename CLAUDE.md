# CLAUDE.md

Remote branches verwijderen (`git push --delete`) lukt niet vanuit cloud-sessies, waarschijnlijk door de GitHub-proxy; vraag de gebruiker dat zelf te doen.

`install.sh` schrijft in `/usr/local/bin` alleen scripts met het voorvoegsel `wanda_`, om botsingen met de standaard containersetup te vermijden, en verwijdert daar nooit iets.
