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
- `fromDate` styrer både hva som godtas og hvor langt tilbake årsnedtrekket lister — skill dem når godkjenningsvinduet er vidt.
- Vent med feilmeldingen til feltet er forlatt, men vis den straks skjemaet har meldt fra om feil.
- I periodefelt: bare feltet som faktisk er feil skal markeres, og fra/til hører sammen i et `Fieldset`.
- `id` skal på `DatePicker.Input`, aldri på `DatePicker` — ellers får du duplikat-id i DOM.

Referanseimplementasjon: `src/components/datovelger/` i `tiltakspenger-soknad`.

## Stil, formatering og linting

- **`pnpm` er pakkehåndtereren** — bruk `pnpm install` / `pnpm run <script>`, ikke `npm`. (Vi er i ferd med å migrere fra npm til pnpm; det kan ligge igjen rusk med npm-referanser her og der — følg `packageManager`-feltet i det aktuelle repoets `package.json`.)
    - **Cooldown på pakker:** `minimumReleaseAge: 10080` (7 dager, som `cooldown` i `dependabot.yml`) i `pnpm-workspace.yaml`. Fra pnpm 11.1.3 sjekkes en committet lockfile mot den ved `pnpm install`, og oppslaget for `@navikt`-pakkene trenger tilgang til GitHub Packages. `PNPM_CONFIG_MINIMUM_RELEASE_AGE=0` overstyrer for én kjøring; `minimumReleaseAgeExclude` er `["@navikt/*", "@nais/*"]`.
    - **`@types:registry=https://registry.npmjs.org/` i `.npmrc`.** Med GitHub Packages som register slår Dependabot opp alle pakker der, og `@types/*` ligger som gamle speilkopier; pnpm feiler da med `ERR_PNPM_NO_MATCHING_VERSION`.
- Hvert frontend-repo har sin egen `eslint.config.*` — sjekk den der for de gjeldende reglene.
- husky + lint-staged der det er konfigurert — lint og formatér
- Script-navn varierer per repo (f.eks. `lint`, `format` / `format:all`, `build`, `test`). **Sjekk `scripts` i det aktuelle repoets `package.json`** før du kjører noe.

## TypeScript

- **Strict mode** (`"strict": true`)
- Unngå `any`
- Ubrukte variabler er feil — prefiks bevisst ubrukte argumenter med `_`

## Prosjektstruktur

Strukturen varierer per repo — **sjekk det aktuelle repoet** før du legger til nye filer, og plasser nye filer der tilsvarende eksisterende ting allerede ligger. Ikke flytt på etablert struktur uten grunn.

## Logging

Samme prinsipp som i backend: **én linje per hendelse i vanlig logg.** Referansen er `tiltakspenger-soknad` (`src/utils/http.ts`, `serverLogger.ts`, `[...middleware].ts`).

- Kall-laget logger vellykkede kall: én info-linje med metode, URL uten query-params, status og `durationMs`.
- Ved feil logger kall-laget ingenting. Det kaster en feil med konteksten i meldingen og originalfeilen som `cause`.
- Flyt-laget logger én `logger.error` med `{ err }` og konsekvensen («returnerer 502»). En håndtert 4xx gir ikke `error`.
- Ingen start- eller prosess-linjer («Henter token», «… start/OK»). Ikke la en formatter overskrive `message` med `err.message`; da blir alle feillinjer like i søk.
- Korrelasjon gjøres av `trace_id` og `span_id`, som settes automatisk, ikke av egne call-id-er.
- Før du legger til en ny logglinje: sjekk hvilken eksisterende linje som alt dekker hendelsen.

## Mikrofrontender

Fire feller i mikrofrontender som rendres inn i Min side:

- **`overflow: hidden` klipper bort fokusringen** når `<a>` fyller kortet. Negativ `outline-offset` (vi bruker `-2px`) løser det; behold nettleserens `outline` framfor en `box-shadow`-ring, som forsvinner i høykontrastmodus.
- **`@font-face` og `@keyframes` prefikses ikke av `postcss-prefix-selector`** og lekker inn i vertens dokument. Importer selektivt fra designsystemet i stedet for hele `ds-css`.
- **Container uten `TZ` kan vise feil dag** for tidspunkter sent på kvelden. Sett `timeZone: "Europe/Oslo"` i `Intl` og `ENV TZ=Europe/Oslo` i Dockerfilen.
- **Match auth-sjekker på path, aldri på hele URL-en.** Sammenlign `pathname` med tillatte stier avgrenset på segmentgrenser, ikke med delstrengsøk i hele URL-en; ellers slipper en beskyttet rute med `?x=/internal` i query-strengen gjennom uten token.

## Testing

Testoppsettet varierer per repo — sjekk det aktuelle repoet:

- **`tiltakspenger-saksbehandling`** — Jest med `jest-environment-jsdom` + `@testing-library/dom` / `@testing-library/jest-dom`.
- **`tiltakspenger-meldekort`** — Playwright (`@playwright/test`), inkl. tilgjengelighetssjekk med `@axe-core/playwright`.
- **`tiltakspenger-soknad`** — Jest med `jest-environment-jsdom` + `@testing-library/react` (`jest.config.mjs`). Kjøres i CI via `kommando`-inputen til den delte node-gaten.
- **`tiltakspenger-meldekort-microfrontend`** har foreløpig ikke et eget test-script.

