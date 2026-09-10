---
name: backend-dependency-update
description: Gjennomfør et fullstendig flåtesveip av avhengigheter i tiltakspenger — JVM, frontender, bilder, workflows og infrastruktur. Finn tillatte oppdateringer utover Dependabot, vurder livssyklus, migreringer og versjonslåser, kontroller sårbarheter, og verifiser og rapporter endringene.
license: MIT
metadata:
  domain: backend frontend
  tags: dependabot dependencies gradle kotlin jvm pnpm changelog migration security cooldown trivy sbom nais
---

# Avhengighetsoppdatering i tiltakspenger

Sveip hele flåten, også avhengigheter uten åpne Dependabot-PR-er. Oppdater gruppevis, fra lav til høy risiko. Dokumenter versjonsvalg, sikkerhetsfunn og verifisering.

## Rammer

- **Ingen `git add`, `commit`, `push`, `merge`, `rebase` eller `checkout` i brukerens arbeidskopi.** Lesende git (`status`, `diff`, `log`, `fetch`) er greit. Mennesket committer; klargjør diffen og commit-meldingen.
- **Ett repo per commit.** Bump av felleslib i sju apper er sju commits.
- **Kjør `./gradlew` inne i sub-repoet.** Hvert repo har egen wrapper og egen `.git`.
- **Bygg alltid i en egen worktree** (`git worktree add -f .worktrees/<navn> origin/main` inne i sub-repoet) når arbeidskopien kan være i bruk av andre: en annen gren, uforklarte endringer eller en Gradle-daemon du ikke startet (`ps -axo pid,etime,command | grep GradleDaemon`). Parallelle bygg i samme arbeidskopi gir falske feil (MissingFileSnapshot, Kover-brudd). Konsist-tester feiler i en worktree (`.git` er en fil, fixturstien filtreres) – verifiser dem i en rsync-kopi under `~/.cache` med `git init`.
- **Kjør Gradle-bygg som én kø, aldri parallelt**, og les sluttlinja i loggen før du melder resultat.
- Endre bare det som trengs for oppdateringen, tilhørende migrering og opprydding i utdaterte låser.

## 1. Kartlegg omfang og versjonseierskap

Hele flåten skal med:

| Område | Repoer |
|---|---|
| Fellesbiblioteker og plattform | `tiltakspenger-libs` |
| Sju JVM-apper | `tiltakspenger-arena`, `tiltakspenger-datadeling`, `tiltakspenger-journalposthendelser`, `tiltakspenger-meldekort-api`, `tiltakspenger-saksbehandling-api`, `tiltakspenger-soknad-api`, `tiltakspenger-tiltak` |
| Frontender | `tiltakspenger-soknad`, `tiltakspenger-saksbehandling`, `tiltakspenger-meldekort`, `tiltakspenger-meldekort-microfrontend` |
| Øvrig | `tiltakspenger-pdfgenrs`, `tiltakspenger-workflows`, `tiltakspenger-iac` og metarepoet |

Finn versjonskataloger, publisert plattform-BOM, lokale overrides og constraints, plugins, Gradle-wrapper, GitHub Actions, pnpm-manifester og lockfiler, Dockerfile-basebilder og øvrige avhengighetsdeklarasjoner.

Bruk `rg` til å finne hvor versjonene faktisk styres. Skill mellom deklarert versjon, resolved versjon og versjonen som er i produksjon.

**Versjonseierskap:**

- JVM-tredjepartsversjoner bumpes kun i `tiltakspenger-libs` og metarepoet/workflows, etter hvor de eies.
- De sju JVM-appene bumper bare `felleslibVersion`; `tiltakspenger-tiltak` bumper også `byggoppsettVersjon` i `gradle.properties`.
- Ikke innfør app-lokale tredjepartsbumps for å omgå sentral styring. Nødvendige sikkerhetsconstraints og opprydding i eksisterende unntak håndteres etter steg 7 og 9.
- Frontendpakker, basebilder og øvrige avhengigheter oppdateres i deklarasjonen som eier dem.

## 2. Bruk versjonspolicyen på alle kandidater

Finn først høyeste **stabile og tillatte** versjon per koordinat; kompatibilitet og migrering vurderes etterpå (steg 8), ikke ved å hoppe over major-versjoner i sveipet.

- **Cooldown er 168 timer fra publiseringsklokkeslettet i UTC.** Dette gjelder også manuelle bumps. Tidligste oppdatering er `publisert + 168 timer`.
- **Nav-unntak:** `navikt/*`, `ghcr.io/navikt/*`, `@navikt/*`, `@nais/*` og `nais/*-actions` kan tas med straks.
- **Kritisk sikkerhetsunntak:** En fiks for CRITICAL/HIGH kan tas innenfor cooldown ved kjent utnyttelse eller eksponert kode i produksjon. Dokumenter beslutningen med CVE-id og konkret begrunnelse i commit-meldingen.
- **Ktor skal bli på 3.4-linja.** Låsen følger en produksjonshendelse. Behold ignore-regelen `>=3.5.0, <3.6.0` i `dependabot.yml`, og foreslå aldri å oppheve den. At regelen ikke matcher 3.6+, gjør ikke disse versjonene tillatt.
- Dependabots cooldown gjelder ikke security updates. Sjekk teamets regel manuelt også for disse.

Frontendene skal ha dette i `pnpm-workspace.yaml`:

```yaml
minimumReleaseAge: 10080
minimumReleaseAgeExclude: ["@navikt/*", "@nais/*"]
```

Ved regenerering av lockfila velger pnpm nyeste versjon som tilfredsstiller manifestet og aldersgrensen, med Nav-unntakene over. Kontroller faktisk resultat; faste versjoner og overrides kan holde igjen oppdateringer.

Registerkall mot `@navikt` krever token: `with-npm-token sh -c 'pnpm install && pnpm outdated'`. Hvert kall gir én passorddialog, så samle alt i én økt; aldri «Always Allow».

## 3. Finn alle oppdateringer

Åpne PR-er er innspill, ikke fasit eller avgrensning.

Kjør inne i hvert repo, eller med `--repo navikt/<repo>`:

```bash
gh pr list --author "app/dependabot" --state open \
  --json number,title,headRefName,createdAt,labels

gh pr view <nr> --json title,body,files,additions,deletions,headRefName
```

Sammenlign PR-lista med manifestene: PR-er som allerede er tatt manuelt, men står åpne, betyr at Dependabot-jobben feiler i repoet (pnpm-repoene rammes av registeroppslaget mot `npm.pkg.github.com`).

Kjør et selvstendig sveip:

- `scripts/nyeste-versjoner.py` (fra libs-rota) slår opp nyeste stabile per nøkkel i `gradle/libs.versions.toml`; `scripts/app-utdatert.py <build.gradle.kts>` gjør det samme for direkte deklarerte koordinater i app-repoene. Begge går mot Maven Central og Plugin Portal.
- Kjør `./gradlew dependencyUpdates` i libs og metarepoet; begge har ben-manes versions-plugin.
- Kjør `pnpm outdated` i alle pnpm-repoene.
- Kontroller wrapper, Actions, basebilder og øvrige deklarasjoner som disse verktøyene ikke dekker.

Undersøk **mellomversjoner**. Hvis nyeste versjon er for fersk eller blokkert, finn høyeste eldre versjon som oppfyller policyen. Ikke konkluder med «ingen oppdatering» bare fordi siste release ikke kan tas.

## 4. Verifiser publiseringstidspunkt

Lagre kilde og publiseringsklokkeslett i UTC for hver valgt eller utsatt kandidat.

| Økosystem | Kilde |
|---|---|
| Maven Central | `https://repo1.maven.org/maven2/<g>/<a>/<v>/`, med punktum i gruppe erstattet av `/`; bruk datoen på POM-linja |
| Plugin Portal og Confluent | `Last-Modified` for artefakten/POM-en |
| npm | `npm view <pakke> time --json` |
| GitHub Actions | `gh api repos/<o>/<r>/releases/tags/<tag>` → `published_at` |
| Bilder og øvrige artefakter | Registerets publiseringsmetadata eller dokumentert release-kilde for den konkrete versjonen/digesten |

Ikke bruk PR-opprettelse, lokal nedlasting eller commit-dato som publiseringstidspunkt. For Actions med flytende tag: identifiser den konkrete releasen taggen peker på.

**Utilgjengelig eller utilstrekkelig kilde betyr ukjent, ikke godkjent cooldown.** Rapporter mangelen. For ordinære tredjepartskandidater må alderen være dokumentert før oppdatering.

## 5. Sjekk relocation og etterfølger

Les `<distributionManagement><relocation>` i nyeste POM for hver Maven-koordinat. Følg hele kjeden og verifiser etterfølgerens koordinat, versjon, publiseringstid og kompatibilitet.

Eksempel fra flåten: `com.github.ben-manes.versions` → `io.github.ben-manes.versions`. Kontroller både plugin-id og relevante marker-/implementasjonsartefakter.

Manglende relocation utelukker ikke flytting. Sjekk README, release notes og migreringsguide før en gammel koordinat erklæres oppdatert.

## 6. Vurder livssyklus

Sjekk README, vedlikeholdspolicy, EOL/deprecation og anbefalt etterfølger.

```bash
gh api repos/<o>/<r> --jq .archived
```

Stillstand alene beviser ikke avvikling. Dokumenter eksplisitte signaler og kilder. Skill mellom vanlig versjonsbump, nødvendig migrering og uavklart vedlikeholdsstatus.

## 7. Revurder alle låser og unntak

Gå gjennom versjonslåser, constraints, `ignore` i `dependabot.yml`, pnpm `overrides` og `minimumReleaseAgeExclude` hver runde.

For hver lås: dokumenter **hva den låser, hvorfor og hva som må være sant for å fjerne den**. Dette skal stå i kommentaren på låselinja, eller ved blokken for flerlinjekonfigurasjon. Bruk gyldig kommentarplassering for filformatet.

Fjern låsen når årsaken er borte, og verifiser resolved versjon og tester. Behold varige policyunntak.

| Lås/unntak | Årsak og handling |
|---|---|
| `org.jetbrains.kotlin:kotlin-compiler-embeddable` strictly `2.0.21`, med Dependabot-ignore i alle app-repoer | Konsist `0.17.3` krasjer med nyere kompilator. Flytt låsen til libs’ konsist-regler som `api`-constraint. Fjern overflødige app-låser etter publisering og verifisert arv. Selve låsen og tilhørende ignore fjernes når Konsist støtter Kotlin 2.4. |
| `org.apache.kafka:kafka-clients` strictly i libs-plattformen, journalposthendelser og saksbehandling-api | Confluents `-ccs`-fork vinner ellers konfliktoppløsningen. Behold låsen. Kommentaren skal beskrive at fjerning krever at riktig klient velges uten den; dette er ikke oppfylt i dag. |
| httpclient5/httpcore5-constraints | Behold markøren `httpklient-unntak: <begrunnelse>` for Konsist-regelen `IngenAndreHttpKlienter`. Fjern når `kafka-schema-registry-client` selv drar fikset versjon. |
| Buildscript-ekskludering av `org.apache.avro:avro-ipc-jetty` i journalposthendelser og saksbehandling-api | Fjerner Jetty 9.4 fra buildscript. Fjern unntaket når upstream ikke lenger drar den utsatte komponenten. Ekskluder aldri hele `avro-tools`: `.avdl` trenger `avro-idl`. |
| pnpm-overrides for `sharp`, `js-cookie`, `uuid`, `qs`, `body-parser`, `shell-quote` i soknad/saksbehandling/meldekort | Bruk `pnpm why <pakke>`. Fjern hver override når foreldrepakken selv krever fikset versjon og lockfila bekrefter det. |
| `minimumReleaseAgeExclude` i saksbehandling | Nav-unntaket skal stå likt i alle pnpm-repoene: `["@navikt/*", "@nais/*"]`. Behold så lenge Nav-unntaket er teamets policy. |
| Ktor-ignore | Lås til 3.4-linja etter produksjonshendelsen med 3.5-klienten. Fjernes først når ktor-klientbruken er migrert til httpklient; ikke foreslå det før da. |
| `org.jetbrains.kotlin:kotlin-gradle-plugin`-constraint på build-logics buildscript i libs | `kotlin-dsl` følger Gradle-distribusjonen og drar en eldre KGP med åpen CVE. Fjern når `buildEnvironment` viser at Gradle selv leverer en versjon uten funn. |

Buildscript-unntaket skal være avgrenset:

```kotlin
buildscript {
    configurations["classpath"].exclude(
        group = "org.apache.avro",
        module = "avro-ipc-jetty",
    )
}
```

## 8. Grupper og vurder migrering

Grupper etter bibliotekfamilie, kompatibilitet og risiko.

| Gruppe | Samordning |
|---|---|
| Kotlin / KGP / kotlinx | Sjekk kompatibilitetskrav; de har ikke nødvendigvis samme versjon |
| Ktor | Samordne via BOM; behold 3.4-linja |
| Jackson | Følg kompatibel BOM/versjonslinje |
| Logging | Sjekk API-kompatibilitet mellom logback, slf4j og encoder |
| Testbiblioteker | JUnit, Kotest, MockK, Testcontainers; testscope |
| Gradle-plugins og wrapper | Byggmiljø, JDK- og Gradle-kompatibilitet |
| GitHub Actions | CI-kjøretid, inputs og rettigheter |
| Frontendpakker og bilder | Runtime, peer dependencies og baseimage-kompatibilitet |
| Rene patch-bumps | Kan samles når endringene er uavhengige |

Risikotrapp: **patch → minor → major**. Batch enkle patch-bumps. Les deprecations og endrede standardverdier ved minor. Behandle major separat og les migreringsguiden. Prioriter sikkerhetsfikser, men bruk cooldown-reglene.

### Les changelog og migreringsguide

For hver avhengighet: les endringene gjennom hele intervallet fra dagens versjon til kandidaten, også mellomliggende releaser.

```bash
gh release view <tag> --repo <owner>/<repo> --json body --jq .body
gh api --paginate repos/<owner>/<repo>/releases \
  --jq '.[] | "\(.tag_name): \(.name)"'
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<tag>/CHANGELOG.md
```

Stien til changelog og migreringsguide varierer; finn den i repoet eller på prosjektets nettside før du henter.

Se etter:

- Koordinatbytte, namespace-endringer og fjernede/omdøpte API-er.
- Ny obligatorisk konfigurasjon og endret standardoppførsel.
- Krav til JVM, Kotlin, Gradle, Node og øvrige runtime-/byggeversjoner.
- Kompatibilitet med konsumenter og nødvendige kodeendringer.
- CVE/GHSA og sikkerhetsinformasjon i release notes og PR-beskrivelse.

Velg målversjon fra sveipet og policyen, ikke automatisk fra PR-tittelen. Hold tilbake migreringer som ikke kan verifiseres forsvarlig.

## 9. Spor transitive avhengigheter og sikkerhetsfunn

Bruk **alle tre sårbarhetskildene**, før endringer og ved sluttkontroll.

### Nais

```bash
nais login --nais
nais vulnerability list all -t tpts -o json
```

Tell bare OSV-poster med tilgjengelig fiks i den handlingsrettede opptellingen. Ufiksede Debian-CVE-er i distroless telles ikke der. Hold slike funn separat fra fikser som kan gjennomføres nå.

### GitHubs dependency-graph som SBOM + Trivy

```bash
gh api /repos/navikt/<repo>/dependency-graph/sbom > <repo>.sbom.json
trivy sbom <repo>.sbom.json
```

Kjør `scripts/sbom-skann.sh [repo ...]` fra en scratch-mappe (uten argumenter: hele flåten); den skriver `<repo>-sbom.json`, `<repo>-trivy.json` og én linje per funn. API-et svarer tomt på raske påfølgende kall, derfor pauser skriptet mellom repoene; et repo som feiler, kjøres på nytt.

Dette bruker samme graf som Dependabot-alerts, gir fiksversjon per funn og krever ikke alert-scope på tokenet (alert-API-et svarer 403 for lesetokenet). Grafen sendes inn ved push til main, så den viser siste deployede revisjon, ikke arbeidskopien.

Triager på scope: For JVM-appene er det `runtimeClasspath` som havner i imaget. Buildscript og test er development; rapporter dem separat.

### Lokalt sluttbilde og frontend

Fra JVM-appens dedikerte worktree:

```bash
./gradlew installDist -x test -x check -x gitHooks
trivy rootfs build/install/<app>/lib
```

For frontender og basebilder:

```bash
trivy fs <repo>
trivy image <basebilde:tag-eller-digest>
```

Frontend-skanningen skal omfatte lockfila. JVM-libskanningen dekker distribuerte biblioteker; basebildet må skannes separat.

### Finn riktig eier av fiksen

```bash
./gradlew dependencyInsight \
  --dependency <navn> \
  --configuration runtimeClasspath

./gradlew buildEnvironment
```

App-repoene er ett Gradle-prosjekt; i libs brukes modulstien (`./gradlew :<modul>:dependencyInsight …`). `buildEnvironment` viser buildscript-classpathen; i libs også `./gradlew -p build-logic buildEnvironment`, siden build-logic er et eget bygg med egen classpath som verken plattform-BOM-en eller løft i `dependencies` når.

Legg transitive fikser i BOM/constraints i modulen som eier eksponeringen. Ikke bruk et rammeverksbump som omvei for en transitiv fiks.

- I libs: bruk plattform-BOM eller eiermodul med `api`-scope når constrainten skal nå konsumentene. Verifiser publisert metadata og resolved versjon i appen.
- I app-repoer: bruk ved behov en avgrenset sikkerhetsconstraint, med begrunnelse og fjerningsvilkår:

```kotlin
constraints {
    implementation("<gruppe>:<artefakt>") {
        version {
            strictly("<fikset-versjon>")
        }
        because("<CVE/årsak>; fjernes når <vilkår>")
    }
}
```

For buildscript-classpathen brukes literaler (katalog-accessorene finnes ikke der ennå):

```kotlin
buildscript {
    dependencies {
        constraints {
            // <CVE>; fjernes når <vilkår>. Hold i sync med katalogen.
            add("classpath", "<gruppe>:<artefakt>:<fikset-versjon>")
        }
    }
}
```

Dependabot bumper ikke transitive Gradle-avhengigheter og lager ikke security-PR-er for Gradle. `security_update_dependency_not_found` (Gradle) og `security_update_not_possible` (npm) er forventede feilsignaturer ved transitive funn.

pnpm-repoene får ikke npm security-PR-er på grunn av en upstream-begrensning. SBOM/Trivy-sveipet er den kompenserende kontrollen. Fravær av PR-er betyr ikke fravær av sårbarheter.

## 10. Oppdater og verifiser i flåterekkefølge

1. Gjør tredjepartsbumps og nødvendige constraints i **libs**, samt endringer som eies av metarepoet/workflows.
2. Kompiler og test berørte moduler. Klargjør diff og commit-melding for mennesket.
3. Etter menneskets push: **vent på faktisk publisering**. Det tar normalt rundt 13 minutter. Finn versjonen i «Build and deploy»-loggen: `0.0.<yyyyMMddHHmmss>`. Ikke gjett versjonen fra klokkeslettet.
4. Bump `felleslibVersion` i **alle sju JVM-appene**. Bump også `byggoppsettVersjon` i tiltak når nytt byggoppsett er publisert. Bruk fellesvariabelen, ikke separate artefaktversjoner.
5. Verifiser at konsumentene får riktig BOM, constraints og resolved versjoner.
6. Oppdater og verifiser frontendene og øvrige berørte repoer etter deres versjonseierskap.
7. Kjør sluttkontroll med SBOM/Trivy og Nais. En lokal fiks er ikke lukket i produksjon før riktig image er deployet og kontrollert.

Kjør fra det enkelte JVM-repoets worktree:

```bash
./gradlew compileKotlin compileTestKotlin --console=plain -x gitHooks
./gradlew clean check --no-build-cache --console=plain -x gitHooks
```

Tilpass task-stier til moduler. `clean check --no-build-cache` er nødvendig fordi stale Kover-data kan gi falske brudd. Bruk `-x gitHooks` i worktrees.

For frontender: regenerer lockfila med pnpm og alderspolicyen aktiv, og kjør repoets bygg, tester, lint og typesjekk der disse finnes. Verifiser relevante konfigurasjoner og bygg for workflows, iac og pdfgenrs.

Ved feil: koble stacktrace til versjonsendringen og changelog, rett nødvendige kallsteder og test på nytt. Del opp store hopp ved uklar årsak. Dokumenter og hold tilbake uløste brudd.

## 11. Vurder og rapporter

Gi én vurdering per gruppe:

| Felt | Innhold |
|---|---|
| Versjonshopp | patch / minor / major / koordinatbytte |
| Breaking changes | nei / konkret endring |
| Sikkerhet | CVE/GHSA, scope og fiksversjon |
| Bygg og test | grønt / rødt / ikke kjørt, med årsak |
| Kodeendringer | ingen / nødvendige migreringer |
| Anbefaling | klar til commit/merge / hold tilbake / krever oppfølging |

Rapporter per koordinat eller annen avhengighetsidentifikator:

| Repo/eier | Koordinat | Fra → til | Publisert UTC | Kilde | Cooldown |
|---|---|---|---|---|---|
| … | … | … | … | URL/metadata | OK / Nav-unntak / sikkerhetsunntak / ukjent |

Knytt hver rad til CVE-er lukket, tester og eventuell gruppevurdering. Skill mellom verifisert lokalt, publisert, konsumert og lukket i produksjon.

Sluttoppsummeringen skal inneholde:

- Anbefaling per gruppe og berørte PR-numre.
- Utsatte kandidater med årsak og tidligste tillatte UTC-dato **og klokkeslett**.
- Låser og unntak som er fjernet, flyttet eller beholdt, med fjerningsvilkår.
- Uavklarte funn, utilgjengelige kilder og kontroller som ikke kunne kjøres.
- Forslag til commit-melding per repo. Sikkerhetsunntak innenfor cooldown må ha CVE-id og begrunnelse.

List klare PR-er og foreslå neste kommandoer ved behov. Mennesket kjører commit, push og merge.
