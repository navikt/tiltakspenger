# AGENTS-frontend.md

TypeScript/React-frontendkonvensjoner for `tiltakspenger`. Les [`AGENTS.md`](AGENTS.md) først for de globale reglene.

## Rammeverk og biblioteker

- **React** med **TypeScript** (strict mode) — se modul-tabellen i [`AGENTS.md`](AGENTS.md) for hvilket rammeverk (Next.js / Vite / Astro) hver frontend bruker
- **@navikt/ds-react** (NAVs Aksel-designsystem) — foretrekk alltid Aksel-komponenter framfor egendefinerte
- **@navikt/aksel-icons** for ikoner
- **SWR** for datahenting
- **dayjs** for datohåndtering
- Hold skjemaer enkle og minimér bibliotekbruk. `react-hook-form` fases gradvis ut der det er mulig — det finnes fortsatt i deler av kodebasen, men **ny kode bør ha en god grunn for å ta det i bruk**. Foretrekk enkle, forvaltbare skjemaer uten ekstra bibliotek.
- **@navikt/oasis** for token-håndtering på frontend

## Stil, formatering og linting

- **`pnpm` er pakkehåndtereren** — bruk `pnpm install` / `pnpm run <script>`, ikke `npm`. (Vi er i ferd med å migrere fra npm til pnpm; det kan ligge igjen rusk med npm-referanser her og der — følg `packageManager`-feltet i det aktuelle repoets `package.json`.)
- Hvert frontend-repo har sin egen `eslint.config.*` — sjekk den der for de gjeldende reglene.
- husky + lint-staged der det er konfigurert — lint og formatér
- Script-navn varierer per repo (f.eks. `lint`, `format` / `format:all`, `build`, `test`). **Sjekk `scripts` i det aktuelle repoets `package.json`** før du kjører noe.

## TypeScript

- **Strict mode** (`"strict": true`)
- Unngå `any`
- Ubrukte variabler er feil — prefiks bevisst ubrukte argumenter med `_`

## Prosjektstruktur

Strukturen varierer per repo — **sjekk det aktuelle repoet** før du legger til nye filer, og plasser nye filer der tilsvarende eksisterende ting allerede ligger. Ikke flytt på etablert struktur uten grunn.

## Testing

Testoppsettet varierer per repo — sjekk det aktuelle repoet:

- **`tiltakspenger-saksbehandling`** — Jest med `jest-environment-jsdom` + `@testing-library/dom` / `@testing-library/jest-dom`.
- **`tiltakspenger-meldekort`** — Playwright (`@playwright/test`), inkl. tilgjengelighetssjekk med `@axe-core/playwright`.
- **`tiltakspenger-soknad`** og **`tiltakspenger-meldekort-microfrontend`** har foreløpig ikke et eget test-script.

