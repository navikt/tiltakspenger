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
- **Delte agent-skills legges i `skills/`, ikke i verktøy-spesifikke kataloger.** Gjenbrukbare arbeidsflyter skrives som en verktøy-uavhengig `SKILL.md` (åpent «Agent Skills»-format) under `skills/<navn>/` — den kanoniske kopien hele teamet deler. Ikke lag verktøy-spesifikke ting (f.eks. filer som bare bor i `~/.copilot/skills/` eller i andre agentverktøys egne kataloger) som varig kilde; la heller verktøyet peke hit via symlink (se [`skills/README.md`](skills/README.md)). Oppdater `skills/README.md`-tabellen når du legger til en ny skill. Nav-felles agents/skills/instructions (installert på brukernivå via [nav-pilot](https://ki-utvikling.nav.no/nav-pilot) fra [navikt/copilot](https://github.com/navikt/copilot)) og Nav-godkjente MCP-servere ([mcp-registry.nav.no](https://mcp-registry.nav.no)) er dokumentert på [ki-utvikling.nav.no](https://ki-utvikling.nav.no) — se også README-seksjonen «KI-verktøy (Copilot, agents, skills og MCP)».
- **Verifiser Markdown-filer etter endring.** Når du oppretter eller endrer `.md`-filer (særlig tabeller), kjør et tilgjengelig verktøy for å sjekke formatteringen — f.eks. `markdownlint`/`markdownlint-cli2`, `prettier --check`, eller `npx` av disse — og rett opp feil. Tabeller må være gyldig GitHub-flavored Markdown (justerte kolonner / korrekt antall `|`), siden bl.a. IntelliJ flagger feilformaterte tabeller. Finnes ingen verktøy, kontroller formatteringen manuelt.

## Personlig task-tracking (`TASKS.md`)

Personlige/lokale oppgaver og backlog som ikke (ennå) hører hjemme i en issue-tracker, lagres i `TASKS.md` i monorepo-roten. Filen er `.gitignore`-t (committes aldri) og er per-utvikler.

- **Agentens egen sesjons-backlog er ikke varig.** Verktøy som holder tasks i en per-sesjon-database mister dem for nye sesjoner. Skriv derfor gjenstående oppgaver til `TASKS.md` slik at de overlever på tvers av sesjoner, og les `TASKS.md` ved oppstart for å gjenoppta kontekst.
- **Kun gjenstående oppgaver listes.** Når noe er ferdig, fjern det (eller flytt til en kort «Ferdig»-logg nederst om ønskelig).
- Bruk Markdown-checkbokser (`- [ ]`) gruppert per tema/repo, med nok kontekst (fil, linje, PR-nummer) til at oppgaven kan utføres uten å lete.

## GitHub-issues og epics

`TASKS.md` er for det personlige/uformelle. Når arbeid skal deles med teamet og spores over tid, hører det hjemme som GitHub-issues. Regler:

- **Tverrgående arbeid = epic i monorepoet.** Oppgaver som berører flere sub-repoer (f.eks. en felles migrering, en delt konvensjon eller et bibliotekbytte) skal ha en **epic-issue i monorepoet (`navikt/tiltakspenger`)**. Epicen eier det generelle: mål, mønster, konvensjoner og en sporingsliste (checkbokser) over de repo-spesifikke issuene.
- **Repo-spesifikke issues i hvert sub-repo.** Det som er konkret for ett sub-repo (hvilke filer/klienter, rekkefølge, verifisering) ligger i en issue i **det** sub-repoet, og lenker opp til epicen. Ikke dupliser det generelle inn i hvert child-issue — pek til epicen i stedet.
- **Kryss-lenk begge veier.** Epicen lister child-issuene (som avkrysningsliste), og hvert child-issue starter med «Del av epic navikt/tiltakspenger#N».
- **Hold epicen som fasit.** Når noe fullføres eller endres, oppdater epicens sporingsliste og flytt/fjern tilsvarende punkter i `TASKS.md` slik at de ikke divergerer. `TASKS.md` bør peke til epicen framfor å gjenta detaljene.
- **`gh` CLI mot riktig repo.** Bruk `gh issue create/edit --repo navikt/<sub-repo>`. `gh issue edit` tar rent issue-nummer (ikke `owner/repo#num`). For å bevare backticks/kodeblokker, bruk `--body-file` framfor `--body`.
- **Labels.** Merk issues med relevante labels (f.eks. `enhancement`, `bug`, `documentation`) slik at de kan filtreres på tvers. Bruk det eksisterende label-settet i repoet framfor å finne på nye ad-hoc; trenger du en ny felles label, opprett den likt i alle repoene (jf. konvergens-tankegangen for CI).
- **Lenk PR til issue.** PR-er som løser en issue skal referere den i beskrivelsen med `Fixes #N` / `Closes #N` (samme repo) eller `Fixes navikt/<repo>#N` (kryss-repo) slik at issuen lukkes automatisk ved merge. For deloppgaver under en epic: lenk til epicen, men la epicen stå åpen til alle child-issues er ferdige.

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
| `skills/` | Delte, verktøy-uavhengige agent-skills (åpent `SKILL.md`-format) som hele teamet kan bruke på tvers av agentverktøy | [lenke](skills/README.md) |

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
- **Port 8085 er reservert for `nais login`** (callback-porten til nais CLI) og skal aldri bindes av lokale tjenester, compose-oppsett eller scripts.
- **GitHub Actions-workflows skal være så like som mulig på tvers av repoene.** Når du endrer CI i ett repo, vurder om de andre repoene bør endres tilsvarende, slik at oppsettet konvergerer i stedet for å sprike. Konkret:
    - Workflowen som bygger og deployer til prod ved push til `main` heter **`Build and deploy`** i alle repoer (også der det egentlig er en publisering, som `tiltakspenger-libs`, eller en kombinert dev+prod-deploy, som `tiltakspenger-meldekort-microfrontend`). Felles navn gjør at verktøy kan hente «siste utrulling» likt på tvers — se `script/status.sh`.
    - Den manuelle deployen til dev (`workflow_dispatch`) er det bevisste unntaket og trenger ikke følge navnekonvensjonen.
    - Hold også steg, action-versjoner og struktur mest mulig identiske mellom repoene; avvik bør være begrunnet i reelle forskjeller (f.eks. Gradle vs. pnpm, fss vs. gcp).
    - **Delte reusable workflows** bor i metarepoets [`.github/workflows/`](.github/workflows/README.md) og kalles fra repoene med `workflow_call` — les README-en der (caller-eksempel, secrets-/permissions-konvensjoner) før du endrer eller dupliserer CI-logikk, og foretrekk å utvide en delt workflow fremfor å kopiere den inn i et enkelt-repo.

## Observability (Loki, Tempo, Mimir)

Alle appene har OTel-autoinstrumentering via NAIS. `trace_id`/`span_id` injiseres automatisk i loggene og propageres mellom tjenestene (`traceparent`-header) — **ikke** legg på manuell span-instrumentering eller egne korrelasjons-id-er uten god grunn. Hvordan id-ene henger sammen er beskrevet i README-seksjonen «Feilsøking med logger og traces».

Grafana-stacken kan spørres direkte via API (krever naisdevice: `nais device status`, koble til med `nais device connect`). Send alltid header `X-Scope-OrgID: tenant` og en beskrivende `User-Agent`:

- **Loki** (logger): `https://loki.nav.cloud.nais.io/loki/api/v1/query_range`
- **Tempo** (traces): `https://tempo.<env>.nav.cloud.nais.io/api/search` og `/api/traces/<trace_id>` (env f.eks. `prod-gcp`)
- **Mimir** (metrikker, PromQL): `https://mimir.nav.cloud.nais.io/prometheus/api/v1/query`

Gotchas og feilsøkingsheuristikker:

- Loki-labelen for cluster er `k8s_cluster_name="prod"` (ikke `prod-gcp`). Appene identifiseres med `service_name`, namespace er `tpts`. Bruk alltid `start`/`end` i spørringene.
- Tempo-søk uten `kind`-filter treffer gjerne jobb-/DB-spans og kan gi inntrykk av at en app mangler HTTP-server-spans. Filtrer med `{resource.service.name="<app>" && kind=server}` før du konkluderer.
- Mangler en app sine spans i én konkret trace mens den ellers har server-spans, nådde requesten sannsynligvis aldri appen — sjekk rollout-aktivitet i tidsrommet (flere ReplicaSets samtidig / «Application started» i Loki).
- Traces er en uavhengig kontrollkilde når du skal skille «feilene stoppet» fra «loggingen stoppet»: spans lages av OTel-agenten uansett hva appene logger. Finn timeouts uavhengig av loggene med TraceQL `{resource.service.name="<app>" && kind=client && duration>9s}` og sammenlign antall med feillinjene i Loki.
- Tempo-søke-API-et kan sporadisk svare helt tomt — retry 2–3 ganger med noen sekunders pause før du konkluderer med «ingen treff». `/api/traces/<id>` krever full 32-tegns trace_id (ikke forkortet).
- macOS: bruk `date -v-1H +%s`, ikke GNU-syntaksen `date -d '1 hour ago'`.
