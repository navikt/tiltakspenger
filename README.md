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
- [tiltakspenger-soknad-mock-api](https://github.com/navikt/tiltakspenger-soknad-mock-api)
- [tiltakspenger-pdfgen](https://github.com/navikt/tiltakspenger-pdfgen)
- [tiltakspenger-pdfgenrs](https://github.com/navikt/tiltakspenger-pdfgenrs)
- [tiltakspenger-soknad](https://github.com/navikt/tiltakspenger-soknad)
- [tiltakspenger-datadeling](https://github.com/navikt/tiltakspenger-datadeling)
- [tiltakspenger-meldekort](https://github.com/navikt/tiltakspenger-meldekort)
- [tiltakspenger-meldekort-api](https://github.com/navikt/tiltakspenger-meldekort-api)
- [tiltakspenger-meldekort-microfrontend](https://github.com/navikt/tiltakspenger-meldekort-microfrontend)
- [tiltakspenger-journalposthendelser](https://github.com/navikt/tiltakspenger-journalposthendelser)

### Lokal kjøring av verdikjeden

Meta-repoet kommer med et docker-compose oppsett som kan benyttes for å kjøre opp
hele verdikjeden lokalt i Docker-containere, med noen unntak (`tiltakspenger-saksbehandling`,
`tiltakspenger-soknad` og `tiltakspenger-soknad-api`). Merk at `tiltakspenger-saksbehandling` kan kjøres opp
på siden av øvrige apper for å kunne teste frontend lokalt.

#### Bruk av docker-compose oppsett for saksbehandling

For enkel bruk av docker-compose-oppsett er det skrevet noen bash-script som ligger på
rot av dette repositoryet.

| script          | beskrivelse                                                                                                                                                |
|-----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ./up.sh         | Script for å bygge og starte alle apper i docker-compose (se i [up.sh](https://github.com/navikt/tiltakspenger/blob/main/up.sh) for tilgjengelige options) |
| ./down.sh       | Script for å stoppe alle apper i docker-compose (se i [down.sh](https://github.com/navikt/tiltakspenger/blob/main/down.sh) for tilgjengelige options)      |
| ./dkill.sh      | Script for å kjøre docker compose down, stopper og fjerner alle containere som eventuelt fortsatt kjører, og fjerner det tilhørende nettverket             |
| ./slettAlt.sh   | Kjører "docker compose down --rmi all --volumes", i.e. sletter alt.                                                                                        |
| ./slettBaser.sh | Kjører "docker compose down --volumes", i.e. sletter basene.                                                                                               |

#### Bruk av docker-compose oppsett for søknad

For kjøring av utviklingsmiljø for å jobbe med søknaden er det lagd et eget bash-script på
rot av dette repositoryet. Det kan kjøres opp med eller uten søknads-api'et, hvis man eksempelvis
skulle ønske å kjøre opp api'et fra IntelliJ.

| script           | beskrivelse                                                                                                                                                                     |
|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ./up-soknad.sh   | Script for å bygge og starte alle apper i docker-compose-soknad (se i [up-soknad.sh](https://github.com/navikt/tiltakspenger/blob/main/up-soknad.sh) for tilgjengelige options) |
| ./down-soknad.sh | Script for å stoppe alle apper i docker-compose (se i [down-søknad.sh](https://github.com/navikt/tiltakspenger/blob/main/down-soknad.sh) for tilgjengelige options)             |

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

Det kan være praktisk å populere lokale databaser med data fra dev-miljøet. Du trenger `pg_dump` og `pg_restore` fra [Postgres binaries](https://www.postgresql.org/download/).

#### Fremgangsmåte
Eksempel for saksbehandling-api, se docker-compose for parametre for andre apper.

- Start den lokale databasen:
```
docker compose up -d postgresSaksbehandling
```

Hvis du allerede har en lokal database, slett den (inkludert volume) og kjør opp på nytt.

- Start en lokal proxy til dev-databasen du skal importere fra, med [nais cli](https://docs.nais.io/persistence/postgres/how-to/personal-access/). Se doc'en for førstegangsoppsett, senere kan du kjøre disse kommandoene:
```
kubectl config use-context dev-gcp
nais postgres proxy -p 5444 tiltakspenger-saksbehandling-api
```

- Kjør `pg_dump` for å dumpe dev-databasen:
```
pg_dump --host=localhost --port=5444 --dbname=saksbehandling --username=<GCP brukernavn> --schema=public --format=directory --file=<path til dump>
```

- Kjør `pg_restore` for å gjenopprette databasen lokalt (se docker-compose for passord, antagelig `test`)
```
pg_restore --host=localhost --port=5433 --dbname=saksbehandling --username=postgres --single-transaction --clean --no-owner --no-privileges <path til dump>
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

Byggvarsler sendes direkte fra GitHub Actions med en egen Slack-webhook som ligger som secret `SLACK_VARSEL_WEBHOOK_URL` i hvert repo (også som Dependabot-secret, siden Dependabot-kjøringer ikke ser vanlige Actions-secrets). Den brukes av test-og-bygg-workflowene i repoene og av den delte [`dependabot-auto-merge.yml`](.github/workflows/README.md). Denne webhooken har ingenting med Alertmanager-kjeden å gjøre — at CI-varsler kommer frem sier altså ikke noe om alert-varslene, og omvendt.

### Videre lesning

- [Nais: Alerting (konsepter)](https://doc.nais.io/observability/alerting/)
- [Nais: Opprette alerts med PromQL](https://doc.nais.io/observability/alerting/how-to/prometheus-basic/) og [referanse for PrometheusRule](https://doc.nais.io/observability/alerting/reference/prometheusrule/)
- [Nais: Tilpassede varsler/kanaler med AlertmanagerConfig](https://doc.nais.io/observability/alerting/how-to/prometheus-advanced/)
- [Prometheus Alertmanager: notifikasjoner og ruting](https://prometheus.io/docs/alerting/latest/configuration/)

## Delte GitHub Actions-workflows

Delte workflows for repoene våre bor i [`.github/workflows/`](.github/workflows/) i dette repoet og kalles med `workflow_call` fra tynne caller-workflows i hvert repo.
Se [README-en i workflow-mappa](.github/workflows/README.md) for caller-eksempel, konvensjoner (secrets, permissions, pinning), hvilke repoer som dekkes og forholdet til Nais-dokumentasjonen/Golden Path — og [#31](https://github.com/navikt/tiltakspenger/issues/31) for utrullingsstatus.

**Hvorfor metarepoet?** Vi vurderte tre plasseringer (kartlagt 2026-07-17). Normen i Nav er et dedikert `<team>-workflows`-repo (20+ team, f.eks. `aap-workflows`), men med en portefølje på et par workflows er et eget repo mest overhead — vi følger heller tilleggsstønader, som bruker metarepoet sitt. `tiltakspenger-libs` ble valgt bort fordi workflow-endringer der ville trigget full maven-publisering, og fordi libs da blir både produsent og konsument av samme CI. Vokser porteføljen, kan workflowene flyttes til et eget `tiltakspenger-workflows`-repo — flyttingen er én endret linje per caller-repo.

Workflowene trenger ingen publisering eller release: callerne henter fila direkte fra `main` ved kjøring, så eneste krav er at endringer er pushet hit.

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
