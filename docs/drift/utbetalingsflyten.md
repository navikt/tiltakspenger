# Utbetalingsflyten: fra vedtak til penger på konto

Denne siden viser hva som skjer fra tiltakspenger sender en utbetaling til pengene er utbetalt, og hvorfor det tar et par dager.
Den første delen er for alle; delen «For utviklere» viser de tekniske detaljene.

## Kort fortalt

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Arial","fontSize":"16px","lineColor":"#596773","clusterBkg":"#FAFAFA","clusterBorder":"#CFD3D8"},"flowchart":{"wrappingWidth":400,"nodeSpacing":40,"rankSpacing":40,"padding":14}}}%%
flowchart TD
    A["<b>Tiltakspenger sender utbetalingen</b><br/>like etter at meldekortet er godkjent"]
    B["<b>Helved sender den videre til Oppdrag</b><br/>står i kø mens Oppdrag er stengt"]
    subgraph D1["Dag 1: hverdagen Oppdrag tar imot utbetalingen"]
        direction TB
        C["<b>Oppdrag godkjenner</b><br/>åpent hverdager 06–21"]
        D["<b>Oppdrag beregner</b><br/>om kvelden etter 21, ferdig ca. 07"]
        C --> D
    end
    subgraph D2["Dag 2: neste hverdag"]
        E["<b>Ventedag</b><br/>utbetalingen venter"]
    end
    subgraph D3["Dag 3: hverdagen etter ventedagen"]
        F["<b>Utbetalt fra Nav</b><br/>pengene er på vei til banken"]
    end

    A --> B --> D1 --> D2 --> D3

    classDef tp fill:#E6F0FF,stroke:#0067C5,color:#23262A
    classDef helved fill:#EFECF4,stroke:#634689,color:#23262A
    classDef os fill:#FFF2E0,stroke:#C77300,color:#23262A
    classDef vent fill:#FFFFFF,stroke:#8F8F8F,color:#23262A,stroke-dasharray:4 3
    classDef ut fill:#E3F6EA,stroke:#06893A,color:#23262A
    class A tp
    class B helved
    class C,D os
    class E vent
    class F ut
```

- Oppdrag er kortnavnet på Oppdragssystemet, som beregner og betaler ut ytelsene i Nav.
- Tiltakspenger sender utbetalingen like etter at et meldekort eller et vedtak er godkjent, også om kvelden og i helgen.
- Meldekort som behandles automatisk, blir bare behandlet mens Oppdrag er åpent, fordi behandlingen må beregne utbetalingen i Oppdrag først.
- Tiltakspenger og helved tar imot utbetalinger døgnet rundt, men Oppdrag er bare åpent 06:00–21:00 på hverdager og 07:00–18:00 på omtrent to av tre lørdager.
- Oppdragssystemet beregner utbetalingene om kvelden etter stenging, og beregningen skal være ferdig rundt 07:00 neste morgen.
- Tiltakspenger har 1 ventedag i Oppdragssystemet, så utbetalingen blir registrert i Utbetalingsreskontroen tidligst to hverdager etter at den ble godkjent.
- Godkjent betyr ikke utbetalt: utbetalingen kan stoppe senere, for eksempel hvis kontonummer mangler.

### Når blir utbetalingen registrert?

| Sendt | Godkjent | Beregnet | Ventedag | Registrert i reskontroen |
| --- | --- | --- | --- | --- |
| Mandag 14:00 | Mandag | Mandag kveld | Tirsdag | Onsdag |
| Mandag 22:00 | Tirsdag morgen | Tirsdag kveld | Onsdag | Torsdag |
| Fredag 15:00 | Fredag | Fredag kveld | Mandag | Tirsdag |
| Lørdag, vanlig helg | Mandag morgen | Mandag kveld | Tirsdag | Onsdag |
| Lørdag med lørdagsåpent | Lørdag | Søndag kveld | Mandag | Tirsdag |

Helligdager regnes som helg.
Det er ikke avklart hvilken dag pengene står på kontoen, siden det også avhenger av banken.

### Unntak

- Oppdrag har lørdagsåpent 07:00–18:00 på omtrent to av tre lørdager; i 2026 er det 35 av 52.
  Datoene står i Excel-arket [Åpningstider for saksbehandlingssystemer i Nav 2026](https://navno.sharepoint.com/sites/fag-og-ytelser-fagsystemer/_layouts/15/download.aspx?UniqueId=9BACC3BA-6D12-4DD1-AC10-7F6B4100AD20) på [Navet](https://navno.sharepoint.com/sites/fag-og-ytelser-fagsystemer/SitePages/%C3%85pningstider-og-registreringsfrister-i-fagsystemene.aspx), som får nytt ark hvert år.
  En utbetaling som sendes fredag kveld eller lørdag, blir da godkjent lørdag og beregnet søndag kveld, så den kommer én dag tidligere enn i en vanlig helg.
- Det samme gjelder når Oppdrag åpner kort i helgen for vedlikehold: alt som blir godkjent i helgen før søndag 21:00, beregnes søndag kveld.
- Det er ingen beregning lørdag kveld, så en åpen lørdag teller ikke som egen dag i flyten.
- Omtrent én hverdag i måneden stenger systemene kl. 18:00 fordi Oppdrag beregner pensjoner om natten; utbetalinger etter 18 blir da godkjent neste hverdag.
- Åpningstiden kan flyttes, for eksempel rundt helligdager og større produksjonssettinger i økonomiløsningene; endringer publiseres på Navet.

## For utviklere

```mermaid
sequenceDiagram
    autonumber
    participant TP as tiltakspenger<br/>saksbehandling-api
    participant UT as helved<br/>utsjekk
    participant UR_SKOG as helved<br/>urskog
    participant OS as Oppdrag (OS)
    participant UR as Utbetalings-<br/>reskontroen (UR)

    Note over TP: Jobb saksbehandling-jobb-send-utbetalinger
    TP->>UT: POST /api/iverksetting/v2
    UT-->>TP: 202 mottatt (409 «allerede mottatt» regnes også som mottatt)
    UT->>UR_SKOG: helved.oppdrag.v1 (Kafka)
    UR_SKOG->>UT: status HOS_OPPDRAG (helved.status.v1)
    UR_SKOG->>OS: oppdrag-XML på IBM MQ
    Note over UR_SKOG,OS: Meldingen ligger i MQ-køen til OS åpner<br/>(hverdager 06:00–21:00)
    OS-->>UR_SKOG: kvittering, alvorlighetsgrad 00/04 = OK, ellers FEILET
    UR_SKOG->>UT: OK eller FEILET (helved.status.v1)
    Note over TP: Jobb saksbehandling-jobb-oppdater-utbetalingsstatus
    TP->>UT: GET /api/iverksetting/{sak}/{id}/status
    UT-->>TP: OK eller FEILET
    Note over OS: Kveldsbatch etter 21:00, ferdig ca. 07:00
    Note over OS: 1 ventedag: neste åpne dag
    OS->>UR: postering med forfallsdato dagen etter ventedagen
    Note over UT,OS: vedskiva sender grensesnittavstemming (start-, data- og sluttmelding) på MQ hver virkedag
```

- `Åpningstider.kt` i saksbehandling-api modellerer åpningstiden som 06:10–20:50 på hverdager som ikke er faste helligdager, med margin mot stengetidene.
  Bevegelige helligdager, lørdagsåpent og vedlikeholdsåpning i helg er ikke med, så modellen treffer uker uten lørdagsåpent og helligdager midt i uka.
- Jobbene `saksbehandling-jobb-send-utbetalinger` og `saksbehandling-jobb-oppdater-utbetalingsstatus` kjører uavhengig av åpningstiden; helved og MQ-køen holder på utbetalingen til OS åpner.
- `AutomatiskMeldekortbehandlingJobb` og `OppdaterUtbetalingsoversiktJobb` står over utenfor `Åpningstider.erInnenforØkonomisystemetsÅpningstider`, fordi simulering og utbetalingsoversikt krever at OS er åpent.
- `Åpningstider.senesteSendetidspunktSomKanStåIReskontroen` regner ut eksemplene i tabellen over.
- Status `FEILET` prøves ikke på nytt og må følges opp manuelt; får en utbetaling ikke OK innen 3 dager, varsler `OppdaterUtbetalingsstatusService`.
- Reverseres en utbetaling innen to virkedager, før posteringene har nådd UR, gir simuleringen tom respons.
- I helved v3 kan en utbetaling angres med `DELETE /utbetalinger/:uid` samme dag før 21:00; vi bruker fortsatt v2.
- Du kontrollerer en utbetaling i OS og UR i Utbetalingsportalen: [utbetalingsportalen.md](utbetalingsportalen.md).

## Kilder

- helved-docs: [Om tjenesten](https://helved-docs.intern.dev.nav.no/kom_i_gang/om_tjenesten), [FAQ](https://helved-docs.intern.dev.nav.no/v3/doc/faq) og [Sjekk status](https://helved-docs.intern.dev.nav.no/kom_i_gang/sjekk_status_pa_utbetaling).
- Koden i [navikt/helved-utbetaling](https://github.com/navikt/helved-utbetaling): `apps/utsjekk`, `apps/urskog` og `dokumentasjon/grensesnittavstemming.md`.
- Confluence: [Hjelp! Noe har gått galt med utbetaling](https://confluence.adeo.no/spaces/TRAFIKKNAVKONTAKTSENTER/pages/800081310) (kjøretider i OS; meldekortytelser beregnes alle hverdager).
- Ventedagen: `Åpningstider.kt` i tiltakspenger-saksbehandling-api.
  Antall ventedager er en innstilling per fagområde i Oppdrag, og TILTPENG har 1 ventedag.
- Søndagsbatch og ventedager som innstilling i Oppdrag: [Årskjøringsplan for FSDRIFT (OS/UR)](https://confluence.adeo.no/spaces/TOB/pages/657867194) på Confluence.
