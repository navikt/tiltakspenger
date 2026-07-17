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

```bash
# Alle items i prosjektet
gh project item-list 227 --owner navikt --limit 1000 --format json \
  -q '.items[] | select(.content.type == "Issue") | "\(.content.repository)#\(.content.number)"' | sort > prosjekt.txt

# Alle åpne issues i alle repoene (utvid repo-lista ved behov)
for r in $(gh repo list navikt --limit 100 --json name -q '.[].name' | grep '^tiltakspenger'); do
  gh issue list -R "navikt/$r" --state open --limit 300 --json number -q ".[] | \"navikt/$r#\(.number)\""
done | sort > aapne.txt

comm -23 aapne.txt prosjekt.txt   # åpne issues som mangler i prosjektet
comm -13 aapne.txt prosjekt.txt   # prosjekt-items som er lukket (sjekk at status er Done)
```

Legg manglende issues inn med `gh project item-add 227 --owner navikt --url <issue-url>` og sett riktig status med `gh project item-edit`.

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
