# Databasene i dev og prod

Fem apper har hver sin Cloud SQL-instans per miljø.
Instansen har samme navn som appen.
Databasen heter:

| App | Database |
| --- | --- |
| `tiltakspenger-saksbehandling-api` | `saksbehandling` |
| `tiltakspenger-meldekort-api` | `meldekort` |
| `tiltakspenger-soknad-api` | `soknad` |
| `tiltakspenger-datadeling` | `datadeling` |
| `tiltakspenger-journalposthendelser` | `journalposthendelser` |

Oppsettet er likt i alle fem, og en endring i ett repo gjøres i de andre også.

## Miljø og team

Tilgangen er personlig og går gjennom [nais cli](https://cli.nais.io/nais_postgres.html) med naisdevice tilkoblet.
Nais beskriver hensikt og oppsett i [Personal access](https://docs.nais.io/persistence/cloudsql/how-to/personal-access/), [Grants and privileges](https://docs.nais.io/persistence/cloudsql/explanations/grants-and-privileges/) og [Users and roles](https://docs.nais.io/persistence/cloudsql/explanations/cloud-sql-users-and-roles/).
Dette dokumentet gjentar ikke det som står der, bare det som er vårt: navn, valg og fallgruver.
Kommandoene tar `-t tpts` og `-e dev-gcp` eller `-e prod-gcp`.
Oppgi miljøet med `-e` hver gang.
Da ser den som leser terminalhistorikken eller skriptet hvilket miljø kommandoen gikk mot.
Vil du ha en [default](https://cli.nais.io/nais_defaults.html), la den peke på dev:

```sh
nais defaults set team tpts
nais defaults set environment dev-gcp
nais defaults list
```

Bruk `nais`-kommandoene der de finnes: `nais postgres`, `nais app`, `nais log`, `nais status` og `nais debug` går gjennom Nais-API-et og logges der.
`kubectl` brukes bare til det `nais` ikke dekker, som pods og andre Kubernetes-ressurser.
nais-defaultene gjelder ikke `kubectl`; den styres av kontekst og namespace.
Kontekstene heter `dev-gcp`, `prod-gcp`, `dev-fss` og `prod-fss`, og lages med `nais kubeconfig`:

```sh
kubectl config use-context dev-gcp
kubectl config set-context --current --namespace=tpts
kubectl config current-context
```

Bruker du begge verktøyene, sett dev som default i begge, og oppgi miljøet eksplisitt mot prod.

## Koble til

`--reason` er påkrevd og havner i revisjonsloggen.
Skriv hva du faktisk skal, for eksempel `"feilsøking av sak 202001019999"` eller `"kontroll av ny tabell utbetalingsoversikt i dev"`.

Kjør [`grant`](https://cli.nais.io/nais_postgres_grant.html) første gang du skal inn i en instans, og på nytt når tilgangen har utløpt; Nais gir tilgangen for en begrenset tid:

```sh
nais postgres grant tiltakspenger-saksbehandling-api -t tpts -e dev-gcp --reason "<hvorfor>"
```

Koble til med [`psql`](https://cli.nais.io/nais_postgres_psql.html) ved senere tilkoblinger:

```sh
nais postgres psql tiltakspenger-saksbehandling-api -t tpts -e dev-gcp --reason "<hvorfor>"
```

`psql` åpner en proxy på en tilfeldig port og et psql-skall i ett.
Skal du bruke et annet verktøy, start proxyen selv og koble til `localhost` på porten du valgte.
Bruk GCP-brukernavnet ditt (`gcloud config get-value account`), databasenavnet fra tabellen og tomt passord:

```sh
nais postgres proxy tiltakspenger-saksbehandling-api -p 5444 -t tpts -e dev-gcp --reason "<hvorfor>"
```

Import av dev-data til en lokal database står i [README](../../README.md#import-av-data-til-lokale-databaser).

## Rettigheter

Rettighetene styres av rollen `cloudsqliamuser`, som alle personlige brukere får.

- [`prepare`](https://cli.nais.io/nais_postgres_prepare.html) kjøres som appens databasebruker og gir rollen `USAGE` på skjemaet `public`, `SELECT` på alle tabeller og sekvenser, og `ALTER DEFAULT PRIVILEGES` for `SELECT` på det som lages senere.
  Den kjøres én gang per instans, av den som først trenger tilgang, og på nytt hvis instansen er migrert eller gjenopprettet:

  ```sh
  nais postgres prepare tiltakspenger-saksbehandling-api -t tpts -e dev-gcp --reason "<hvorfor>"
  ```

- Fire av repoene har en eldre migrering som gjør det samme som `prepare`, pakket i en sjekk på at rollen finnes.
  Nye repoer skal ikke ha en slik blokk: `prepare` og `revoke` er plattformens kontrollpunkt, begge revisjonslogges med `--reason`, og en migrering som gir tilgang på egen hånd kan åpne igjen det noen har trukket tilbake.
  Allerede kjørte migreringer endres ikke.
- Får du `permission denied for table …` på en ny tabell, mangler default-rettighetene i instansen.
  Sjekk i psql med `select defaclrole::regrole, defaclacl from pg_default_acl;`.
  Kjør `prepare` på nytt for å dekke både tabellene som finnes nå og dem som lages senere.
- [`revoke`](https://cli.nais.io/nais_postgres_revoke.html) trekker tilgangen tilbake fra rollen, også for tabeller som lages senere:

  ```sh
  nais postgres revoke tiltakspenger-saksbehandling-api -t tpts -e dev-gcp --reason "<hvorfor>"
  ```

## Prod

Prod inneholder personopplysninger.
Bruk `psql` framfor en dump.
Hent bare det du trenger, unngå `select *`.
Ta aldri data ut av basen uten avtale.
Skript og dokumentasjon ligger i offentlige repoer: ingen saksnummer, personopplysninger eller spørringsresultater der.
