---
name: gcp-tilgangsopprydding
description: Fjern GCP-tilgangen til folk som har sluttet i teamet. Dekker alle tre lagene tilgang ligger i — prosjekt-IAM, BigQuery-datasett-ACL og tjenestekonto-IAM. Bruk ved offboarding eller tilgangsrevisjon.
license: MIT
metadata:
  domain: sikkerhet
  tags: gcp iam offboarding tilgang bigquery tjenestekonto nais gcloud
---

# GCP-tilgangsopprydding

Oppskrift for å fjerne tilgangen til folk som har sluttet i teamet, uten å klikke seg gjennom konsollet.

> Verktøy-uavhengig `SKILL.md` — se [`../README.md`](../README.md) for hvordan du aktiverer den.

## Rammer

- **Ingenting fjernes uten at et menneske har sett listen.** Tørrkjør alltid først og legg fram endringene linje for linje. Vent på et eksplisitt ja før du skriver.
- **Bygg inn en behold-sperre.** Legg de som skal bli inn i en liste skriptet sjekker jobblista mot, og la det avbryte hele kjøringen ved treff. Billig forsikring mot en tastefeil i en e-postadresse.
- **Ikke skru på API-er, ikke endre kvoter, ikke rør noe utenfor de navngitte personene.** Å aktivere et API er en endring i prosjektet.
- **«Står ikke i Nais-teamet» er et signal, ikke bevis.** Designere, analytikere og folk fra nabo-team kan ha legitim tilgang uten å være teammedlemmer. Spør før du fjerner noen som ikke er bekreftet ute.

## Prosjekter

`tpts-dev-6211`, `tpts-prod-b5ff`, `tpts-ci-db2c` (sistnevnte har normalt ingen brukerbindinger).

## Steg 1 — teammedlemskapet

Nais-teamet er kilden. Fjern der først; reconcilerne trekker gruppetilgangen (`group:tpts@nav.no`), GitHub-teamet og namespace-tilgangen.

```bash
nais members list -t tpts                 # hvem står der, og hvem er eier
nais members remove <e-post> -t tpts      # krever at du er eier
```

Et teammedlem **uten** direkte binding er det normale og riktige — tilgangen går via gruppa.

## Steg 2 — de tre lagene med rester

Teamfjerning rører ikke håndlagte grants. De ligger i tre lag, og IAM-siden i konsollet viser bare det første.

### Lag 1: prosjekt-IAM

```bash
for P in tpts-dev-6211 tpts-prod-b5ff; do
  gcloud projects get-iam-policy "$P" --format=json \
  | jq -r --arg p "$P" '.bindings[] | .role as $r | (.condition.title // "UBETINGET") as $c
      | .members[] | select(startswith("user:")) | [ltrimstr("user:"), $r, $c, $p] | @tsv'
done | sort -f | column -t -s $'\t'
```

Skill mellom to slag bindinger — forskjellen avgjør alt:

- **Betingede** med tittel `nais_cli_access` eller `temp_access` lages automatisk av nais CLI ved postgres-tilkobling, med utløpstid i uttrykket. Utløpte gir null tilgang. De er støy som gjør policyen uleselig, ikke en lekkasje.
- **Ubetingede** er den faktiske, levende tilgangen. Det er disse som betyr noe.

Fjerning:

```bash
gcloud projects remove-iam-policy-binding <prosjekt> \
  --member="user:<e-post>" --role=<rolle> --all
```

`--all` tar bindingen uansett betingelse, som er det du vil når noen skal helt ut. Uten `--all` må betingelsen oppgis for å skille duplikate rader (samme rolle finnes ofte både betinget og ubetinget).

### Lag 2: BigQuery-datasett-ACL

**Dette er det laget folk glemmer.** Datasett-ACL-er ligger utenfor prosjektets IAM-policy: de vises ikke i `get-iam-policy`, og `remove-iam-policy-binding` rører dem ikke. En som har sluttet kan stå som `OWNER` på et prod-datasett uten at det er synlig noe sted i IAM-fanen.

```bash
for P in tpts-dev-6211 tpts-prod-b5ff; do
  for D in $(bq --project_id="$P" ls --format=json | jq -r '.[]?.datasetReference.datasetId'); do
    bq --project_id="$P" show --format=prettyjson "$P:$D" \
    | jq -r --arg d "$P:$D" '.access[]? | select(.userByEmail)
        | "  \($d)  \(.userByEmail)  →  \(.role)"'
  done
done
```

Skriving går via hele datasettobjektet:

```bash
bq --project_id=<p> show --format=prettyjson <p>:<datasett> > naa.json
jq '.access = [.access[] | select((.userByEmail // "") != "<e-post>")]' naa.json > ny.json
bq --project_id=<p> update --source=ny.json <p>:<datasett>
```

**Sjekk eierskap før du fjerner en `OWNER`.** Datasettet må beholde minst én — `specialGroup: projectOwners` holder. La skriptet avbryte hvis fjerningen ville gjort datasettet eierløst.

### Lag 3: tjenestekonto-IAM

Hvem som kan opptre som eller forvalte tjenestekontoene. `roles/iam.serviceAccountAdmin` på `tpts-terraform@` er den bredeste enkelttilgangen som finnes utenfor prosjektpolicyen — den lar deg forvalte kontoen som provisjonerer infrastrukturen.

```bash
for P in tpts-dev-6211 tpts-prod-b5ff; do
  for SA in $(gcloud iam service-accounts list --project="$P" --format='value(email)'); do
    gcloud iam service-accounts get-iam-policy "$SA" --project="$P" --format=json \
    | jq -r --arg s "$P/$SA" '.bindings[]? | .role as $r
        | .members[]? | select(startswith("user:")) | "  \($s)  \(ltrimstr("user:"))  →  \($r)"'
  done
done

gcloud iam service-accounts remove-iam-policy-binding <sa> \
  --member="user:<e-post>" --role=<rolle> --project=<prosjekt>
```

## Fallgruver

- **`gcloud asset search-all-iam-policies` virker ikke.** Cloud Asset API er avslått i prosjektene, og gcloud svarer med en interaktiv «enable and retry? (y/N)» som i et ikke-interaktivt skall ser ut som at kommandoen henger. Gå rett på ressurstypene i stedet, slik stegene over gjør.
- **`del_`-prefiks** på en e-postadresse betyr at kontoen alt er deaktivert i AD. Bindingen er død, men rydd den vekk.
- **Cloud SQL har ikke policy per instans** — kun prosjektnivå, så lag 1 dekker den.
- **Sikkerhetskopi og tilbakerulling.** Ta `get-iam-policy > backup.json` før du skriver, men vit at `set-iam-policy` avviser den etterpå fordi `etag` er utdatert. Det er en sikring, ikke en feil; feltet må strippes for å tvinge en tilbakerulling.
- **Verifiser at et negativt søk kunne gitt treff.** Et filter som ikke matcher noe ser identisk ut med «ingenting å rydde». Sjekk at før- og etterbildet faktisk er forskjellig, og at ressurstypene du søkte i finnes.

## Sluttverifisering

Kjør alle tre lagene på nytt med de fjernede adressene som filter, og få `RENT` i hvert lag før du melder ferdig. List til slutt opp hvem som fortsatt har direkte tilgang, og kontroller den mot `nais members list`.
