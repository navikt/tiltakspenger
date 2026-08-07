# Lesetoken for `gh`

`gh auth login` lager et OAuth-grant med `repo` — full lese- og skrivetilgang til hvert private og interne repo kontoen når — pluss `workflow`, og `admin:public_key` hvis du lar den håndtere SSH-nøkler for deg.
Grantet har ingen utløpsdato.

Et fine-grained personal access token med bare lesetillatelser er et smalere alternativ: det er begrenset til repoene du velger, det dør av seg selv, og det kan ikke skrive noe sted.

Prinsippet er at legitimasjon som er tilgjengelig hele tiden bare skal kunne lese.
Push går uansett ikke med token, men over ssh med en nøkkel i maskinvare — se [ssh-nokkel-mac.md](ssh-nokkel-mac.md).

## 1. Lag tokenet

<https://github.com/settings/personal-access-tokens/new>

| Felt | Verdi |
|---|---|
| Expiration | 90 dager |
| Resource owner | `navikt` |
| Repository access | Only select repositories |

Velg repoene du faktisk jobber i. For `tiltakspenger` er det disse:

```
tiltakspenger                          tiltakspenger-meldekort-microfrontend
tiltakspenger-arena                    tiltakspenger-pdfgen
tiltakspenger-datadeling               tiltakspenger-pdfgenrs
tiltakspenger-iac                      tiltakspenger-saksbehandling
tiltakspenger-journalposthendelser     tiltakspenger-saksbehandling-api
tiltakspenger-libs                     tiltakspenger-soknad
tiltakspenger-meldekort                tiltakspenger-soknad-api
tiltakspenger-meldekort-api            tiltakspenger-tiltak
```

Velg **ikke** `All repositories`.
Tillatelsene i et fine-grained token gjelder likt for alle valgte repoer, så `All repositories` med `Contents: read` gir tokenet lesetilgang til alt kontoen når — inkludert interne repoer i hele organisasjonen.

### Repository permissions

Sju stykker, alle **Read-only**:

```
Actions            Contents      Issues     Pull requests
Commit statuses    Deployments   Metadata
```

Alt annet står på **No access**, og det er standardverdien — du skal bare endre disse sju.

To rader er verdt å forstå framfor å hoppe over:

**Workflows: No access** er sperren mot å endre workflow-filer.

**Code scanning alerts, Dependabot alerts og Secret scanning alerts: No access.**
Det er fristende å tenke at lesetilgang er gratis når repoet er offentlig, men varslene er ikke offentlige selv om koden er det. Målt uten pålogging mot et offentlig repo 2026-08-07:

```
actions/runs           200   offentlig
deployments            200   offentlig
code-scanning/alerts   401   ikke offentlig
dependabot/alerts      401   ikke offentlig
```

Et secret scanning-varsel peker dessuten rett på hvor en levende hemmelighet ligger i kildekoden.

### Organization permissions

Dette er en **egen bolk under** repo-tillatelsene, med sine egne rader, og den er lett å gå glipp av.

- `Members: Read-only` — tilsvarer det gamle `read:org`
- `Projects: Read-only` — kreves for [team-boardet](https://github.com/orgs/navikt/projects/227). Uten den feiler `gh project` med `GraphQL: Resource not accessible by personal access token (organization.projectV2)`. Skal du flytte elementer mellom statuser fra kommandolinja, trengs `Read and write`.

Alt annet: **No access**.

## 2. Ta det i bruk

Kopier tokenet — det vises bare én gang — og sjekk at det er tokenet som ligger på utklippstavla før du piper det videre:

```sh
pbpaste | awk 'NR==1{ printf "lengde=%d  prefiks=%s\n", length($0), substr($0,1,11) }'
```

Forventet er `prefiks=github_pat_` og en lengde rundt 93.
En kopiert kommando piper like gjerne inn, gir `HTTP 401: Bad credentials`, og legger søppel i nøkkelringen så `gh` står utlogget etterpå.

```sh
pbpaste | gh auth login --hostname github.com --with-token
gh config set git_protocol ssh
```

`gh auth login` nullstiller `git_protocol` til `https`, så den siste linja er ikke valgfri hvis du vil at git skal bruke ssh.

## 3. Verifiser

```sh
gh auth status
gh api /user --include --silent 2>&1 | grep -i 'token-expiration\|x-oauth-scopes'
```

Innlogget mot `keyring`, en utløpsdato, og **ingen scope-header** — fine-grained tokens har ikke scopes.

Disse skal virke:

```sh
gh issue list -R navikt/<repo> --limit 3
gh run list -R navikt/<repo> --limit 3
gh pr list -R navikt/<repo> --limit 3
gh project view 227 --owner navikt
```

Denne skal feile med **403 «Resource not accessible by personal access token»**, som bekrefter at tokenet ikke når admin-flaten:

```sh
gh api repos/navikt/<repo>/branches/main/protection
```

Offentlige repoer som *ikke* står i utvalget er fortsatt lesbare — et fine-grained token sperrer ikke for offentlige data. HTTPS-kloner av offentlige repoer utenfor lista fungerer altså som før.

## 4. Trekk tilbake det gamle grantet

<https://github.com/settings/applications> → **GitHub CLI** → **Revoke access**.

Dette steget er lett å hoppe over, og det er det eneste som faktisk fjerner den gamle tilgangen.
At `gh` lokalt bruker et nytt token betyr ikke at det gamle er dødt — grantet lever hos GitHub til det trekkes.

Et OAuth-grant beholder dessuten unionen av alt som noen gang er innvilget, og `gh auth refresh` kan hente tillatelsene tilbake i et nytt token uten et nytt samtykkevindu. Derfor må hele grantet trekkes, ikke bare tokenet byttes.

## Dette virker bevisst ikke

- `gh issue create`, `edit` og `comment` svarer 403. Skriving krever et eget token.
- Push over HTTPS avvises. Push går over ssh.
- Private og interne repoer gir 404 hvis de ikke står i utvalget. Git-lesing der går over ssh; trenger du API-tilgang, lag et eget token med kort levetid for anledningen.

## Fornyelse

GitHub varsler før utløp.
På tokenets egen side finnes **Regenerate token**, som beholder repolista og tillatelsene — da holder det å kjøre kommandoene i steg 2 på nytt.
Å redigere tillatelser endrer derimot ikke tokenverdien, så det krever ingen ny innlogging.
