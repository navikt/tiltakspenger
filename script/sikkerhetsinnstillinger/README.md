# sikkerhetsinnstillinger

Sammenligner utvalgte sikkerhetsinnstillinger fra GitHubs REST-API på tvers av teamets repoer og skriver én
Markdown-rad per repo, slik at avvik er synlige. Bruker bare `GET` og setter ingenting.

Kolonnene: CodeQL default setup mot egen workflow, Dependabot alerts og security updates, om `dependabot.yml`
finnes, secret scanning med push protection og validity checks, generic patterns, AI-detected secrets og
delegert dismissal/bypass, private vulnerability reporting, org-nivå security configuration,
GITHUB_TOKEN-rettigheter og rulesets. Arkiverte repoer listes under tabellen. Verdier som mangler eller ikke kan
leses markeres som ukjente, aldri som «av», og under tabellen står hva hver statuskode som forekom betyr.

Skriptet dekker ikke det som ikke er funnet i REST-API-et: Copilot Autofix, grouped security updates, malware
alerts, extended metadata, automatic dependency submission, custom patterns og «prevent direct alert dismissals»
for Dependabot og code scanning. De leses i UI-et.

## Bruk

```sh
./script/sikkerhetsinnstillinger/sikkerhetsinnstillinger.sh
REPOS="navikt/tiltakspenger-libs" ./script/sikkerhetsinnstillinger/sikkerhetsinnstillinger.sh
```

Repoene oppdages fra git-remotene under metarepo-rota, som i `script/status.sh`. Krever `gh`, `jq`, `python3`
og `base64`.

## Tilgang

Det meste krever repo-tillatelsen «Administration» (lesing), som det vanlige `gh`-lesetokenet mangler. Lag et
fine-grained token med Administration: read og Metadata: read på teamets repoer. Private repoer trenger i
tillegg Contents: read for filene, og `org-config` svarer 403 også med Administration; hvilken tillatelse den
krever er ikke kjent.

Skriv aldri tokenet på kommandolinja. Skriptet henter det, i denne rekkefølgen, fra `GH_TOKEN` i miljøet, fra
`TOKEN_KOMMANDO` (en kommando som skriver tokenet til stdout, f.eks. fra Keychain eller en age-fil) eller ved
skjult innliming når det kjøres i en terminal. `UTEN_TOKEN=1` bruker `gh` sin vanlige innlogging. Detaljene står
i toppen av skriptet.
