---
name: tiltakspenger-testdata
description: Lag testdata lokalt for tiltakspenger-saksbehandling via ferdige scripts — testsak med innvilget vedtak, meldekortbehandling, klagebehandling, eller digital-/papirsøknad seedet mot LokalMain. Kan også forhåndsvise og lagre PDF-brevene fra pdfgenrs.
license: MIT
metadata:
  domain: backend
  tags: tiltakspenger testdata lokal meldekort klage søknad seeding
---

# Tiltakspenger testdata

Tynn peker til de ferdige scriptene i `tiltakspenger-saksbehandling/scripts/testdata/`.
Ikke reimplementer flyten — kjør scriptene.
Scriptene og full dokumentasjon er fasit; denne skillen er bare en snarvei.

> Denne skillen følger det åpne «Agent Skills»-formatet (`SKILL.md` med YAML-frontmatter) og er **verktøy-uavhengig** — ren markdown-instruksjon som kan brukes av en hvilken som helst agent/LLM-CLI (GitHub Copilot, open source-verktøy som OpenCode, lokale LLM-er osv.). Se [`../README.md`](../README.md) for hvordan du aktiverer den i ulike verktøy.

## Forutsetninger (sjekk først)

- Kjør fra rot av `tiltakspenger-saksbehandling` (`cd tiltakspenger-saksbehandling`) — script-stiene under er relative dit.
- Scriptene bor på `main`. Er du på en eldre feature-branch uten `scripts/testdata/`, hent dem derfra (f.eks. `git archive main scripts/testdata | tar -x`) eller bytt til en oppdatert branch.
- `LokalMain` i `tiltakspenger-saksbehandling-api` må kjøre på `http://localhost:8080` (`curl -sf http://localhost:8080/isready`).
- Lokal Postgres (docker) må kjøre.
- Ved Flyway-trøbbel som hindrer oppstart: se DB-reset nederst i dokumentasjonen (lenke under).

## Vanligste oppgave: lag alt på én gang

Kjør fra rot av `tiltakspenger-saksbehandling`:

```bash
# digital søknad som inngang
./scripts/testdata/opprett-alt-digital.sh

# papirsøknad (manuelt registrert) som inngang
./scripts/testdata/opprett-alt-papir.sh
```

Begge lager en sak med iverksatt innvilget vedtak + meldekortbehandling + klagebehandling, og skriver ut et **saksnummer** som utvikleren kan søke opp i frontend.

## Trenger du bare en del?

Scriptene er lagdelt (byggekloss → kombo → topp-nivå). Velg minste script som løser oppgaven:

| Utvikleren vil ha                                                                                                                                                    | Kjør                                                                                                 |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Alt (sak + meldekort + klage)                                                                                                                                        | `opprett-alt-digital.sh` / `opprett-alt-papir.sh`                                                    |
| Bare en sak med innvilget vedtak                                                                                                                                     | `opprett-innvilget-sak-digital.sh` / `opprett-innvilget-sak-papir.sh`                                |
| Bare en meldekortbehandling                                                                                                                                          | innvilget sak-script, deretter `opprett-meldekortbehandling.sh SAK_ID KJEDE_ID`                      |
| Bare en klagebehandling                                                                                                                                              | `opprett-klage.sh SAK_ID [VEDTAK_ID]` (på en eksisterende sak)                                       |
| Simuleringer å teste (ytelse, feilutbetaling, justering en-/flerdags, sperre-scenarioer på tvers av meldeperioder/måneder, trekk m/reversering, månedsskifte-splitt) | `opprett-simuleringsscenarioer.sh`                                                                   |
| Iverksatt meldekort / åpen korrigering med egne dagstatuser                                                                                                          | `fyll-og-iverksett-meldekort.sh` / `opprett-meldekort-korrigering.sh` `SAKSNUMMER [DATO=STATUS ...]` |
| Alle PDF-brevene som filer                                                                                                                                           | `forhandsvis-alle-pdfer.sh` (krever pdfgenrs på 8084 i docker)                                       |
| Ett enkelt PDF-brev                                                                                                                                                  | `forhandsvis-vedtaksbrev.sh` / `forhandsvis-meldekortbrev.sh` / `forhandsvis-klagebrev.sh`           |
| Ett enkelt endepunkt-steg                                                                                                                                            | tilsvarende byggekloss-script (se `scripts/testdata/README.md`)                                      |

PDF-scriptene lagrer til `$PDF_UT_DIR` (default `/tmp/tiltakspenger-pdfer`), med
én PDF per brev fra pdfgenrs. PDF-er som kun genereres av jobber (journalføring)
dekkes ikke.

## Mot dev (Hel Ved v3)

Kjør med `MILJO=dev`; personen lagrer ett token per ident med `dev-token.sh` (se README-ens «Dev»-del), og `dev-token.sh liste` viser hvilke som finnes, med roller og utløpstid.
Scriptene velger selv saksbehandler og beslutter ut fra rollene i tokenene; overstyr med `DEV_SAKSBEHANDLER=<ident>` og `DEV_BESLUTTER=<ident>`.
En bruker med fortrolig eller strengt fortrolig adresse gir 403 med `tilgang_nektet_kode_7` eller `tilgang_nektet_kode_6`; begge identene må da ha tilgang til den graderingen, og tokenets `groups` viser ikke det.
Agenten lager aldri tokens selv og ber om nye når `_lib.sh` melder at de har utløpt.
Bruk bare fiktive fødselsnumre (4–9 som tredje siffer, Navs og Skatteetatens syntetiske serier); scriptene avviser andre.

```bash
cd tiltakspenger-saksbehandling/scripts/testdata
MILJO=dev ./finn-testbrukere.sh                 # eksisterende brukere fra benken, med datohint for V2/V3
./sjekk-testbrukere.sh                          # brukerne fra Confluence med søkbare tiltak, V3-KLAR=ja uten sak
MILJO=dev ./hent-eller-opprett-sak.sh <FNR> V2  # ny sak på V2 (eller V3) før søknaden sendes
./helved-v3-scenarioer.sh "$SAKSNUMMER"                    # legacy-modus med seks V3-steg på én sak
./helved-v3-scenarioer.sh forbered-papir "$FNR" V3       # ny sak med eksplisitt V2 eller V3
./helved-v3-scenarioer.sh fullfor papir-saker.tsv
./helved-v3-scenarioer.sh simuler-gate utbetaling.tsv
./helved-v3-scenarioer.sh utbetaling utbetaling.tsv
./helved-v3-scenarioer.sh verifiser-helved helved-verifisering.tsv
./finn-journalpost.sh <FNR>                     # brukerens journalpost i SAF, til papirsøknad
./opprett-journalpost.sh <FNR>                  # ny journalpost i dokarkiv når brukeren ikke har noen
```

Papirsøknad i dev trenger en journalpost som gjelder brukeren.
`MILJO=dev ./registrer-papir-soknad.sh <SAKSNUMMER>` henter den selv med `finn-journalpost.sh`; finnes ingen, lag en med `opprett-journalpost.sh` og kjør på nytt.
Tiltaket hentes fra tiltaksdeltakelsene på saken i saksbehandlings-API-et (2023–2027), og søknaden gjelder hele tiltaket med indeks `TILTAKSINDEKS` (default 0).
Mottatt dato er tiltakets startdato, og `SOKNAD_MOTTATT_DATO` overstyrer den.
Journalpostscriptene bruker maskintoken fra tokengeneratoren mot SAF og dokarkiv og trenger ingen OBO-tokens.

## Hel Ved V3 med papirsaker i batch

`forbered-papir FNR V2|V3 [TILTAKSINDEKS]` oppretter en ny sak, registrerer papirsøknaden og fører den til VEDTATT.
En eksisterende sak avvises før papirregistrering fordi oppdragsversjonen ikke kan verifiseres fra `GET /sak`.
Bruk legacy-modus eller `fullfor` for eksisterende saker først etter at oppdragsversjonen er verifisert fra en autoritativ kilde.
En vellykket kjøring skriver ut `OPPDRAGSVERSJON=V2` eller `OPPDRAGSVERSJON=V3` fra den eksplisitte opprettelsen, og dette er unntaket som ikke trenger oppdragstilstand-endepunktet.
Bruk denne verdien eller en annen autoritativ kontroll i manifestets `VERSJON`.
Ikke utled manifestets `VERSJON` fra datoen i saksnummeret alene.
`fullfor MANIFEST.tsv` leser saksnummer fra første kolonne eller en ren saksnummerlinje, hopper over duplikater og endrer ikke en allerede vedtatt nyeste papirsøknad.
En delvis aktiv papirsøknad føres bare videre når den også er sakens nyeste søknadsbehandling.
`simuler-gate` og `utbetaling` krever fire TSV-felt i denne rekkefølgen: `SAKSNUMMER`, `VERSJON`, `OPPDRAG_BEREGNET`, `SIMULERING_OK`.
Overskriften er valgfri; tomme linjer og kommentarer som starter med `#` er tillatt, og bekreftelsesfeltene må være `ja` eller `nei`.
Bare `ja` passerer bekreftelsesgaten, og `simuler-gate` er skrivebeskyttet og kan kontrollere saker som allerede har meldekortbehandlinger.
`simuler-gate` leser `GET /sak/{saksnummer}/oppdragstilstand` for hver rad og blokkerer når svaret ikke kan leses sikkert.
`utbetaling` godtar bare `VERSJON=V3` og avviser saker med eksisterende meldekortbehandlinger i de to første kjedene eller en aktiv flyt.
`utbetaling` kjører den samme oppdragstilstand-kontrollen både i gaten og rett før første mutering i hver sak, og stopper hvis endepunktet ikke kan leses.
Kjør først `simuler-gate` for en skrivebeskyttet kontroll, og kjør `utbetaling` bare når alle sakene er klare.
`OPPDRAG_BEREGNET=ja` betyr at operatøren har bekreftet at Oppdragssystemet fullførte en relevant Q1-beregning etter at saken ble `VEDTATT`.
Beregningens faktiske tidsplan er ikke verifisert.
`SIMULERING_OK=ja` bekrefter at en faktisk, separat simulering viste forventet Q1-resultat.
Før du iverksetter et meldekort, sender en V3-melding eller går videre med migrering, må simuleringen vise forventet Q1-resultat.
Registrer forventet Q1-resultat og eventuelle avvik for hver sak og hvert scenario.
Skriptet venter ikke på et klokkeslett, poller ikke Oppdragssystemet og bruker ikke noe Hel Ved-statusendepunkt.
Dolly- og Modia-oppretting, tokenfornyelse og eksterne statuser er manuelle eller eksterne forutsetninger.
Skriptet automatiserer ikke duplikater, rekkefølgefeil, timeoutinjeksjon eller produksjon.
Oppdragstilstand-endepunktet brukes bare i lokal/dev og aldri i produksjon.
Hel Ved V3-saker dokumenterer ikke migrering; normal migrering krever egne V2-saker og avklart historikk.
Normal migrering skal aldri bruke `opphevSperrenStraks=true` eller `migrer-uten-kontrollsimulering.sh` som bevis.
`verifiser-helved` bruker bare Peisschtappern-endepunktet `GET /api/saker/<saksnummer>/TILTPENG` med eksternt Hel Ved-saksnummer, ikke id fra saksbehandlings-API-et `sak_*`.
Kommando: `./helved-v3-scenarioer.sh verifiser-helved helved-verifisering.tsv`.
Verifiseringen er skrivebeskyttet og erstatter ikke simulering, migreringsbevis, driftsskjema eller vurdering av personopplysninger.
Kommandoen trenger ikke OBO-tokens, men den krever naisdevice mot intern dev og tilgang til tokengeneratorens offentlige maskintokenendepunkt.

## Nyttig å vite (så du ikke gjetter)

- Auth mot LokalMain bruker fake Texas-tokens: saksbehandler `TokenMcTokenface` (A123456), beslutter `TokenMcTokenface2` (B123456). To brukere pga. 4-øyne.
- Papir lokalt bruker fnr `12845678911` (matcher SAF-fakens journalpost `12345`).
- `kjedeId` inneholder `/` og må URL-encodes (`%2F`) — scriptene håndterer dette.
- Papir-utledning av tiltaksdeltakelse i client-fakene er kjent skjør; scriptene har en fallback. Se TODO-ene i `TiltaksdeltakelseFakeKlient.kt` / `LocalApplicationContext.kt`.

## Full dokumentasjon

Scripts, curl og GUI fra A til Å (digital + papir):
`tiltakspenger-saksbehandling/docs/opprette-behandlinger-lokalt.md`.
