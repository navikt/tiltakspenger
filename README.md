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

For å legge til et nytt repo kan man skrive

```
meta project import tiltakspenger-whatnot git@github.com:navikt/tiltakspenger-whatnot
```

Se [meta](https://github.com/mateodelnorte/meta) for flere kommandoer.

Dersom du nå åpner `build.gradle` med `Open` (som Project) i IntelliJ så får du alle komponentene inn i ett
IntelliJ-oppsett.

Repoene som er inkludert i dette meta-repoet er

- [tiltakspenger-iac] (https://github.com/navikt/tiltakspenger-iac)
- [tiltakspenger-libs] (https://github.com/navikt/tiltakspenger-libs)
- [tiltakspenger-arena] (https://github.com/navikt/tiltakspenger-arena)
- [tiltakspenger-saksbehandling-api] (https://github.com/navikt/tiltakspenger-saksbehandling-api)
- [tiltakspenger-tiltak] (https://github.com/navikt/tiltakspenger-tiltak)
- [tiltakspenger-saksbehandling] (https://github.com/navikt/tiltakspenger-saksbehandling)
- [tiltakspenger-soknad-api] (https://github.com/navikt/tiltakspenger-soknad-api)
- [tiltakspenger-soknad-mock-api] (https://github.com/navikt/tiltakspenger-soknad-mock-api)
- [tiltakspenger-pdfgen] (https://github.com/navikt/tiltakspenger-pdfgen)
- [tiltakspenger-soknad] (https://github.com/navikt/tiltakspenger-soknad)
- [tiltakspenger-datadeling] (https://github.com/navikt/tiltakspenger-datadeling)
- [titlakspenger-meldekort] (https://github.com/navikt/tiltakspenger-meldekort)
- [titlakspenger-meldekort-api] (https://github.com/navikt/tiltakspenger-meldekort-api)

Lenker til PR-sidene
- [tiltakspenger-arena] (https://github.com/navikt/tiltakspenger-arena/pulls)
- [tiltakspenger-datadeling] (https://github.com/navikt/datadeling/pulls)
- [tiltakspenger-iac] (https://github.com/navikt/tiltakspenger-iac/pulls)
- [tiltakspenger-libs] (https://github.com/navikt/tiltakspenger-libs/pulls)
- [tiltakspenger-pdfgen] (https://github.com/navikt/tiltakspenger-pdfgen/pulls)
- [tiltakspenger-soknad] (https://github.com/navikt/tiltakspenger-soknad/pulls)
- [tiltakspenger-soknad-api] (https://github.com/navikt/tiltakspenger-soknad-api/pulls)
- [tiltakspenger-soknad-mock-api] (https://github.com/navikt/tiltakspenger-soknad-mock-api/pulls)
- [tiltakspenger-tiltak] (https://github.com/navikt/tiltakspenger-tiltak/pulls)
- [tiltakspenger-saksbehandling] (https://github.com/navikt/tiltakspenger-saksbehandling/pulls)
- [tiltakspenger-saksbehandling-api] (https://github.com/navikt/tiltakspenger-saksbehandling-api/pulls)
- [tiltakspenger-meldekort] (https://github.com/navikt/tiltakspenger-meldekort/pulls)
- [tiltakspenger-meldekort-api] (https://github.com/navikt/tiltakspenger-meldekort-api/pulls)

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

### Import av data til lokale databaser

Det kan være praktisk å populere lokale databaser med data fra dev-miljøet. Du trenger `pg_dump` og `pg_restore` fra [Postgres binaries](https://www.postgresql.org/download/).

#### Fremgangsmåte
Eksempel for saksbehandling-api, se docker-compose for parametre for andre apper.

- Start den lokale databasen:
```
docker compose up -d postgresSaksbehandling
```

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
