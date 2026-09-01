# tiltakspenger

Startpunkt (metarepo) for tiltakspenger

## Komme i gang

### Oppsett av meta-repo

[meta](https://github.com/mateodelnorte/meta) brukes til å sette opp
repositories for alle repoene.

Enn så lenge må du sørge for å ha `npm` installert (`brew install node`).

```
npm install meta -g --no-save
```

Merk! meta foran vanlig clone-kommando:

```
meta git clone git@github.com:navikt/tiltakspenger.git
```

Nå kan git brukes som normalt for hvert repo.


Dersom noen har lagt til et nytt repo som du ikke har, kan du oppdatere med:
```meta git update```

For å legge til et nytt repo kan man skrive

```
meta project import tiltakspenger-whatnot git@github.com:navikt/tiltakspenger-whatnot
```

Se [meta](https://github.com/mateodelnorte/meta) for flere kommandoer.

Dersom du nå åpner `build.gradle` med `Open` (som Project) i IntelliJ så får du alle komponentene inn i ett
IntelliJ-oppsett.

Repoene som er inkludert i dette meta-repoet er

- [tiltakspenger-iac](https://github.com/navikt/tiltakspenger-iac)
- [tiltakspenger-libs](https://github.com/navikt/tiltakspenger-libs)
- [tiltakspenger-arena](https://github.com/navikt/tiltakspenger-arena)
- [tiltakspenger-saksbehandling-api](https://github.com/navikt/tiltakspenger-saksbehandling-api)
- [tiltakspenger-tiltak](https://github.com/navikt/tiltakspenger-tiltak)
- [tiltakspenger-saksbehandling](https://github.com/navikt/tiltakspenger-saksbehandling)
- [tiltakspenger-soknad-api](https://github.com/navikt/tiltakspenger-soknad-api)
- [tiltakspenger-pdfgenrs](https://github.com/navikt/tiltakspenger-pdfgenrs)
- [tiltakspenger-soknad](https://github.com/navikt/tiltakspenger-soknad)
- [tiltakspenger-datadeling](https://github.com/navikt/tiltakspenger-datadeling)
- [tiltakspenger-meldekort](https://github.com/navikt/tiltakspenger-meldekort)
- [tiltakspenger-meldekort-api](https://github.com/navikt/tiltakspenger-meldekort-api)
- [tiltakspenger-meldekort-microfrontend](https://github.com/navikt/tiltakspenger-meldekort-microfrontend)
- [tiltakspenger-journalposthendelser](https://github.com/navikt/tiltakspenger-journalposthendelser)
- [tiltakspenger-interndokumentasjon](https://github.com/navikt/tiltakspenger-interndokumentasjon) (privat — intern dokumentasjon, ingen kode)

### Lokal kjøring av verdikjeden

Meta-repoet kommer med et docker-compose oppsett som kan benyttes for å kjøre opp
hele verdikjeden lokalt i Docker-containere, med noen unntak (`tiltakspenger-saksbehandling`,
`tiltakspenger-soknad` og `tiltakspenger-soknad-api`). Merk at `tiltakspenger-saksbehandling` kan kjøres opp
på siden av øvrige apper for å kunne teste frontend lokalt.

#### Bruk av docker-compose oppsett for saksbehandling

For enkel bruk av docker-compose-oppsett er det skrevet noen bash-script som ligger på
rot av dette repositoryet.

| script          | beskrivelse                                                                                                                                                                                                                                                        |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ./up.sh         | Script for å bygge og starte alle apper i docker-compose (se i [up.sh](https://github.com/navikt/tiltakspenger/blob/main/up.sh) for tilgjengelige options)                                                                                                         |
| ./up-min.sh     | Starter kun databasene for saksbehandling og meldekort, pdfgenrs-tjenesten og wiremock — kan benyttes når backend-appene kjøres separat og med mock auth (se i [up-min.sh](https://github.com/navikt/tiltakspenger/blob/main/up-min.sh) for tilgjengelige options) |
| ./down.sh       | Script for å stoppe alle apper i docker-compose                                                                                                                                                                                                                   |
| ./dkill.sh      | Script for å kjøre docker compose down, stopper og fjerner alle containere som eventuelt fortsatt kjører, og fjerner det tilhørende nettverket                                                                                                                     |
| ./slettAlt.sh   | Kjører "docker compose down --rmi all --volumes", i.e. sletter alt.                                                                                                                                                                                                |
| ./slettBaser.sh | Kjører "docker compose down --volumes", i.e. sletter basene.                                                                                                                                                                                                       |

#### Bruk av docker-compose oppsett for søknad

For kjøring av utviklingsmiljø for å jobbe med søknaden er det lagd et eget bash-script på
rot av dette repositoryet. Oppsettet dekker støttetjenestene rundt søknaden; selve søknads-api'et
kjøres fra IntelliJ, med `main()` i `LokalMain.kt`.

| script           | beskrivelse                                                                                                                                                                     |
|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ./up-soknad.sh   | Script for å bygge og starte alle apper i docker-compose-soknad (se i [up-soknad.sh](https://github.com/navikt/tiltakspenger/blob/main/up-soknad.sh) for tilgjengelige options) |
| ./down-soknad.sh | Script for å stoppe alle apper i docker-compose-soknad. Tar ingen options                                                                                                        |

### Status på bygg og pods

`script/status.sh` gir et hurtigblikk på tilstanden til hele verdikjeden:

- **Siste utrulling** (`Build and deploy`) på `main` for alle våre GitHub-repoer, hentet med `gh`.
- **Pod-status** i namespace `tpts` i dev og prod, hentet med `kubectl`.

```
./script/status.sh
```

Forventer kun at du er logget inn — `gh auth login` for GitHub og `nais kubeconfig`
for kubectl-contextene. Scriptet feiler på vanlig måte hvis du ikke er det.

> On-prem-klyngene (`*-fss`, f.eks. `tiltakspenger-arena`) krever at du har huket
> av `onprem-k8s-dev` / `onprem-k8s-prod` i naisdevice. Mangler tilgangen, gir
> scriptet en kort melding om det i stedet for å henge.

Oppførsel kan justeres med miljøvariabler, bl.a. `NAMESPACE`, `DEV_CLUSTERS`,
`PROD_CLUSTERS`, `KUBE_TIMEOUT` og `DEPLOY_WORKFLOW` — se toppen av scriptet.

### Import av data til lokale databaser

Det kan være praktisk å populere lokale databaser med data fra dev-miljøet. Du trenger `pg_dump` og `pg_restore` versjon 17 eller nyere fra [Postgres binaries](https://www.postgresql.org/download/).

#### Med script (anbefalt)

`script/import-dev-db-*.sh` gjør hele jobben under: starter den lokale databasen, setter opp proxy mot dev, dumper til en midlertidig mappe under `/tmp`, tømmer den lokale databasen og importerer. Argumentet er GCP-brukernavnet ditt (`gcloud config get-value account`):

```
./script/import-dev-db-saksbehandling.sh <GCP brukernavn>
./script/import-dev-db-meldekort.sh <GCP brukernavn>
```

> **NB:** scriptet dropper og oppretter den lokale databasen på nytt. Alt du har lokalt går tapt, og appen må ikke holde tilkoblinger åpne mens det kjører.

#### Fremgangsmåte manuelt
Eksempel for saksbehandling-api, se docker-compose for parametre for andre apper.

- Start den lokale databasen:
```
docker compose up -d postgresSaksbehandling
```

- Start en lokal proxy til dev-databasen du skal importere fra, med [nais cli](https://docs.nais.io/persistence/postgres/how-to/personal-access/). Se doc'en for førstegangsoppsett, senere kan du kjøre disse kommandoene:
```
kubectl config use-context dev-gcp
nais postgres proxy -p 5444 tiltakspenger-saksbehandling-api -t tpts -e dev-gcp --reason lols
```

- Kjør `pg_dump` for å dumpe dev-databasen:
```
pg_dump --host=localhost --port=5444 --dbname=saksbehandling --username=<GCP brukernavn> --format=directory --no-owner --no-privileges --exclude-extension='*' --file=<path til dump>
```

- Tøm den lokale databasen før import (se docker-compose for passord, antagelig `test`). Alternativt kan du slette containeren inkludert volume og kjøre opp på nytt.
```
psql --host=localhost --port=5433 --username=postgres --dbname=postgres -c 'DROP DATABASE IF EXISTS saksbehandling WITH (FORCE);' -c 'CREATE DATABASE saksbehandling;'
```

- Kjør `pg_restore` for å gjenopprette databasen lokalt:
```
pg_restore --host=localhost --port=5433 --dbname=saksbehandling --username=postgres --single-transaction --no-owner --no-privileges <path til dump>
```

## KI-verktøy (Copilot, agents, skills og MCP)

Nav har felles dokumentasjon og verktøy for KI-assistert utvikling:

- [ki-utvikling.nav.no](https://ki-utvikling.nav.no) — Navs dokumentasjonsside for KI-assistert utvikling: kom i gang, god praksis, retningslinjer, [nav-pilot](https://ki-utvikling.nav.no/nav-pilot) og [cplt](https://ki-utvikling.nav.no/cplt) (sandboxing av agenter). [Verktøy-katalogen](https://ki-utvikling.nav.no/verktoy) lister alle agents, skills, instructions, prompts og MCP-servere med installasjonshjelp. (Intern variant: min-copilot.ansatt.nav.no.)
- [navikt/copilot](https://github.com/navikt/copilot) — kildekoden til alt over: agents, instructions, prompts, skills og MCP-registeret ([apps/mcp-registry](https://github.com/navikt/copilot/tree/main/apps/mcp-registry)).
- [mcp-registry.nav.no](https://mcp-registry.nav.no) — register over Nav-godkjente MCP-servere (MCP Registry v0.1-API, se `/v0.1/servers`).

Nav-felles agents/skills/instructions installeres med [nav-pilot](https://ki-utvikling.nav.no/nav-pilot):

```
brew install navikt/tap/nav-pilot
nav-pilot install --user --all   # til ~/.copilot, gjelder alle repoer
```

Skillsene er i det åpne Agent Skills-formatet (`SKILL.md`) og kan gjenbrukes av andre
agentverktøy enn Copilot — f.eks. open source-verktøyet [OpenCode](https://opencode.ai)
via `nav-pilot export opencode`, eller et hvilket som helst verktøy som leser formatet
(symlink `~/.copilot/skills` inn i verktøyets skills-katalog). MCP-serverne i registeret
kan på samme måte legges inn i andre MCP-klienter.

Repoets egne, verktøy-uavhengige skills ligger i [`skills/`](skills/README.md).

Agentene skal kjøre isolert — se [kravet på ki-utvikling.nav.no](https://ki-utvikling.nav.no/nyheter/sandboxing-er-pakrevd-pa-nav-utstyr).
På macOS og Linux holder det å installere cplt.
For Windows, der cplt ikke finnes, ligger det en oppskrift med WSL2 i [`docs/ki-agenter/`](docs/ki-agenter/) som ikke er testet.

## Designsystem, skjemaer og datoer (Aksel)

Alle frontendene bruker Navs designsystem [Aksel](https://aksel.nav.no). Les «Retningslinjer» på komponentsiden, ikke bare props-tabellen — flere av de viktige valgene står bare i prosateksten og fremgår ikke av typene.

**Datoer** er området der vi har truffet flest fallgruver, og der kildene faktisk gir litt ulike råd:

- [Aksel: DatePicker](https://aksel.nav.no/komponenter/core/datepicker) — under «Retningslinjer»: ved datoer langt fram eller tilbake i tid skal `dropdownCaption` brukes sammen med `fromDate`/`toDate`, ellers må brukeren bla én måned av gangen. Seksjonen «Vurder om Datepicker er den rette løsningen for deg» tar opp at et rent tekstfelt ofte er bedre for datoer brukeren kan utenat.
- [Aksel: TextField](https://aksel.nav.no/komponenter/core/textfield) og [Aksel: MonthPicker](https://aksel.nav.no/komponenter/core/monthpicker) — alternativene Aksel peker på.
- [Aksel: Mønster for skjemavalidering](https://aksel.nav.no/monster-maler/soknadsdialog/monster-for-skjemavalidering) — anbefaler blant annet å akseptere flere formater på datoer for å redusere feil.
- [Uutilsynet: Skjema](https://uutilsynet.no/wcag-standarden/skjema/38) — normativ i Norge (forskrift om universell utforming av ikt): «Dersom brukeren skal legge inn dato, for eksempel fødselsdato eller avreisedato, bør det være et tekstfelt, gjerne supplert med en datovelger.» Datoformatet beskrives «i ledeteksten eller i tilknytning til skjemaelementet» — begge deler er altså greit.
- [Uutilsynet: 1.3.5 Identifiser formål med inndata](https://www.uutilsynet.no/wcag-standarden/135-identifiser-formal-med-inndata-niva-aa/142) — autofyll-kravet gjelder bare felt som samler informasjon om brukeren selv, «og ikke til en annen person». Derfor er `autoComplete="off"` riktig på f.eks. barnets fødselsdato (Aksel setter det uansett selv på `DatePicker.Input`).
- [Uutilsynet: Løsningsforslag per krav](https://www.uutilsynet.no/veiledning/losningsforslag-krav/1366)
- [Digdir/Designsystemet: Ask users for date and time](https://designsystemet.no/en/patterns/date-and-time/) — går lenger enn Aksel: «Custom-built date pickers often result in lower accessibility and more friction than simple text fields.» Foreløpig bare publisert på engelsk, og mønsteret diskuteres fortsatt i [digdir/designsystemet#1681](https://github.com/digdir/designsystemet/discussions/1681).
- [GOV.UK: Dates](https://design-system.service.gov.uk/patterns/dates/) — primærkilden både Aksel og Digdir viser til.

### Slik gjør vi det

Vi beholder Aksels datovelger, men tekstfeltet er hovedveien inn — det skal alltid gå raskt å skrive datoen rett inn:

- **Ingen forhåndsutfylt dato.** Feltet er tomt til brukeren fyller det ut selv.
- **Formatet står i `description`** (`Format: dd.mm.åååå`), ikke i selve labelen.
- **Ikke lag egen parsing.** Aksel godtar allerede `dd.mm.åååå`, `ddmmåååå`, `dd/mm/åååå`, `dd-mm-åååå` og tosifret år (`allowTwoDigitYear`, på som standard). Det dekker uutilsynets råd om å akseptere flere formater uten at vi skriver noe eget.
- **`dropdownCaption` når feltet har både `fromDate` og `toDate`**, slik at bruker kan hoppe direkte til år og måned. Nedtrekket krever begge grensene for å vises i det hele tatt.
- **Grensene er ekte validering, ikke bare navigasjon.** Aksel avviser datoer utenfor `fromDate`/`toDate` også når de skrives inn, så sett dem romslig nok til at legitime svar ikke blokkeres.
- **`fromDate` styrer to ting samtidig:** hva som godtas, og hvor langt tilbake årsnedtrekket lister. Et romslig godkjenningsvindu gir derfor en lang årsliste — med mindre du skiller dem. `useDatepicker` sin `fromDate` avgjør valideringen, `DatePicker` sin avgjør kalenderen og nedtrekket, og de trenger ikke være like. `Datovelger` gjør skillet med `kalenderFraDato`: fødselsdato godtar hundre år tilbake, men lister bare tjue i nedtrekket — eldre årstall skrives inn i tekstfeltet.
- **Dekk hele valideringsobjektet fra `onValidate`.** Ved ugyldig inndata nullstiller `useDatepicker` skjemaverdien; håndterer du bare `isAfter`, står brukeren igjen med tekst i feltet og «du må oppgi dato» ved innsending. `isWeekend` og `isDisabled` hører med — faller de gjennom til formatmeldingen, oppgir du feil årsak.
- **Vent med feilmeldingen til feltet er forlatt.** Sier du fra på hvert tastetrykk, står det «er ugyldig» mens datoen fortsatt er halvskrevet. Unntaket er når skjemaet allerede har meldt fra om feil på feltet: da er det sendt inn, og den presise meldingen skal fram med en gang. Uten unntaket får den som skriver en ugyldig dato og trykker enter «du må oppgi dato» mens det står tekst i feltet, siden enter sender inn uten å utløse blur.
- **Marker bare feltet som faktisk er feil.** I et periodefelt gjelder skjemafeilen («fra etter til», «du må oppgi periode») begge feltene, mens en parsefeil gjelder det ene. Farger du begge røde uansett, skjuler du hvilket felt som skal rettes.
- **Fra og til hører sammen i et `Fieldset`.** Uten det heter feltene bare «Fra» og «Til» for skjermlesere, og flere perioder på samme side lar seg ikke skille. Legenden er spørsmålet. Ikke sett `error` på selve fieldsettet — da arver begge feltene markeringen, og punktet over ryker.
- **`useDatepicker` leser `defaultSelected` kun ved montering.** Skal feltet nullstilles eller vise en annen verdi senere (f.eks. i en modal som blir stående montert), må komponenten monteres på nytt via `key`.
- **Send `id` til `DatePicker.Input`, aldri til `DatePicker`.** Rot-komponenten bruker `id` som aria-id for popoveren, så samme id begge steder gir duplikat-id i DOM og en `aria-controls` som peker på seg selv.

Referanseimplementasjonen er `Datovelger`/`Periodevelger` i [`tiltakspenger-soknad`](https://github.com/navikt/tiltakspenger-soknad) (`src/components/datovelger/`). Feilteksten ligger i `datoFeilmelding.ts` og visningstidspunktet i `useDatofeil.ts`, begge med tester i samme mappe — reglene over er dekket der, så en endring som bryter dem gir rødt bygg.

## Feilsøking med logger og traces

Alle appene (frontender og backender) er auto-instrumentert med OpenTelemetry via NAIS (`observability.autoInstrumentation` i nais.yml). Det gir to id-er som injiseres automatisk i logglinjene — via pino på frontendene (merk: `tiltakspenger-meldekort` logger med `console` og får dem ikke i dag) og logback-MDC på backendene — og som propageres automatisk mellom tjenestene på HTTP-kall:

- **`trace_id`** identifiserer **hele kjeden** for én request, ende til ende. Alle tjenestene requesten er innom (ingress → wonderwall → frontend → api → PDL/texas osv.) deler samme trace_id. Dette er nøkkelen for å korrelere logger på tvers av tjenester.
- **`span_id`** identifiserer **én enkelt operasjon** i kjeden — én server-håndtering, ett utgående HTTP-kall, én DB-spørring. Spans danner et tre med varighet per ledd. På en logglinje forteller span_id hvilken operasjon linjen ble logget inne i.

Slik kobler du en feil i én tjeneste til resten av kjeden (i [Grafana](https://grafana.nav.cloud.nais.io) → Explore):

1. Finn feillinjen i Loki, f.eks. `{service_name="tiltakspenger-soknad"} | json | level="error"`.
2. Kopier `trace_id` fra linjen.
3. Søk på trace_id-en i Loki **uten** service-filter for å få logglinjene fra alle tjenestene i kjeden, og/eller slå den opp i Tempo for spantreet med tidsbruk per ledd.

Mangler en tjeneste helt i en trace der den normalt har spans, nådde requesten den sannsynligvis aldri — da er det infrastruktur (f.eks. pågående utrulling), ikke treg kode, som er sporet.

Traces er også en uavhengig kontrollkilde, siden spans lages av OTel-agenten uansett hva appene logger. Skal du skille «feilene har stoppet» fra «loggingen har stoppet», søk i Tempo etter lange klient-spans (f.eks. `duration>9s` når timeouten er 10 s) og sammenlign med feillinjene i Loki — tallene skal stemme overens. Trege men vellykkede kall dukker ikke opp som feil, men finnes igjen i frontendens kall-linjer (`GET <url> -> 200 (9042ms)`) med varighet som skal matche spanet.

## Alarmer og Slack-varsler

Teamet har tre varselkanaler i Slack, med to helt uavhengige kilder bak seg:

| Kanal | Avsender | Kilde |
|---|---|---|
| `#tp-varsel` | «Tiltakspenger slack notifications» | GitHub Actions (byggfeil på main, feilede dependabot-auto-merges) |
| `#tp-varsel-dev` | «Alertmanager nav-dev» | Alerts fra dev-clustrene (dev-gcp/dev-fss) |
| `#tp-varsel-prod` | «Alertmanager nav-prod» | Alerts fra prod-clustrene (prod-gcp/prod-fss) |

Merk avsendernavnet når du leser et varsel: dev- og prod-alertene har identisk tekst (samme alert-regler deployes til begge miljøer), så det er lett å tro at et dev-varsel gjelder prod. Sjekk «nav-dev»/«nav-prod» og kanalnavnet før du feilsøker.

### Hvor alertene er definert

- **Felles alerts** for alle appene ligger i [`tiltakspenger-iac/alerts/felles-alerts.yaml`](https://github.com/navikt/tiltakspenger-iac) («Applikasjon er nede», «Høy feilrate i logger», «Kafka consumer offset lag»). De deployes som `PrometheusRule` til alle fire clustrene av `deploy-alerts.yaml`-workflowen i samme repo ved push til main. «Høy feilrate i logger» teller feillinjer via Lokis recording rule `loki:service:loglevel:count1m` (detected_level=error, per service_name) — terskelen er >5 feil siste time **og** >0 siste 15 min.
- **App-spesifikke alerts** ligger i `.nais/alerts.yml` i hvert app-repo, f.eks. «Utbetaling har feilet!» i `tiltakspenger-saksbehandling-api` (basert på appens egne metrikker).

### Slack-webhooken og rutingen (Alertmanager)

Rutingen fra alert til Slack-kanal styres **ikke** fra repoene våre. Nais legger en `AlertmanagerConfig` ved navn `slack-config` i `tpts`-namespacet i hvert cluster (eid av `ReplicationConfig monitoring-team-slack-alerts`), som fanger alle alerts med `namespace: tpts` og poster dem til teamets kanal for miljøet. Selve webhook-URL-en ligger i secreten `slack-webhook` i namespacet — hverken secreten eller Alertmanager-loggene er lesbare med vanlig utviklertilgang, så oppsettet endres via team-innstillingene i [Nais Console](https://console.nav.cloud.nais.io) (eller ved å spørre i `#nais`). Nyttige detaljer fra rutingen:

- Varsler grupperes per `alertname`, og en alert som blir stående i firing re-varsles først etter `repeatInterval: 1h`. Stillhet betyr altså ikke at alerten er borte.
- `[RESOLVED]`-meldinger sendes som standard; en alert kan skru dem av med label `send_resolved: "false"` (slik «Utbetaling har feilet!» gjør).
- Label `alert_type: custom` unntar en alert fra default-rutingen, for alerts som skal til egne kanaler via egen `AlertmanagerConfig` — se [nais-dokumentasjonen om tilpassede varsler](https://doc.nais.io/observability/alerting/how-to/prometheus-advanced/).

### Feilsøking: «kanalen er stille» eller «kom dette varselet frem?»

Alert-historikken kan rekonstrueres uavhengig av Slack med en range-query mot Mimir på seriene `ALERTS{namespace="tpts", alertstate="firing"}` — husk å skille på `k8s_cluster_name` (dev/prod), ellers blander du miljøene. Recording rule-metrikkene fra Loki (f.eks. `loki:service:loglevel:count1m`) er også spørrbare i Mimir, så du kan regne ut selv om en terskel faktisk ble krysset. Se «Feilsøking med logger og traces» over for API-tilgang og headere. Feiler selve leveransen til Slack, synes det bare i plattformens metrikker (`alertmanager_notifications_failed_total{integration="slack"}` — uten per-team-label) og i Alertmanager-loggene som kun nais-teamet har tilgang til.

### CI-varslene (`#tp-varsel`)

Byggvarsler sendes direkte fra GitHub Actions med en egen Slack-webhook som ligger som secret `SLACK_VARSEL_WEBHOOK_URL` i hvert repo (også som Dependabot-secret, siden Dependabot-kjøringer ikke ser vanlige Actions-secrets). Den brukes av test-og-bygg-workflowene i repoene og av den delte [`dependabot-auto-merge.yml`](https://github.com/navikt/tiltakspenger-workflows/blob/main/.github/workflows/dependabot-auto-merge.yml). Webhook-verdien administreres i Slack-appen [«Tiltakspenger slack notifications»](https://api.slack.com/apps/A080BJA5P34/incoming-webhooks) under *Incoming Webhooks* (krever collaborator-tilgang på appen) — GitHub-secrets kan ikke leses tilbake, så det er dit man går for å hente verdien når et nytt repo skal ha secreten. Denne webhooken har ingenting med Alertmanager-kjeden å gjøre — at CI-varsler kommer frem sier altså ikke noe om alert-varslene, og omvendt.

### Videre lesning

- [Nais: Alerting (konsepter)](https://doc.nais.io/observability/alerting/)
- [Nais: Opprette alerts med PromQL](https://doc.nais.io/observability/alerting/how-to/prometheus-basic/) og [referanse for PrometheusRule](https://doc.nais.io/observability/alerting/reference/prometheusrule/)
- [Nais: Tilpassede varsler/kanaler med AlertmanagerConfig](https://doc.nais.io/observability/alerting/how-to/prometheus-advanced/)
- [Prometheus Alertmanager: notifikasjoner og ruting](https://prometheus.io/docs/alerting/latest/configuration/)

## Delte GitHub Actions-workflows

Delte workflows for repoene våre bor i [`navikt/tiltakspenger-workflows`](https://github.com/navikt/tiltakspenger-workflows) (`.github/workflows/`) og kalles med `workflow_call` fra tynne caller-workflows i hvert repo.
Se [README-en i workflow-mappa der](https://github.com/navikt/tiltakspenger-workflows/blob/main/.github/workflows/README.md) for caller-eksempel, konvensjoner (secrets, permissions, pinning), hvilke repoer som dekkes og forholdet til Nais-dokumentasjonen/Golden Path — og [#31](https://github.com/navikt/tiltakspenger/issues/31) for utrullingsstatus.

**Hvorfor eget repo?** Normen i Nav er et dedikert `<team>-workflows`-repo (20+ team, f.eks. `aap-workflows`). Vi startet (2026-07-17) med workflowene i dette metarepoet fordi porteføljen var liten, men flyttet dem til `tiltakspenger-workflows` da porteføljen vokste — flyttingen var én endret linje per caller-repo, som forventet. `tiltakspenger-libs` er fortsatt uaktuelt fordi workflow-endringer der ville trigget full maven-publisering, og fordi libs da blir både produsent og konsument av samme CI.

## Sikkerhet

Oppskrifter for herding av utviklermaskinen ligger i [`docs/sikkerhet/maskin-hardening/`](docs/sikkerhet/maskin-hardening/).
Målet er at nøkler ligger i maskinvare og ikke kan kopieres ut av maskinen, og at legitimasjon som alltid er tilgjengelig bare kan lese.
For macOS: [SSH-nøkkel i Secure Enclave](docs/sikkerhet/maskin-hardening/ssh-nokkel-mac.md), [signerte commits](docs/sikkerhet/maskin-hardening/signerte-commits-mac.md) og [lesetoken for `gh`](docs/sikkerhet/maskin-hardening/gh-lesetoken.md).
For Linux finnes en [samlet oppskrift for signering](docs/sikkerhet/maskin-hardening/signerte-commits-linux.md) som ikke er testet.

## Team-board (GitHub Project)

Teamet bruker GitHub-projectet [**Team tiltakspenger** (`navikt/projects/227`)](https://github.com/orgs/navikt/projects/227) som felles oversikt på tvers av alle `tiltakspenger*`-repoene. Projectet eies av organisasjonen `navikt` og er lenket til teamet `navikt/tpts`.

Nye åpne issues og PR-er legges inn automatisk via projectets **Auto-add**-workflows (per repo). Innholdet deles opp i tre views med hvert sitt filter:

| View           | Filter                              |
| -------------- | ----------------------------------- |
| Issues         | `is:issue is:open`                  |
| Dependabot PRs | `is:pr is:open label:dependencies`  |
| PRs            | `is:pr is:open -label:dependencies` |

Auto-add-workflowene bruker `is:issue is:open` for issues og `is:pr is:open` for PR-er.

> **Merk:** view-filtre og Auto-add-workflows kan i dag kun konfigureres i GitHub-UI-et — det finnes ingen API/CLI for å opprette eller endre dem. Nye repoer må derfor legges til i Auto-add-workflowene manuelt.

### Lese status fra kommandolinja

Statusen til én issue leses fra issuen selv, ikke fra prosjektlista:

```bash
gh issue view <nr> --repo navikt/<repo> --json projectItems \
  -q '.projectItems[] | "\(.title)=\(.status.name)"'
# → Team tiltakspenger=In Progress
```

Trenger du hele prosjektet — for eksempel for å finne issues som mangler i det — må `--limit` settes høyere enn antall items, og resultatet kontrolleres mot totalen svaret oppgir:

```bash
gh project item-list 227 --owner navikt --limit 2000 --format json > prosjekt.json
jq -e '.totalCount == (.items | length)' prosjekt.json || echo "avkortet – hev --limit"
```

Uten den kontrollen kutter `gh project item-list` stille ved `--limit` og gir et delvis svar med exit 0.
Projectet passerte 500 items sommeren 2026, så defaultgrensen på 30 er langt under.
Items fra alle `tiltakspenger*`-repoene ligger i samme project, så et issue-nummer må alltid pares med `content.repository` når du filtrerer.
