---
name: backend-dependency-update
description: Oppdater backend-avhengigheter i tiltakspenger-repoene ved å finne Dependabot-PR-er, gruppere dem, lese changelog/migreringsguider, verifisere bygg + test, og gjøre en vurdering per gruppe. Bruk for å «ta Dependabot-PR-ene», bumpe dependencies, rydde i avhengighetsoppdateringer eller gå gjennom utdaterte biblioteker i et Kotlin/JVM-repo.
license: MIT
metadata:
  domain: backend
  tags: dependabot dependencies gradle kotlin jvm changelog migration security
---

# Backend Dependency Update

Strukturert arbeidsflyt for å håndtere **Dependabot-PR-er** i tiltakspenger-backendrepoene (Kotlin/JVM, Gradle). Målet er å oppdatere avhengigheter **gruppevis**, lese relevant changelog/migreringsguide, verifisere at det **bygger og tester grønt**, og avslutte med en **vurdering** (merge / hold tilbake / krever oppfølging).

> Denne skillen følger det åpne «Agent Skills»-formatet (`SKILL.md` med YAML-frontmatter) og er **verktøy-uavhengig** — den er ren markdown-instruksjon som kan brukes av en hvilken som helst agent/LLM-CLI (GitHub Copilot, Claude, lokale open source-verktøy osv.). Se [`../README.md`](../README.md) for hvordan du aktiverer den i ulike verktøy.

Gjelder Gradle-baserte repoer som `tiltakspenger-arena`, `tiltakspenger-datadeling`, `tiltakspenger-journalposthendelser`, `tiltakspenger-meldekort-api`, `tiltakspenger-saksbehandling-api`, `tiltakspenger-soknad-api`, `tiltakspenger-tiltak` og `tiltakspenger-libs`.

## Viktige rammer (fra AGENTS.md)

- **Ingen muterende git-kommandoer.** Ikke kjør `git add/commit/push/merge/rebase/checkout -b`. Lesende git (`status`, `diff`, `log`, `fetch`) er greit. Foreslå muterende steg og la mennesket kjøre dem — eller la Dependabot/PR-flyten håndtere merge.
- **`./gradlew` fra inne i sub-repoet** — hvert sub-repo har egen wrapper og egen `.git/`.

## Arbeidsflyt

1. **Finn alle Dependabot-PR-er** (per repo eller på tvers av repoer).
2. **Grupper** PR-ene (samme bibliotekfamilie / økosystem / risikonivå).
3. For hver gruppe, i stigende risiko: **les changelog + migreringsguide**, **vurder (kan velge å utelate her)**, **bump**, **bygg + test**.
4. **Oppsummer** med en klar anbefaling per gruppe.

---

## 1. Finn Dependabot-PR-er

Alle disse repoene er åpne på github, så du kan finne repoene via curl (lenker i AGENTS.md), eller
Kjør inne i sub-repoet (eller iterer over flere):

```bash
# Alle åpne Dependabot-PR-er i gjeldende repo
gh pr list --author "app/dependabot" --state open \
  --json number,title,headRefName,createdAt,labels \
  --jq '.[] | "#\(.number)  \(.title)  (\(.headRefName))"'
```

Fleet-wide (kjør per repo-mappe):

```bash
for r in tiltakspenger-arena tiltakspenger-datadeling tiltakspenger-journalposthendelser \
         tiltakspenger-meldekort-api tiltakspenger-saksbehandling-api \
         tiltakspenger-soknad-api tiltakspenger-tiltak tiltakspenger-libs; do
  echo "=== $r ==="
  ( cd "$r" && gh pr list --author "app/dependabot" --state open \
      --json number,title --jq '.[] | "#\(.number)  \(.title)"' )
done
```

Detaljer for én PR (tittel viser typisk `Bump X from A to B`):

```bash
gh pr view <nr> --json title,body,files,additions,deletions,headRefName
```

## 2. Grupper PR-ene

Slå sammen PR-er som logisk hører sammen, så du bumper + tester én gang per gruppe i stedet for én gang per PR. Vanlige grupper:

| Gruppe | Eksempler | Hvorfor sammen |
|---|---|---|
| **Kotlin / KGP** | `kotlin-*`, `kotlin-gradle-plugin`, kotlinx | Må følge hverandre i versjon |
| **Ktor** | `io.ktor:*` | BOM/versjon henger sammen |
| **Jackson** | `com.fasterxml.jackson*` | Skal være samme versjonslinje |
| **Logging** | `logback`, `slf4j`, `logstash-logback-encoder` | API-kompatibilitet |
| **Testbiblioteker** | `junit*`, `kotest*`, `mockk`, `testcontainers*` | Kun testscope, lav risiko |
| **Gradle-plugins** | `shadow`, `spotless`, `flyway-plugin` | Byggtid, ikke runtime |
| **GitHub Actions** | `actions/*`, `gradle/*` | CI, ikke runtime |
| **Patch-bump (rene)** | x.y.Z-endringer uten breaking | Kan batches og raskt verifiseres |

Tommelfingerregler:
- **Patch (`x.y.Z`)** → lav risiko, batch flere sammen.
- **Minor (`x.Y.0`)** → les changelog for nye deprecations/feature-flagg.
- **Major (`X.0.0`)** → behandle alene, les migreringsguide nøye.
- **Sikkerhetsoppdateringer (CVE/GHSA)** → prioriter, uavhengig av gruppe.

## 3. Per gruppe: les → bump → bygg/test → vurder

### 3a. Les changelog og migreringsguide

For hver dependency i gruppen, hent endringene mellom `from`- og `to`-versjon:

```bash
# GitHub release notes mellom to tags (når biblioteket ligger på GitHub)
gh release view <tag> --repo <owner>/<repo> --json body --jq .body
gh api repos/<owner>/<repo>/releases --jq '.[] | "\(.tag_name): \(.name)"' | head -30

# Hent en CHANGELOG eller migreringsguide direkte (verktøy-uavhengig)
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<tag>/CHANGELOG.md | less
```

- Bruk agentens egen nettleser-/hentefunksjon (eller `curl`) på `CHANGELOG.md`, GitHub Releases eller offisiell migreringsguide når en major-versjon krysses.
- Se spesielt etter: **breaking changes**, **fjernede/omdøpte API-er**, **nye obligatoriske config**, **endret default-oppførsel**, **min. JVM/Kotlin-versjon**.
- Sjekk om Dependabot-PR-en selv er en **sikkerhetsoppdatering** (lenker til GHSA/CVE i body).

### 3b. Bump versjonen lokalt

Finn hvor versjonen settes (varierer per repo):

```bash
grep -rn "<artefakt-eller-versjonsnavn>" build.gradle.kts gradle/libs.versions.toml gradle.properties 2>/dev/null
```

Vanlige steder:
- `build.gradle.kts` — `val xVersion = "..."` eller inline i `dependencies { }`.
- `gradle/libs.versions.toml` — version catalog (`[versions]`).
- `gradle.properties` — globale versjonsproperties.
- Felles intern lib bumpes ofte via én variabel, f.eks. `val felleslibVersion = "0.0.842"`.

Rediger versjonsstrengen til måltversjonen fra PR-tittelen. Ikke endre urelaterte ting.

### 3c. Bygg og test

Alltid fra inne i sub-repoet:

```bash
./gradlew compileKotlin compileTestKotlin --console=plain   # rask feilavdekking
./gradlew test --console=plain                              # full test
```

- Kompiler først (raskere feedback på breaking API-endringer), så test.
- Ved feil: les stacktrace, koble den til changelog-en (deprecated/fjernet API?), og rett kallsteder. Hvis bruddet er reelt og ikke trivielt, **dokumentér og hold PR-en tilbake** framfor å presse gjennom.
- Store hopp (mange versjoner siden sist) kan avdekke urelaterte breaking changes — bump heller ett om gangen i tvilstilfeller.

### 3d. Vurder

Lag en kort vurdering per gruppe:

| Felt | Innhold |
|---|---|
| **Versjonshopp** | patch / minor / major |
| **Breaking changes** | ja/nei + hva |
| **Sikkerhet** | løser CVE/GHSA? |
| **Bygg + test** | grønt / rødt (+ hva som feilet) |
| **Kodeendringer nødvendig** | ingen / hvilke |
| **Anbefaling** | merge / hold / krever oppfølging |

## 4. Oppsummering

Avslutt med en tabell over alle grupper og anbefaling. For PR-er klare til merge: list dem, men la **mennesket** kjøre merge (eller approve så Dependabot auto-merger). Foreslå eksplisitte kommandoer i stedet for å kjøre dem:

```text
Klare til merge:  #123 (junit 5.x→5.y), #124 (mockk patch)
Hold tilbake:     #130 (Ktor 2→3, krever API-migrering — egen oppgave)
```

## Tips

- Oppdater lokal task-tracking (f.eks. `TASKS.md`) hvis repoet bruker det.
- En PR der `./gradlew test` allerede er grønt på Dependabot-branchen i CI er lav risiko; lokal verifisering bekrefter mot din JDK.
- Hvis du bare vil verifisere Dependabot-branchen direkte: `git fetch` (lesende, tillatt) og les diffen — men ikke sjekk ut/merge.
- For internt felleslib (`tiltakspenger-libs`): bump alle `:$felleslibVersion`-referansene via den ene variabelen, ikke per artefakt.
