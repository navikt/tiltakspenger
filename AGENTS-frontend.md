# AGENTS-frontend.md

TypeScript/React-frontendkonvensjoner for `tiltakspenger`. Les [`AGENTS.md`](AGENTS.md) først for de globale reglene.

## Rammeverk og biblioteker

- **React** med **TypeScript** (strict mode) — se modul-tabellen i [`AGENTS.md`](AGENTS.md) for hvilket rammeverk (Next.js / Vite / Astro) hver frontend bruker
- **@navikt/ds-react** (NAVs Aksel-designsystem) — foretrekk alltid Aksel-komponenter framfor egendefinerte. Les «Retningslinjer» på komponentsiden, ikke bare props-tabellen
- **@navikt/aksel-icons** for ikoner
- **SWR** for datahenting
- **dayjs** for datohåndtering
- Hold skjemaer enkle og minimér bibliotekbruk. `react-hook-form` fases gradvis ut der det er mulig — det finnes fortsatt i deler av kodebasen, men **ny kode bør ha en god grunn for å ta det i bruk**. Foretrekk enkle, forvaltbare skjemaer uten ekstra bibliotek.
- **@navikt/oasis** for token-håndtering på frontend

## Skjemaer og datoer

Datofelter har egne regler hos oss, og de er lette å bomme på. **Les [«Designsystem, skjemaer og datoer (Aksel)» i `README.md`](README.md#designsystem-skjemaer-og-datoer-aksel) før du rører et datofelt** — der ligger både kildene (Aksel, Uutilsynet, Digdir) og de konkrete reglene vi har landet på. Kort oppsummert:

- Tekstfeltet er hovedveien inn; datovelgeren er et supplement. Ingen forhåndsutfylt dato.
- Formatet hører hjemme i `description` (`Format: dd.mm.åååå`), ikke i labelen.
- Ikke skriv egen dato-parsing — Aksel godtar allerede flere formater.
- `dropdownCaption` når feltet har både `fromDate` og `toDate`, så bruker slipper å bla måned for måned.
- `id` skal på `DatePicker.Input`, aldri på `DatePicker` — ellers får du duplikat-id i DOM.

Referanseimplementasjon: `src/components/datovelger/` i `tiltakspenger-soknad`.

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

