# Klassifiseringskriterier for hemmelighetssveipet

Reglene `klassifiser.py` gir hvert treff fra [navikt/gitleaks-wrapper](https://github.com/navikt/gitleaks-wrapper)
status etter. Fila er reglene alene — tall, filer og avgjørelser for ett bestemt sveip står i
`reports/sveip-<dato>/` (gitignorert), sammen med en kopi av denne fila slik den var da sveipet ble
klassifisert. Git-historikken her viser når en regel ble endret og hvorfor.

## Statusene

Wrapperen har tre statuser. Slik brukes de i baselinebeviset:

- **ok** — treffet er ikke en hemmelighet og ikke en personopplysning som trenger oppfølging. Kriteriet som ga ok står i begrunnelsesfila.
- **violation** — treffet skal følges opp: et fødselsnummer i ekte serie, eller en Nav-ident som kan være en ansatt. Oppfølgingsstatus (fortsatt i HEAD / fjernet i hvilken commit) står i baselinebeviset.
- **unsure** — ingen regel avgjør treffet entydig. Lista skal være kort og avgjøres av et menneske i wrapperens `run.py review --status-filter unsure`. Tvil gir alltid unsure, aldri ok.

Én review-nøkkel er `repo:commit:fil:regel:linje`. Når flere treff står på samme linje deler de nøkkel
(kjent begrensning i wrapperen); da får nøkkelen den strengeste statusen av treffene på linja
(violation > unsure > ok), og begrunnelsesfila viser hvert treff for seg.

Statuser et menneske har satt i `review.json` (ok eller violation) vinner over reglene ved neste kjøring,
og listes som manuelle avgjørelser i baselinebeviset. `unsure` er aldri en avgjørelse og overstyres
av reglene. `--regler-vinner` nullstiller alle manuelle avgjørelser.

## Teststi (brukes av flere regler)

En sti regnes som **test-/utviklingsdata** når den treffer ett av disse mønstrene (`TESTSTI` i skriptet):

- katalognavn `test`, `tests`, `testdata`, `__tests__`, `fixture(s)`, `mock(s)`, `mockdata`, `data`, `e2e`, `cypress`, `playwright`, `stories`, `storybook`, `demo`, `local`, `lokal`, `local-migration(s)`, `mock-req-res`, `labs`
- filnavn `*.test.*`, `*.spec.*`, `*.stories.*`, `*Test.kt/java/ts/tsx/js/py`
- `src/test/` hvor som helst i stien
- `mock`/`Mock`/`fake`/`Fake` som del av stien

`local-migration(s)` er med fordi det er Flyway-seed for lokal utviklingsdatabase (kjøres aldri i dev/prod).
Stier som *ikke* treffer: `src/main` (utenfor local-migration), `docs/`, `doc/`, rotfiler som `AGENTS.md`,
`README.md`, `build.gradle.kts`, `.nais/vars/*.yml` (unntatt `labs`).

## Kriterier per regel

### `off-id` — 11 sifre (kandidat for fnr/dnr/hnr/tnr)

Hvert treff kjøres gjennom wrapperens `validate.py` (navikt/fnrvalidator-logikken, med 2032-regelen for k1).

| Resultat fra validate | Sti | Status | Kriterium-kode |
|---|---|---|---|
| ugyldig (kontrollsiffer eller dato stemmer ikke) | alle | ok | `offid-ugyldig` |
| `tnr` / `dnr-and-tnr` (måned 81–92, Test-Norge) | alle | ok | `offid-tnr` |
| `hnr` / `dnr-and-hnr` (måned 41–52, Dolly-serien) | teststi | ok | `offid-hnr-teststi` |
| `hnr` / `dnr-and-hnr` | ikke teststi, men samme verdi finnes i en teststi i samme repo | ok | `offid-hnr-samme-som-testdata` |
| `hnr` / `dnr-and-hnr` | ikke teststi | ok | `offid-hnr-utenfor-teststi` |
| `fnr` / `dnr` (ekte serie) | alle | violation | `offid-fnr-ekte-serie` |

Et fødselsnummer/d-nummer fra Folkeregisteret har fødselsdato i posisjon 1–6 (dag, måned, år; d-nummer har
dag + 40), jf. [Skatteetatens beskrivelse av oppbygningen](https://skatteetaten.github.io/folkeregisteret-api-dokumentasjon/nytt-fodselsnummer-fra-2032/)
(2032-endringen gjelder bare k1). Måned 41–52 og 81–92 er derfor aldri et gyldig fnr/dnr: +40-serien brukes av
Dolly (Nav syntetisk testpopulasjon) og som hjelpenummer i helsesektoren, +80 av Test-Norge. Navs identvalidator
avviser numre i +40-serien som reelt nummer («ugyldig dato … i formatet ddMMyy»), så et slikt nummer kan ikke
identifisere en person i produksjon. Hjelpenummer-forbeholdet i fnrvalidator er ikke relevant for Nav, som ikke
bruker hjelpenummer som identifikator. De tre hnr-radene har hver sin kode for sporbarhet, ikke fordi utfallet er ulikt.

Ikke-reelle numre (ugyldig, +40, +80) er ikke personopplysninger og listes ut med verdi i
`ikke-reelle-numre.md`, kommaseparert per repo, så de kan limes inn i
[Dollys identvalidator](https://dolly.ekstern.dev.nav.no/identvalidator) (krever innlogging) som kontroll:
alle skal komme ut som syntetiske eller ugyldige (`erSyntetisk`/`erGyldig`), ingen i ekte serie. Nedlastingen
`identvalidering.csv` legges i sveipmappa, og skriptet skriver kontrollresultatet inn i beviset.

Numre i ekte serie regnes som violation uansett sti — også i tester — fordi de kan tilhøre en person og skal
byttes til åpenbart fiktive sifre (teamets regel for ny kode). Verdiene skrives aldri til rapportene;
`run.py secrets --rule-filter off-id --status-filter violation` i wrapperen viser dem for den som skal følge opp.

### `nav-ident` — bokstav + 6 sifre

| Treff | Status | Kriterium-kode |
|---|---|---|
| Forbokstav `Z`/`z` | ok | `navident-z-testbruker` |
| Sifrene er alle like (f.eks. 111111) eller en stigende/fallende rekke (f.eks. 123456, 654321) | ok | `navident-plassholder` |
| Alt annet | violation | `navident-mulig-ansatt` |

Z-identer er testbrukere i dev/Dolly, og rekke- eller repetisjonssifre er åpenbare plassholdere (står i tester
og dokumentasjon sammen med navn som «Superman»). Øvrige identer kan tilhøre ansatte og følges derfor opp som
violation. Regelen `\b[A-Za-z][0-9]{6}\b` gir ikke treff på UUID-er eller hex-hasher (ordgrensen krever
ikke-ordtegn før bokstaven).

### `nav-email` / `trygdeetaten-email` / `slack-email`

Alle → **ok**, kriterium `epost-jobbadresse`. Jobbadresser i kode, seed-data, alert-mottakere og dokumentasjon
er kontaktopplysninger, ikke hemmeligheter, og ingen av dem gir tilgang til noe.

### `JDBC` / `Postgres` (trufflehog)

Vert og passord leses ut av tilkoblingsstrengen maskinelt (verdien skrives aldri ut).

| Treff | Status | Kriterium-kode |
|---|---|---|
| Treffet er en Maven-koordinat for en JDBC-driver i `build.gradle.kts` (`com.oracle.database.jdbc:…`), ikke en tilkoblingsstreng | ok | `db-maven-koordinat` |
| Strengen er en mal, ikke en tilkoblingsstreng: `<vert>`-plassholdere i kildelinja, eller Kotlin-templatevariabler (`$vert`, `$passord`, `${…}`) som vert/passord | ok | `db-plassholder-mal` |
| Vert er `localhost`, `host.docker.internal` eller `127.0.0.1`, og passordet (om det finnes) er et generisk utviklingspassord (`postgres`, `test`, `password`, `passord`, `passord1`, `hemmelig`, `hemmelighet`, `testpassord`, `dummy`, `secret`, `admin`, `root`, tomt) | ok | `db-lokal-utviklingsdatabase` |
| Vert er et navn uten punktum i en fil under en `lokal`-/`local`-sti (docker-compose-tjenestenavn), med utviklingspassord som over | ok | `db-compose-tjenestenavn` |
| Alt annet (vert med punktum, ukjent passord, ukjent form) | unsure | `db-ukjent` |

trufflehog kjøres av wrapperen med `--no-verification`; ingen tilkoblingsstreng er prøvd mot en tjener.

### `generic-api-key` (gitleaks standardregel)

| Treff | Status | Kriterium-kode |
|---|---|---|
| Den fangede «nøkkelen» er et Kotlin-parameternavn brukt som navngitt argument (`<verdi> = …` på en linje i fila) | ok | `gak-parameternavn` |
| Fila er `.nais/vars/*.yml` og verdien er et vertsnavn (kun små bokstaver, sifre, punktum, bindestrek) | ok | `gak-vertsnavn-nais-vars` |
| Fila ligger under `local-migration(s)/` og kildelinja er en `INSERT`/`VALUES`-rad — verdien er en kolonneverdi i Flyway-seed for lokal database | ok | `gak-seed-verdi` |
| Alt annet | unsure | `gak-ukjent` |

gitleaks' generiske regel utløses av ordet «key»/«token» i nærheten; i denne kodebasen fanger den
parameternavnet i `withSaksbehandler(tokenService = tokenService, <parameter> = false)`.

### `TrelloApiKey` (trufflehog)

| Treff | Status | Kriterium-kode |
|---|---|---|
| Kildelinja med verdien inneholder `trello.com/c/` — den 32 tegn lange «nøkkelen» er URL-sluggen til et Trello-kort i en kodekommentar | ok | `trello-kortlenke` |
| Alt annet | unsure | `trello-ukjent` |

Kildelinja slås opp ved å søke etter verdien i fila slik den var i commiten, fordi trufflehog oppgir
linjenummer i diffen for noen treff.

### Ukjente regler

Treff fra regler uten kriterium her får `unsure` med kode `ukjent-regel-<regel-id>`. Da skal denne fila utvides
før treffene avgjøres.

## Utenfor review-modellen

trufflehog-treff i commit-*meldinger* har ingen filreferanse og tas ikke inn i wrapperens rapporter eller
`review.json`. Skriptet teller dem per repo og detektor i baselinebeviset; de vurderes manuelt der
(hittil: Snyks prosjekt-ID i lenka i Snyks egne oppgraderings-PR-meldinger — ikke en hemmelighet).

## Slik etterprøves en klassifisering

1. `reports/sveip-<dato>/kriterier.md` er reglene som gjaldt; `kjøringsbevis`-blokka øverst i
   `baselinebevis.md` sier hvilken commit av skriptet som kjørte, når, og mot hvilke rapportfiler.
2. `begrunnelser.csv` har én rad per treff med kriteriekoden — hvert tall i baselinebeviset kan regnes ut
   derfra.
3. `python3 run.py report` i wrapperen skal vise **Todo: 0**; utskriften ligger som `rapport.txt`.
4. `run.py show --status-filter violation` og `--status-filter unsure` i wrapperen viser radene med verdi og
   kodekontekst for den som skal avgjøre eller kontrollere — utskriften lagres ikke.
5. Skriptet endrer ingenting i wrapperens `repos/` (kun lesende git-kommandoer) og kjører ikke sveipet på nytt.
