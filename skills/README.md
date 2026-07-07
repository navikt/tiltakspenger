# Skills

Delte, **verktøy-uavhengige** agent-skills for tiltakspenger-monorepoet.

Hver skill er en mappe med en `SKILL.md` i det åpne [Agent Skills](https://code.visualstudio.com/docs)-formatet: ren markdown med en YAML-frontmatter (`name`, `description`, valgfri `metadata`). Formatet leses av flere agentverktøy (GitHub Copilot CLI, Claude, m.fl.) og kan også bare leses manuelt av et menneske eller en lokal LLM. **Ingenting her er bundet til ett bestemt verktøy.**

## Tilgjengelige skills

| Skill | Hva den gjør |
|---|---|
| [`backend-dependency-update`](./backend-dependency-update/SKILL.md) | Finn Dependabot-PR-er, ta dem gruppevis med changelog-/migreringsgjennomgang, verifiser bygg + test, og gjør en vurdering per gruppe. |
| [`tiltakspenger-testdata`](./tiltakspenger-testdata/SKILL.md) | Lag testdata lokalt (sak med innvilget vedtak, meldekortbehandling, klagebehandling) via de ferdige scriptene — digital eller papirsøknad som inngang. |

## Hvordan ta dem i bruk

Skillene er bare markdown, så bruk den måten verktøyet ditt foretrekker:

- **GitHub Copilot CLI** — kopier eller symlink mappa inn i `~/.copilot/skills/`:
  ```bash
  ln -s "$PWD/skills/backend-dependency-update" ~/.copilot/skills/backend-dependency-update
  ```
  (Skills indekseres ved oppstart — start en ny sesjon etterpå.)
- **Claude / claude-code** — symlink inn i `~/.claude/skills/` (samme `SKILL.md`-format).
- **Andre / lokale LLM-verktøy** — pek verktøyet til mappa, eller lim inn `SKILL.md` som kontekst/instruksjon. Innholdet er rene steg-for-steg-instruksjoner.

Den kanoniske kopien bor her i repoet slik at hele teamet deler samme arbeidsflyt; verktøy-spesifikke kataloger (`~/.copilot/skills`, `~/.claude/skills`) peker hit via symlink.
