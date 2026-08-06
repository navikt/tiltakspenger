---
name: github-issues-revisjon
description: Periodisk revisjon av GitHub-issues på tvers av tiltakspenger-repoene — sjekk prosjektdekning, finn duplikater/overlapp, verifiser ferdig-kandidater mot koden før lukking, og finn manglende kryss-lenker. Bruk for å «gå over issuene», rydde i backloggen eller kvalitetssikre issue-sporingen.
license: MIT
metadata:
  domain: admin
  tags: github issues prosjekt backlog opprydding labels
---

# GitHub-issues-revisjon

Strukturert arbeidsflyt for å revidere GitHub-issuene i tiltakspenger-repoene (metarepoet + alle sub-repoene under `navikt/tiltakspenger*`). Målet er en ærlig backlog: alt spores i teamprosjektet, ingen dubletter, ingenting står åpent som egentlig er ferdig, og beslektede saker peker på hverandre.

> Denne skillen følger det åpne «Agent Skills»-formatet (`SKILL.md` med YAML-frontmatter) og er **verktøy-uavhengig** — ren markdown-instruksjon som kan brukes av en hvilken som helst agent/LLM-CLI (GitHub Copilot, open source-verktøy som OpenCode, lokale LLM-er osv.). Se [`../README.md`](../README.md) for hvordan du aktiverer den i ulike verktøy.

## Viktige rammer

- **Lukk aldri en issue uten kodeverifisering.** Tekst i issuen («kan være ferdig», avhukede sjekkbokser) er et signal, ikke bevis — verifiser mot fersk `origin/main` først.
- **Spør et menneske ved tvil.** Utfør trygge, reverserbare endringer (lenker, labels, body-oppdateringer) direkte; spør før lukking av saker du ikke fikk verifisert fullt ut, og før sammenslåing av saker.
- **Verktøynøytral omtale.** Ingen leverandørnavn utover GitHub Copilot og open source-verktøy (f.eks. OpenCode) i noe som publiseres (issues, labels, kommentarer).
- Krever `gh` autentisert mot `navikt` med prosjekt-scope (`gh auth refresh -s project` ved behov).

## Nøkkel-ID-er

- Teamprosjektet er **nr. 227 «Team tiltakspenger»** (owner `navikt`, project-id `PVT_kwDOALTM884Bctw1`).
- Status-feltet har id `PVTSSF_lADOALTM884Bctw1zhXUgas` med valgene: Trengs avklaring `7ab102d6`, Todo `f75ad846`, In Progress `47fc9ee4`, Done `98236657`, Ønsker fra saksbehandler `ed05a560`, Blokkert `1b41a788`.
- Label-konvensjoner: `agent` = velavgrenset teknisk oppgave en KI-agent kan ta (tydelig mål/mønster, ingen menneskelige beslutninger igjen); `avklaring` = trenger beslutning/utfylling — skal også ha status «Trengs avklaring» i prosjektet.

## Arbeidsflyt

### 1. Prosjektdekning

Alle åpne issues skal ligge i prosjekt 227.

Listene under må være **komplette** før `comm` betyr noe — en avkortet liste og en tom liste ser like ut, og forskjellen mellom dem er hele svaret.
Derfor sjekker hvert steg sin egen fullstendighet og avbryter framfor å rapportere på et utvalg.

```bash
set -e

# Alle items i prosjektet. Svaret oppgir .totalCount — bruk det som fasit, ikke et gjettet --limit.
gh project item-list 227 --owner navikt --limit 2000 --format json > prosjekt.json
jq -e '.totalCount == (.items | length)' prosjekt.json > /dev/null \
  || { echo "Prosjektlista er avkortet: $(jq '.totalCount' prosjekt.json) items finnes, $(jq '.items|length' prosjekt.json) hentet. Hev --limit."; exit 1; }
jq -r '.items[] | select(.content.type == "Issue") | "\(.content.repository)#\(.content.number)"' prosjekt.json | sort > prosjekt.txt

# Alle repoer med «tiltakspenger» i navnet. Søke-APIet oppgir total_count, så avkorting er synlig.
gh api '/search/repositories?q=org:navikt+tiltakspenger+in:name&per_page=100' > repoer.json
jq -e '.total_count == (.items | length) and (.incomplete_results | not)' repoer.json > /dev/null \
  || { echo "Repolista er ufullstendig: $(jq '.total_count' repoer.json) treff, $(jq '.items|length' repoer.json) hentet."; exit 1; }
# Søket treffer «tiltakspenger» hvor som helst i navnet, så prefikset filtrerer bort fremmede repoer
# (dvh_tiltakspenger, RPA_DIR_*Tiltakspenger*) som ikke er våre.
jq -r '.items[] | select(.archived | not) | select(.name | startswith("tiltakspenger")) | .full_name' repoer.json | sort > repoer.txt

# Alle åpne issues i de repoene. --state står eksplisitt: default er «open», og lukkede
# issues er usynlige helt til du ber om --state all.
: > aapne.txt
while read -r repo; do
  if ! gh issue list -R "$repo" --state open --limit 500 --json number > issues.json 2> issues.err; then
    # Issues avslått i repoet er et ekte «null åpne saker». Alt annet er en lesefeil vi ikke får overse.
    grep -q "disabled issues" issues.err || { echo "Klarte ikke lese issues i $repo:"; cat issues.err; exit 1; }
    continue
  fi
  test "$(jq 'length' issues.json)" -lt 500 \
    || { echo "$repo har minst 500 åpne issues — hev --limit."; exit 1; }
  jq -r --arg r "$repo" '.[] | "\($r)#\(.number)"' issues.json >> aapne.txt
done < repoer.txt
sort -o aapne.txt aapne.txt

comm -23 aapne.txt prosjekt.txt   # åpne issues som mangler i prosjektet
comm -13 aapne.txt prosjekt.txt   # prosjekt-items som er lukket (sjekk at status er Done)
```

Ikke bytt til `gh repo list navikt` for repo-oppslaget.
Organisasjonen har over 3000 repoer, og `gh repo list` kutter stille ved `--limit` uansett hvor høyt det settes — den utelater dessuten arkiverte repoer som default.
Målt 2026-08-06 traff `gh repo list navikt --limit 100 | grep '^tiltakspenger'` **2** repoer, mens søke-APIet fant **19** aktive (metarepoet + 18 sub-repoer).
Repoer med issues avslått (`tiltakspenger-interndokumentasjon`) får `gh issue list` til å avslutte med kode 1 og tom stdout.
Løkka skiller derfor det tilfellet fra en ekte lesefeil: uten den skillelinja stopper `set -e` sveipet ved fjerde repo, og resten blir aldri lest.
Kjør blokka som et skript og les exit-koden — kjører du den linje for linje, kan `set -e` oppføre seg annerledes enn i reell bruk.

Legg manglende issues inn med `gh project item-add 227 --owner navikt --url <issue-url>` og sett riktig status med `gh project item-edit`.
Les alltid tilbake at statusen faktisk står der før du rapporterer den som satt — se [Les tilbake etter skriving](#les-tilbake-etter-skriving) under.

### Les tilbake etter skriving

At `item-add` og `item-edit` returnerer en item-ID betyr bare at kallet ble tatt imot, ikke at feltet fikk verdien du ville ha.
Les tilbake fra issuen selv, som er et punktoppslag og derfor verken kan avkortes eller forveksles med en issue med samme nummer i et annet repo:

```bash
gh issue view <nr> --repo navikt/<repo> --json projectItems \
  -q '[.projectItems[] | "\(.title)=\(.status.name)"] | if length == 0 then "IKKE I NOE PROSJEKT" else join(", ") end'
# → Team tiltakspenger=In Progress
```

Tom liste her betyr at issuen ikke ligger i noe prosjekt — det er et ekte svar, ikke et uteblitt treff.
Bruk aldri `gh project item-list` til å bekrefte en enkelt skriving: den lista er over 500 items lang, kutter stille ved `--limit`, og inneholder items fra alle repoene, så et issue-nummer alene er tvetydig og må pares med `content.repository`.

### 2. Duplikater og overlapp

Hent titler + bodies for alle åpne issues og se etter par som beskriver samme behov eller samme situasjon fra to vinkler.

- Bevisste frontend/backend-par (samme funksjon i to repo) er **ikke** duplikater — men de skal kryss-lenke hverandre.
- Per-repo-varianter av samme oppgave (f.eks. samme migrering i alle repo) skal lenke en felles epic.
- Ved reelt overlapp: legg en `> [!NOTE]`-obs i begge med lenke til den andre og «kan påvirke hverandre, bør kanskje løses samtidig» — la et menneske avgjøre sammenslåing.

### 3. Ferdig-kandidater

Signaler: alle sjekkbokser avhuket, «kan være ferdig»/«vurder å lukke» i body, eller at koden åpenbart har endret seg siden issuen ble skrevet.

```bash
git -C <repo> fetch origin main
git -C <repo> grep -in "<nøkkelbegrep>" origin/main -- '<sti>'
```

- Verifiser hvert punkt i issuen mot koden på `origin/main` (domene, DTO/API, migreringer, tester — det issuen faktisk krever).
- Er alt bekreftet: **omskriv kortet** så det kan forstås i ettertid (hva det gjaldt, hva som ble verifisert, ev. restpunkter som egen sak), lukk det med en kort kommentar, og sett status **Done** i prosjektet.
- Er det delvis ferdig: snevr inn tittel/body til det som gjenstår, og dokumenter det verifiserte.
- Finner du bevis på at det **ikke** er ferdig (f.eks. en TODO i koden): skriv funnet inn i issuen så neste leser slipper å lete.

### 4. Manglende lenker

Se etter bodies som omtaler andre saker, tråder, commits eller planer uten å lenke dem:

- «se den andre saken», «jf. tråden», «planen om å …» uten URL.
- Issues med helt tom body (typisk importerte kort) — skriv minst én setning og lenk beslektede saker.
- Sjekkbokser som er gjort i koden uten at issuen er oppdatert — huk av og lenk commit/PR.

### 5. Rapport

Avslutt med en oppsummering gruppert på de fire kategoriene: hva som ble endret direkte, og hva som trenger menneskelig beslutning (med anbefaling per punkt).
