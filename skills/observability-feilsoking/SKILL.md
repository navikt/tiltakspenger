---
name: observability-feilsoking
description: Feilsøk produksjonsproblemer i tiltakspenger-appene med Loki (logger), Tempo (traces) og Mimir (metrikker) via API. Bruk ved timeouts, feilspikes, trege kall, «requester som forsvinner», eller når du skal verifisere om en feil ligger i app, nabotjeneste eller infrastruktur. Inneholder teamets labels, standardspørringer og feilsøkingsheuristikker.
license: MIT
metadata:
  domain: observability
  tags: loki tempo mimir grafana traces logger metrikker feilsøking prod
---

# Observability-feilsøking for tiltakspenger

Teamspesifikk oppskrift for å spørre Grafana-stacken direkte via API.
Bakgrunn om trace_id/span_id og hvordan de henger sammen: se «Feilsøking med logger og traces» i metarepoets README.

## Forutsetninger

- naisdevice tilkoblet: sjekk med `nais device status`, koble til med `nais device connect`.
- Alle API-kall skal ha headerne `X-Scope-OrgID: tenant` og en beskrivende `User-Agent`.

## Endepunkter og labels

| Pilar | Endepunkt |
|---|---|
| Loki (logger) | `https://loki.nav.cloud.nais.io/loki/api/v1/query_range` |
| Tempo (traces) | `https://tempo.<env>.nav.cloud.nais.io/api/search` og `/api/traces/<trace_id>` (env: `prod-gcp` / `dev-gcp`) |
| Mimir (PromQL) | `https://mimir.nav.cloud.nais.io/prometheus/api/v1/query` og `query_range` |

Labels for våre apper:

- Loki: `k8s_cluster_name="prod"` eller `"dev"` (IKKE `prod-gcp`), app via `service_name`, namespace via `service_namespace="tpts"` (IKKE `namespace` — den finnes ikke i Loki og gir tomt svar). Bruk alltid `start`/`end` (nanosekunder). Strømmene har bare `service_name`, `service_namespace`, `k8s_cluster_name`, `k8s_container_name`, `k8s_node_name`, `k8s_pod_name` og `detected_level`; resten må hentes ut av logglinja med `| json`.
- `tiltakspenger-arena` kjører på fss og ligger under `prod-fss`/`dev-fss` — i både Loki og Mimir. Sveiper du over hele flåten, bruk `k8s_cluster_name=~"prod.*"`; med eksakt `"prod"` faller arena stille ut av svaret.
- Tempo: `resource.service.name="<app>"`. Filtrer på `kind` (`server`/`client`) — søk uten kind-filter treffer jobb-/DB-spans og kan lure deg til å tro at HTTP-spans mangler.
- Mimir: app-metrikker via `app="<app>"` (f.eks. `http_server_request_duration_seconds_*`, `jvm_gc_duration_seconds_*`).

## Start her: tell før du henter

De fleste spørsmål er tall («har vi feil nå?», «hvor mange?», «når begynte det?»), og da er logglinjer feil verktøy.
Uthenting av linjer gir maks 100 om gangen og kutter de eldste først, mens en metrikkspørring gir eksakt svar i ett kall uten linjegrense.

```bash
# Fordeling per nivå siste time — ett kall, eksakt. Ingen ERROR-rad = ingen feil i vinduet.
curl -s -H "X-Scope-OrgID: tenant" -H "User-Agent: tpts/feilsok" \
  "https://loki.nav.cloud.nais.io/loki/api/v1/query" -G \
  --data-urlencode 'query=sum by (level) (count_over_time({service_name="tiltakspenger-saksbehandling-api", k8s_cluster_name="prod"} | json [1h]))' \
  --data-urlencode "time=$(date +%s)"
# → DEBUG 6846, INFO 2555 (målt 2026-08-06)
```

Bytt `[1h]` mot `[24h]` for døgnet, eller kjør mot `query_range` med `step` for en kurve som viser *når* det endret seg.
Først når tallet er lokalisert i tid, hent de rå linjene for det smale vinduet — da er 100 linjer rikelig.

Får du tomt svar, sjekk at navnet finnes før du konkluderer:

```bash
# Hvilke av våre apper logger i det hele tatt (15), og hvilket cluster kjører én av dem i.
# Uten query-selektoren får du alle 2424 appene i tenanten.
.../loki/api/v1/label/service_name/values?query={service_namespace="tpts"}&start=<ns>&end=<ns>
.../loki/api/v1/label/k8s_cluster_name/values?query={service_name="<app>"}&start=<ns>&end=<ns>

# Hvilke metrikknavn finnes (659 for tpts), og fantes serien i vinduet
.../prometheus/api/v1/label/__name__/values?match[]={namespace="tpts"}&start=<s>&end=<s>
.../prometheus/api/v1/series?match[]=up{namespace="tpts",app="<app>"}&start=<s>&end=<s>
```

`/series` svarer på om serien fantes i tidsvinduet, noe instant-spørringen ikke kan — den ser bare 5 minutter bakover, så en app som sluttet å rapportere ser identisk ut med en metrikk som aldri har eksistert.

## Standardspørringer

Feillinjer for en app (siste døgn):

```bash
curl -s -H "X-Scope-OrgID: tenant" -H "User-Agent: tpts/feilsok" \
  "https://loki.nav.cloud.nais.io/loki/api/v1/query_range" -G \
  --data-urlencode 'query={k8s_cluster_name="prod", service_name="tiltakspenger-soknad"} | json | level="error"' \
  --data-urlencode "limit=100" \
  --data-urlencode "start=$(date -v-24H +%s)000000000" \
  --data-urlencode "end=$(date +%s)000000000"
```

Hele kjeden for én hendelse: kopier `trace_id` fra feillinjen, søk i Loki uten service-filter (`|= "<trace_id>"`), og hent spantreet fra Tempo:

```bash
curl -s -H "X-Scope-OrgID: tenant" -H "User-Agent: tpts/feilsok" \
  "https://tempo.prod-gcp.nav.cloud.nais.io/api/traces/<full 32-tegns trace_id>"
```

Finn timeouts/trege kall uavhengig av logger (TraceQL):

```bash
# klient-spans nær timeout-grensa (10 s) fra frontenden
--data-urlencode 'q={resource.service.name="tiltakspenger-soknad" && kind=client && duration>9s}'
```

Backend-latens og «nådde requesten appen i det hele tatt?» (Mimir):

```bash
# antall requests > 5 s siste døgn (0 betyr at trege requests aldri nådde HTTP-laget)
sum(increase(http_server_request_duration_seconds_count{app="tiltakspenger-soknad-api"}[1d]))
  - sum(increase(http_server_request_duration_seconds_bucket{app="tiltakspenger-soknad-api", le="5"}[1d]))
```

Per-pod-tidslinje (deploy-/churn-korrelasjon) i Loki:

```
sum by (k8s_pod_name) (count_over_time({k8s_cluster_name="prod", service_name="<app>"}[10m]))
```

## Heuristikker

- **Mangler en app sine spans i én trace**, men har server-spans ellers → requesten nådde sannsynligvis aldri appen. Kryssjekk med access-loggen (soknad-api logger `Status: ..., Path: ..., Call-id: ...` for alle requests) og med rollout-aktivitet i tidsrommet (flere ReplicaSets / «Application started»).
- **Skille «feilene stoppet» fra «loggingen stoppet»**: tell lange klient-spans i Tempo per døgn og sammenlign med feillinjer i Loki — tallene skal stemme. Spans lages av OTel-agenten uavhengig av appens logging.
- **Helsesjekker feiler aldri, men brukertrafikk gjør det** → problemet ligger i service-rutet nettverk (kubelet går direkte på pod-IP), ikke i appen.
- **Svartehull-signatur**: dns.lookup + tcp.connect lykkes på få ms, deretter total stillhet til klient-timeout, ingen server-spans, ingen backend-logger, backend betjener naboer normalt → infrastruktur (conntrack/dataplane), ta det med nais-teamet med trace-id-er som bevis.

## Kjente feller

- **Uthenting av logglinjer kutter stille.** Uten `limit` får du 100 linjer, uten `start`/`end` bare siste time, og siden nyeste linje kommer først forsvinner de eldste treffene — nettopp dem du leter etter tidlig i vinduet. Sammenlign `stats.summary.totalPostFilterLines` med `totalEntriesReturned` i svaret: matchet flere linjer enn du fikk, er resultatet avkortet. Grensene for gh, Loki, Tempo og Mimir er samlet i metarepoets `AGENTS.md`, seksjonen «Lesegrenser og stille avkorting».
- **Mimirs `query_range` klipper til retensjon uten å si fra.** En spørring om 90 dager ga 30 dager tilbake med `status: success` og ingen `warnings` (målt 2026-08-06), så en «total siste kvartal» blir stille en månedstotal. Sammenlign første punkt i svaret med `start`-en du ba om.
- Tempo-søk kan sporadisk svare helt tomt — retry 2–3 ganger med noen sekunders pause før du konkluderer.
- `/api/traces/<id>` krever full 32-tegns trace_id.
- Uten cluster-filter i Loki blander du prod- og dev-pods (samme `service_name`).
- `count_over_time(...[1d])` med step 86400: punktene merkes med vinduets SLUTT — «14.07» betyr døgnet FØR 14.07 00:00.
- macOS: `date -v-1H +%s`, ikke GNU-syntaksen `date -d '1 hour ago'`.
- Dev har mye lavere trafikk — «0 treff i dev» beviser ikke at problemet er prod-spesifikt.
