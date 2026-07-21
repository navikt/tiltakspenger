---
name: tiltakspenger-testdata
description: Lag testdata lokalt for tiltakspenger-saksbehandling via ferdige scripts — testsak med innvilget vedtak, meldekortbehandling, klagebehandling, eller digital-/papirsøknad seedet mot LokalMain. Kan også forhåndsvise og lagre PDF-brevene fra pdfgen og pdfgenrs.
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

| Utvikleren vil ha | Kjør |
| --- | --- |
| Alt (sak + meldekort + klage) | `opprett-alt-digital.sh` / `opprett-alt-papir.sh` |
| Bare en sak med innvilget vedtak | `opprett-innvilget-sak-digital.sh` / `opprett-innvilget-sak-papir.sh` |
| Bare en meldekortbehandling | innvilget sak-script, deretter `opprett-meldekortbehandling.sh SAK_ID KJEDE_ID` |
| Bare en klagebehandling | `opprett-klage.sh SAK_ID [VEDTAK_ID]` (på en eksisterende sak) |
| Alle PDF-brevene som filer | `forhandsvis-alle-pdfer.sh` (krever pdfgen på 8081 + pdfgenrs på 8084 i docker) |
| Ett enkelt PDF-brev | `forhandsvis-vedtaksbrev.sh` / `forhandsvis-meldekortbrev.sh` / `forhandsvis-klagebrev.sh` |
| Ett enkelt endepunkt-steg | tilsvarende byggekloss-script (se `scripts/testdata/README.md`) |

PDF-scriptene lagrer til `$PDF_UT_DIR` (default `/tmp/tiltakspenger-pdfer`), med
både pdfgen- og pdfgenrs-variant av hvert brev (lokal skygge-kjøring) slik at de
kan sammenlignes. PDF-er som kun genereres av jobber (journalføring) dekkes ikke.

## Nyttig å vite (så du ikke gjetter)

- Auth mot LokalMain bruker fake Texas-tokens: saksbehandler `TokenMcTokenface` (A123456), beslutter `TokenMcTokenface2` (B123456). To brukere pga. 4-øyne.
- Papir bruker fnr `12345678911` (matcher SAF-fakens journalpost `12345`).
- `kjedeId` inneholder `/` og må URL-encodes (`%2F`) — scriptene håndterer dette.
- Papir-utledning av tiltaksdeltakelse i client-fakene er kjent skjør; scriptene har en fallback. Se TODO-ene i `TiltaksdeltakelseFakeKlient.kt` / `LocalApplicationContext.kt`.

## Full dokumentasjon

Scripts, curl og GUI fra A til Å (digital + papir):
`tiltakspenger-saksbehandling/docs/opprette-behandlinger-lokalt.md`.
