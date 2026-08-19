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
- **Les tilbake etter skriving mot eksterne systemer.** En skriving er ikke ferdig før verdien er lest tilbake fra systemet.At kallet returnerte en id betyr bare at det ble tatt imot — ikke at feltet fikk verdien du ville ha. Og et negativt søkeresultat er ikke bevis før du vet at søket kunne funnet noe: en tom liste og en avkortet liste ser helt like ut. Har du en id, et nummer eller en url, gjør et **punktoppslag** på den (`gh issue view <nr> --repo navikt/<repo>`, `gh run view <id>`, Tempos `/api/traces/<trace_id>`) — et punktoppslag kan ikke avkortes, og det skiller «finnes ikke» fra «fant ikke». Må du bruke en liste, se [Lesegrenser og stille avkorting](#lesegrenser-og-stille-avkorting).
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
- **Rydd i issuen mens du jobber med den, ikke etterpå.** En issue skal til enhver tid speile virkeligheten. Retter en avklaring premisset — utdaterte navn, verdier eller antakelser i den opprinnelige rapporten — så oppdater selve beskrivelsen i stedet for å la feilen bli stående og villede; en rå stacktrace eller et Trello-utdrag hører hjemme bak `<details>`, ikke som hele innholdet. Skriv avklaringer inn som kommentar når de tas, kryss av delmål underveis, hold labels og assignee riktige, og si eksplisitt hva som er forkastet og hvorfor (draft-PR-er, tilnærminger som ikke bar). Da slipper neste person å rekonstruere historikken fra commits.
- **Spør før du lukker.** Når arbeidet er merget, deployet og verifisert, be den ansvarlige om en kort bekreftelse på at issuen kan oppdateres og lukkes — ikke lukk på eget initiativ. Lukk med `--reason completed`, og legg igjen en avsluttende kommentar som svarer ut sjekklisten i issuen: hva ble gjort, hvilken commit, hva avklaringene landet på, og hva som eventuelt gjenstår som ny issue.
- **`gh` CLI mot riktig repo.** Bruk `gh issue create/edit --repo navikt/<sub-repo>`. `gh issue edit` tar rent issue-nummer (ikke `owner/repo#num`). For å bevare backticks/kodeblokker, bruk `--body-file` framfor `--body`.
- **Les tilbake det du skrev.** Etter `gh issue create/edit`, `gh project item-add/item-edit` eller en labelendring: hent verdien tilbake fra issuen med et punktoppslag før du melder at den er satt. Statusen i team-boardet leses fra issuen selv, ikke fra prosjektlista: `gh issue view <nr> --repo navikt/<repo> --json projectItems -q '.projectItems[] | "\(.title)=\(.status.name)"'`. Tom liste der betyr at issuen ikke ligger i noe prosjekt — et ekte svar, i motsetning til et uteblitt treff i en avkortet liste. Bruk aldri `gh project item-list` for å bekrefte én skriving: den kutter stille ved `--limit` (se [Lesegrenser og stille avkorting](#lesegrenser-og-stille-avkorting)), og siden prosjektet inneholder items fra alle repoene er et issue-nummer alene tvetydig og må pares med `content.repository`.
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
| `tiltakspenger-interndokumentasjon` | Intern dokumentasjon som ikke hører til én kodebase (privat repo, ingen kode). Ett område i dag: minimum kontrollrammeverk økonomisystem | [lenke](tiltakspenger-interndokumentasjon/AGENTS.md) |
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
- **Nais-prober følger en felles mal.** Alle apper definerer `startup`, `liveness` og `readiness` med verdiene under — kun probe-stiene er app-spesifikke. Startup-proben gir appen inntil ~5 minutter på å starte (kald autoskalert node, image pull, Flyway/JVM-oppvarming) uten at liveness dreper den; liveness og readiness aktiveres først når startup-proben har lyktes. **Avvik fra malen skal begrunnes med en kommentar ved probe-blokken i appens nais-manifest** (eksempel: `tiltakspenger-soknad`, som mangler helse-endepunkter). Bakgrunn: [Nais-spec for `startup`](https://doc.nais.io/workloads/application/reference/application-spec/#startup) og [Kubernetes-dokumentasjonen om prober](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/).

    ```yaml
    startup:
      path: <appens isAlive-sti>
      initialDelay: 5
      periodSeconds: 5
      failureThreshold: 60 # 5 + 60 × 5 s ≈ 5 min oppstartsvindu
      timeout: 3
    liveness:
      path: <appens isAlive-sti>
      periodSeconds: 10
      failureThreshold: 3
      timeout: 3
    readiness:
      path: <appens isReady-sti>
      periodSeconds: 5
      failureThreshold: 1
      timeout: 3
    ```

- **Lokal utvikling** orkestreres via `docker-compose.yml` i monorepo-roten (og `docker-compose-soknad.yml` for søknad). Backend-appenes `LokalMain` starter selv databasetjenesten sin fra denne fila hvis den ikke allerede kjører, via `startLokalPostgres` i `tiltakspenger-libs:lokal-oppstart` — så `./up.sh` er ikke lenger et forkrav for å kjøre en enkelt app. Foreløpig er det `tiltakspenger-meldekort-api` og `tiltakspenger-soknad-api` som gjør dette; resten av flåten kan ta det i bruk med samme kall. Ligger tjenesten i en annen compose-fil enn `docker-compose.yml`, sier du fra med `composefilnavn` (søknad peker på `docker-compose-soknad.yml`). Rømningsluke for de som ikke vil ha compose-containerne: `LOKAL_DB_MODUS=testcontainers`.
- **Port 8085 er reservert for `nais login`** (callback-porten til nais CLI) og skal aldri bindes av lokale tjenester, compose-oppsett eller scripts.
- **Merk brancher og commits med et nda-mål.** Branch-navn og commit-meldinger bør inneholde nøkkelordet for målet arbeidet støtter, f.eks. `tp-bau` for Navs felles mål «Sikker og stabil drift» — branch `tp-bau/fjern-ubrukt-felt`, commit-melding som ender på `tp-bau`. [navikt/nda](https://github.com/navikt/nda) kobler deployments til teamets tertialtavle ved å matche nøkkelordene i commit-meldingene, case-ufølsomt og hvor som helst i teksten; en deploy uten mål-nøkkelord blir stående ukoblet. Målene og nøkkelordene ligger på tertialtavla i nda, og `tp-bau` er standardvalget når arbeidet ikke hører til et mer spesifikt mål. Agenter committer ikke selv, men skal foreslå branch-navn og commit-meldinger med nøkkelordet på plass.
- **GitHub Actions-workflows skal være så like som mulig på tvers av repoene.** Når du endrer CI i ett repo, vurder om de andre repoene bør endres tilsvarende, slik at oppsettet konvergerer i stedet for å sprike. Konkret:
    - Workflowen som bygger og deployer til prod ved push til `main` heter **`Build and deploy`** i alle repoer (også der det egentlig er en publisering, som `tiltakspenger-libs`, eller en kombinert dev+prod-deploy, som `tiltakspenger-meldekort-microfrontend`). Felles navn gjør at verktøy kan hente «siste utrulling» likt på tvers — se `script/status.sh`.
    - Den manuelle deployen til dev (`workflow_dispatch`) er det bevisste unntaket og trenger ikke følge navnekonvensjonen.
    - Hold også steg, action-versjoner og struktur mest mulig identiske mellom repoene; avvik bør være begrunnet i reelle forskjeller (f.eks. Gradle vs. pnpm, fss vs. gcp).
    - **Delte reusable workflows** bor i metarepoets [`.github/workflows/`](.github/workflows/README.md) og kalles fra repoene med `workflow_call` — les README-en der (caller-eksempel, secrets-/permissions-konvensjoner) før du endrer eller dupliserer CI-logikk, og foretrekk å utvide en delt workflow fremfor å kopiere den inn i et enkelt-repo.
    - **Caller-filene skal være like på tvers av repoene** — samme filnavn, `name:` og struktur; kun reelle repo-forskjeller (f.eks. java-versjon) får avvike. Endrer du en caller i ett repo, oppdater de andre tilsvarende.

## Lesegrenser og stille avkorting

Alle listekommandoene vi bruker mot GitHub og Grafana-stacken har en øvre grense som treffer uten at det sies fra.
Du får de første N radene og exit 0, og en avkortet liste ser nøyaktig ut som en tom.
Derfor må «fant ingenting» aldri rapporteres som «det finnes ingenting» før én av disse tre holder:

1. **Punktoppslag framfor liste.** Har du id, nummer eller url, hent ressursen direkte — et punktoppslag kan ikke avkortes, og svarer 404 der en liste bare ville vært tom.
2. **Totalen svaret selv oppgir.** Flere av APIene bærer fasiten i samme JSON; sammenlign den med antall returnerte rader.
3. **Antall mot grensen.** Får du nøyaktig så mange rader som grensen tillater, anta at lista er avkortet — færre rader enn grensen er derimot bevis på at den er komplett.

Målt 2026-08-06:

| Lesesti | Default-grense | Total i svaret? | Merknad |
| --- | --- | --- | --- |
| `gh issue list` | 30 rader, og bare `--state open` | Nei — ren JSON-array | Lukkede issues er usynlige til du ber om `--state all` |
| `gh pr list` | 30 rader, bare åpne | Nei | Samme filterfelle som over |
| `gh run list` | 20 rader | Nei | De 20 nyeste på tvers av alle workflowene; avgrens med `--workflow` |
| `gh repo list <org>` | kutter ved `--limit` uansett verdi, og utelater arkiverte | Nei | `--limit 5000` mot `navikt` ga nøyaktig 5000 rader — altså avkortet |
| `gh project item-list` | 30 items | **Ja — `.totalCount`** | Prosjekt 227 har over 500 items |
| `gh api <rest-sti>` | `per_page=30` | Nei (`Link`-header synlig med `-i`) | `--paginate` henter alle sidene |
| `gh api /search/...` | `per_page=30`, hardt tak på 1000 treff | **Ja — `total_count` og `incomplete_results`** | Eneste pålitelige måte å telle repoer i `navikt` på |
| Loki `query_range` | 100 linjer, og vindu = siste time uten `start`/`end` | **Ja — `stats.summary.totalPostFilterLines`** | `direction=backward` er default, så avkortingen fjerner de **eldste** linjene |
| Tempo `/api/search` | 20 traces, maks 3 spans per trace | **Ja — `metrics.completedJobs` mot `totalJobs`** | Målt 212 av 1652 jobber fullført; søket er et utvalg, ikke en telling |
| Mimir `query` (instant) | ser bare 5 minutter bakover fra `time` | Nei | En metrikk som ikke finnes og en metrikk uten ferske samples gir begge tomt svar med `status: success` |
| Mimir `query_range` | retensjon på ~30 dager | Nei | En spørring om 90 dager ga 30 dager med `status: success` og ingen `warnings` |

Loki-linja fortjener en presisering, siden både grensen og tidsvinduet kan skjule treff hver for seg.
Uten `limit` får du 100 linjer, uten `start`/`end` får du bare siste time, og fordi nyeste linje kommer først er det de eldste treffene som forsvinner.
Leter du etter en hendelse tidlig i vinduet, er det nettopp den som blir kuttet bort.
Sammenlign `totalPostFilterLines` med `totalEntriesReturned` i svaret: matchet flere linjer enn du fikk, er resultatet avkortet.

## Observability (Loki, Tempo, Mimir)

Alle appene har OTel-autoinstrumentering via NAIS. `trace_id`/`span_id` injiseres automatisk i loggene og propageres mellom tjenestene (`traceparent`-header) — **ikke** legg på manuell span-instrumentering eller egne korrelasjons-id-er uten god grunn. Hvordan id-ene henger sammen er beskrevet i README-seksjonen «Feilsøking med logger og traces».

Grafana-stacken kan spørres direkte via API (krever naisdevice: `nais device status`, koble til med `nais device connect`). Send alltid header `X-Scope-OrgID: tenant` og en beskrivende `User-Agent`:

- **Loki** (logger): `https://loki.nav.cloud.nais.io/loki/api/v1/query_range`
- **Tempo** (traces): `https://tempo.<env>.nav.cloud.nais.io/api/search` og `/api/traces/<trace_id>` (env f.eks. `prod-gcp`)
- **Mimir** (metrikker, PromQL): `https://mimir.nav.cloud.nais.io/prometheus/api/v1/query`

Gotchas og feilsøkingsheuristikker:

- Cluster-labelen er `k8s_cluster_name="prod"` eller `"dev"` (ikke `prod-gcp`), namespace `tpts`. Bruk alltid `start`/`end`. **`prod` dekker ikke alle appene:** `tiltakspenger-arena` kjører på fss og har `k8s_cluster_name="prod-fss"`. Sveiper du over hele flåten, bruk `=~"prod.*"` — ellers faller arena stille ut av svaret. Verdiene som finnes for oss er `dev`, `dev-fss`, `prod` og `prod-fss` (målt 2026-08-06).
- **Hvilken label appen har, avhenger av metrikken.** I Loki heter den `service_name`. I Mimir bruker de skrapede plattformmetrikkene (`up`, `kube_*`) `app`, mens `traces_spanmetrics_*` — som genereres fra traces — bruker `service_name` og har verken `app` eller `namespace`. Å bruke feil av dem gir et tomt, vellykket svar. Er du i tvil, spør Mimir hvilke serier som finnes framfor å gjette: `/api/v1/series?match[]=up{namespace="tpts"}`.
- **Spør om et tall når spørsmålet er et tall.** Skal du vite *hvor mange* eller *om det finnes noe i det hele tatt*, hent en metrikk framfor logglinjer — linjegrensen på 100 gjelder ikke metrikkspørringer, og du får eksakt svar i ett kall: `sum by (level) (count_over_time({service_name="<app>", k8s_cluster_name="prod"} | json [1h]))`. Målt 2026-08-06 ga én time med sb-api-logger 9392 linjer gjennom en metrikkspørring, mot 100 returnerte linjer ved vanlig uthenting. At det ikke kommer noen `ERROR`-rad i et slikt svar **er** et bevis på at det ikke fantes feil i vinduet — i motsetning til et linjesøk som ikke fant noen. Hent rå linjer først når du har snevret inn og faktisk skal lese teksten.
- **Slå opp hva som finnes før du konkluderer med at noe mangler.** Et tomt svar skyldes like ofte feilstavet app- eller metrikknavn som at det ikke finnes data. Oppslagene er raske og svarer entydig: `/loki/api/v1/label/service_name/values?query={service_namespace="tpts"}` lister appene våre som faktisk logger (15 inkl. `kube-events` og `nais-ingress`; uten `query`-selektoren får du alle 2424 i tenanten), `/loki/api/v1/label/k8s_cluster_name/values?query={service_name="<app>"}` sier hvilket cluster appen kjører i, `/prometheus/api/v1/label/__name__/values?match[]={namespace="tpts"}` lister alle metrikknavnene våre (659), og `/prometheus/api/v1/series?match[]=<selector>` med `start`/`end` svarer på om en serie fantes i vinduet — noe instant-spørringen ikke kan, siden den bare ser 5 minutter bakover.
- **Namespace heter ikke det samme i de to.** I Mimir er det `namespace="tpts"`; i Loki er det `service_namespace="tpts"` (`namespace` og `k8s_namespace_name` finnes ikke der og gir tomt svar). Strømmenes labelsett i Loki er `service_name`, `service_namespace`, `k8s_cluster_name`, `k8s_container_name`, `k8s_node_name`, `k8s_pod_name` og `detected_level` — alt annet må hentes ut av selve logglinja med `| json`.
- **Ingen av spørringene sier fra når de kutter.** Loki gir 100 linjer og siste time som default og fjerner de eldste treffene først; Mimirs instant-spørring ser bare 5 minutter bakover; `query_range` klipper stille til retensjonsvinduet på ~30 dager. Grensene og hvordan du oppdager dem står i [Lesegrenser og stille avkorting](#lesegrenser-og-stille-avkorting) — les den før du konkluderer med at noe ikke finnes i loggene eller metrikkene.
- **Tempo-søk er et utvalg, ikke en telling.** `/api/search` gir maks 3 spans per trace (juster med `spss`), og ferske spans mangler ofte i attributtfiltrerte søk selv om de finnes. Trenger du fasit, hent hele tracen: `/api/traces/<id>` med full 32-tegns trace_id. Én hel trace er også raskeste verifisering etter en deploy — den viser rekkefølge, varighet og status gjennom hele kjeden.
- Filtrer alltid på `kind`. Uten `{resource.service.name="<app>" && kind=server}` treffer søket jobb- og DB-spans, og det ser ut som appen mangler HTTP-spans.
- Mangler en app sine spans i én konkret trace mens den ellers har server-spans, nådde requesten sannsynligvis aldri appen — sjekk rollout-aktivitet i tidsrommet (flere ReplicaSets samtidig / «Application started» i Loki).
- Traces er en uavhengig kontrollkilde når du skal skille «feilene stoppet» fra «loggingen stoppet»: spans lages av OTel-agenten uansett hva appene logger. Finn timeouts uavhengig av loggene med `{resource.service.name="<app>" && kind=client && duration>5s}` og sammenlign antall med feillinjene i Loki.
- **Persentiler:** Tempos `/api/metrics/query_range` (`| quantile_over_time(duration, .5, .9, .99)`) tar **maks 3 timer** per spørring. For dager/uker: `traces_spanmetrics_latency_*` i Mimir. `le`-bøttene der er i sekunder og stopper på 5 s, så en p99 over det kommer ut som `+Inf` — suppler med andel over terskel: `1 - (increase(...bucket{le="5"}[30d]) / increase(...count[30d]))`.
- **Spanmetrics skiller ikke utgående kall.** Alle klient-spans havner under `span_name="POST"`, så nedstrømstjenester og Texas-sidecaren (millisekunder) blandes og drar p50 kunstig ned. Splitt per mål må hentes fra Tempo med `span.url.full`-filter.
- Dimensjonerer du timeouts, er **server-spanet på appens egen rute** tallet som teller — det er det konsumenten venter på, og det inkluderer haleoverhead (GC, kald pod, kø) som ikke finnes i noen utgående p99.
- macOS: bruk `date -v-1H +%s`, ikke GNU-syntaksen `date -d '1 hour ago'`.
- `gcloud`-tokenet utløper og må fornyes interaktivt, så `kubectl` kan falle bort midt i en økt. Loki/Tempo/Mimir over API virker uansett — bruk dem til logg- og trafikkoppfølging etter deploy.
- Alerts og Slack-varsler: se README-seksjonen «Alarmer og Slack-varsler». Viktigste feller: `ALERTS{namespace="tpts"}` i Mimir blander dev og prod uten filter på `k8s_cluster_name`; dev- og prod-alerts har identisk tekst men går til hhv. `#tp-varsel-dev` og `#tp-varsel-prod`; CI-varslene i `#tp-varsel` bruker en helt annen webhook (GitHub-secret `SLACK_VARSEL_WEBHOOK_URL`) enn Alertmanager.
