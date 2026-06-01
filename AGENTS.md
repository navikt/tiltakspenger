# AGENTS.md

> **Selv-oppdateringsregel:** Når du gjør endringer i prosjektstruktur, konvensjoner, avhengigheter, API-mønstre eller arbeidsflyter beskrevet i denne filen, skal du oppdatere filen som en del av samme commit.

## Oversikt

`tiltakspenger` er NAVs monorepo for tiltakspenger-ytelsen.
Vi bruker norsk bokmål for å beskrive domenet — engelsk brukes kun for rene teknologinavn som ikke har en god eller vanlig norsk oversettelse.
Vi bruker også i størst mulig grad de særnorske tegnene æøå, med unntak av noen tekniske begrensninger i enkelte bibliotek, rammeverk, konsumenter og standarder.
Repoet består av flere Kotlin/JVM-backendtjenester, et delt Kotlin-bibliotek og TypeScript/React-frontendapplikasjoner.

Denne filen dokumenterer **tverrgående regler** som gjelder for alle sub-repoer. Typespesifikke konvensjoner ligger i:

- [`AGENTS-backend.md`](AGENTS-backend.md) — Kotlin/JVM-backendtjenester og `tiltakspenger-libs`
- [`AGENTS-frontend.md`](AGENTS-frontend.md) — TypeScript/React-frontender

> **⚠️ Viktig for agenter:** Hvert sub-repo (f.eks. `tiltakspenger-saksbehandling-api`, `tiltakspenger-libs`, …) har sin **egen `.git/`-katalog** — de er uavhengige git-repoer som er sjekket ut side om side under denne mappen. Workspace-søkeverktøy (`file_search`, `grep_search`, semantisk indeksering) behandler hver nøstede `.git` som en repogrense og **vil ikke traversere inn i sub-repoer**. Når du trenger filer inne i et sub-repo, bruk `list_dir` og `read_file` med absolutte stier, eller kjør `rg`/`grep -r`/`find` inne fra sub-repoet. Se [Arbeid på tvers av sub-repoer](#arbeid-på-tvers-av-sub-repoer) under.

## Agentregler (gjelder alle repoer)

- **Ingen muterende git-kommandoer.** Agenter skal aldri kjøre `git add`, `git commit`, `git push`, `git reset --hard`, `git checkout -b` / branch-bytting, `git merge`, `git rebase`, `git tag`, `git stash`, `git clean` eller annet som endrer repotilstand eller historikk.
- **git-kommandoer som leser (ikke muterer) er greit**, f.eks. `git status`, `git diff`, `git log`, `git show`, `git blame`, `git branch --list`, `git remote -v`, `git ls-files`. `git fetch` regnes også som trygt — det oppdaterer kun remote-tracking refs og rører ikke working tree eller lokale branches.
- **Unntak ved refaktorering:** `git mv` og `git rm` er greit for å la git følge med på at filer flyttes eller fjernes.
- Hvis en endring ser ut til å kreve en muterende git-operasjon utover unntakene over, beskriv hva som bør gjøres og la brukeren kjøre det.
- **Foretrekk innebygde shell-/CLI-kommandoer framfor å opprette nye script-filer** (`.sh`, `.py`, …). Engangsoppgaver løses i terminalen med `bash`, `rg`, `find`, `jq`, `python3 -c "…"` osv. Opprett nye script kun når noe er ment å gjenbrukes, og legg det da i et passende sub-repo.
- **Bruk `python3`, ikke `python`.** På utvikler-Macene ligger `python3` på PATH mens `python` ofte ikke gjør det — ikke bruk tid på å lete etter en `python`-binær.

## Repostruktur

### Kotlin-backendtjenester (deployes til NAIS)

Følg [`AGENTS-backend.md`](AGENTS-backend.md).

| Modul | Beskrivelse | Sub-repo AGENTS.md |
|---|---|---|
| `tiltakspenger-arena` | Arena-integrasjon | [lenke](tiltakspenger-arena/AGENTS.md) |
| `tiltakspenger-datadeling` | Datadeling mot andre systemer | [lenke](tiltakspenger-datadeling/AGENTS.md) |
| `tiltakspenger-journalposthendelser` | Konsumerer journalposthendelser | [lenke](tiltakspenger-journalposthendelser/AGENTS.md) |
| `tiltakspenger-meldekort-api` | Meldekort-API | [lenke](tiltakspenger-meldekort-api/AGENTS.md) |
| `tiltakspenger-pdfgen` | PDF-genereringstjeneste med maler for PDF-generering | [lenke](tiltakspenger-pdfgen/AGENTS.md) |
| `tiltakspenger-saksbehandling-api` | Saksbehandlings-API (kjerne-API for saksbehandling) | [lenke](tiltakspenger-saksbehandling-api/AGENTS.md) |
| `tiltakspenger-soknad-api` | Søknads-API | [lenke](tiltakspenger-soknad-api/AGENTS.md) |
| `tiltakspenger-tiltak` | Tiltak-integrasjon | [lenke](tiltakspenger-tiltak/AGENTS.md) |

### Delte Kotlin-biblioteker

Følg [`AGENTS-backend.md`](AGENTS-backend.md) i tillegg til de libs-spesifikke arkitekturnotatene.

| Modul | Beskrivelse | Sub-repo AGENTS.md |
|---|---|---|
| `tiltakspenger-libs` | Delt Kotlin-bibliotek, publiseres til GitHub Packages (deployes ikke til NAIS) | [lenke](tiltakspenger-libs/AGENTS.md) |

### TypeScript-frontender

Følg [`AGENTS-frontend.md`](AGENTS-frontend.md).

| Modul | Beskrivelse                      | Sub-repo AGENTS.md |
|---|----------------------------------|---|
| `tiltakspenger-meldekort` | Meldekort-UI for innbygger (Vite-klient + Express-server, pnpm workspace) | [lenke](tiltakspenger-meldekort/AGENTS.md) |
| `tiltakspenger-meldekort-microfrontend` | Meldekort-mikrofrontend på nav.no (Astro) | [lenke](tiltakspenger-meldekort-microfrontend/AGENTS.md) |
| `tiltakspenger-saksbehandling` | Saksbehandlings-UI (Next.js)     | [lenke](tiltakspenger-saksbehandling/AGENTS.md) |
| `tiltakspenger-soknad` | Søknads-UI for innbygger (Next.js) | [lenke](tiltakspenger-soknad/AGENTS.md) |

### Annet

| Modul | Beskrivelse | Sub-repo AGENTS.md |
|---|---|---|
| `tiltakspenger-iac` | Infrastruktur som kode | [lenke](tiltakspenger-iac/AGENTS.md) |

## Arbeid på tvers av sub-repoer

Fordi hvert sub-repo er sitt eget git-repo, skal agenter:

1. **Finne sub-repoer** ved å kjøre `list_dir` på dette rotnivået, ikke ved å stole på `file_search` for `**/*`.
2. **Lese AGENTS.md fra sub-repoet** du jobber i (alle sub-repoer har minst en stubb-AGENTS.md som lenker hit). Kombiner reglene der med reglene i denne filen samt relevant backend-/frontend-fil.
3. **Søke inne i et sub-repo** ved å `cd`-e inn i det og kjøre `rg` / `grep -r` / `find` direkte, eller ved å gi absolutte stier til `read_file` og `list_dir`. Workspace-verktøyene `file_search` / `grep_search` finner ikke filer inne i sub-repoer.
4. **Kjøre bygg og tester inne i sub-repoet** — hvert sub-repo har sin egen Gradle wrapper / `package.json` / hjelpeskripter.
5. Når en selv-oppdatering er på sin plass: oppdater filen som er nærmest endringen — `AGENTS.md` for tverrgående endringer, `AGENTS-backend.md` / `AGENTS-frontend.md` for type-spesifikke, og sub-repoets `AGENTS.md` for repo-spesifikke.

## Delte konvensjoner

Noen ting gjelder **både** for backend og frontend:

- **4 mellomrom som innrykk** i kildekode (Kotlin og Prettier er konfigurert for dette).
- **Vi bruker norsk bokmål for å beskrive domenet.** Begreper som `Sak`, `Søknad`, `Periode`, `Behandling`, `Vedtak`, `Meldekort`, `Saksbehandler`, `Tiltak` og selve programnavnet `tiltakspenger` brukes på norsk overalt — i kode, typer, API-er, dokumentasjon og kommentarer. Lovverk og forvaltningsspråk er på norsk og styrer terminologien. **Ikke** oversett til engelske ekvivalenter som "case management", "application", "decision", "employment scheme benefits" e.l. — heller ikke i AGENTS-filer eller beskrivelser. Tekniske termer (`route`, `service`, `repository`, `DTO`, …) og rammeverknavn (Kotlin, Next.js, …) er på engelsk.
- **Ingen personopplysninger/stedlokaliserende i vanlige logger.** Backend bruker `Sikkerlogg` fra `tiltakspenger-libs:logging`; frontend skal aldri logge personsensitiv/identifiserende informasjon, dette gjelder også fødselsnummer eller lignende til konsoll / observability-verktøy.
- **Auth via NAIS Texas** på backend (`tiltakspenger-libs:texas`) og **@navikt/oasis** på frontend.
- **Alle tjenester kjører på NAIS** — følg NAIS-konvensjoner for konfig og hemmeligheter.
- **Lokal utvikling** orkestreres via `docker-compose.yml` i monorepo-roten (og `docker-compose-soknad.yml` for søknad).

