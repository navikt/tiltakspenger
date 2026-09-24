---
name: backend-dependency-update
description: Gjennomfør et fullstendig flåtesveip av avhengigheter i tiltakspenger — JVM, frontender, bilder, workflows og infrastruktur. Finn tillatte oppdateringer utover Dependabot, be Dependabot gjenskape utdaterte PR-er, vurder livssyklus, migreringer og versjonslåser, kontroller sårbarheter, og verifiser og rapporter endringene.
license: MIT
metadata:
  domain: backend frontend
  tags: dependabot dependencies gradle kotlin jvm pnpm changelog migration security cooldown trivy sbom nais
---

# Avhengighetsoppdatering i tiltakspenger

Sveip hele flåten, også avhengigheter uten åpne Dependabot-PR-er. Oppdater gruppevis, fra lav til høy risiko. Dokumenter versjonsvalg, sikkerhetsfunn og verifisering.

## Rammer

- **Ingen `git add`, `commit`, `push`, `merge`, `rebase` eller `checkout` i brukerens arbeidskopi.** Lesende git (`status`, `diff`, `log`), `fetch`, `pull` og `git worktree` er greit. Brukeren committer; klargjør diffen og commit-meldingen.
- **Ett repo per commit.** Bump av felleslib i seks apper er seks commits.
- **Kjør `./gradlew` inne i sub-repoet.** Hvert repo har egen wrapper og egen `.git`.
- **Bygg alltid i en egen worktree** (`git worktree add -f .worktrees/<navn> origin/main` inne i sub-repoet) når arbeidskopien kan være i bruk av andre: en annen gren, uforklarte endringer eller en Gradle-daemon du ikke startet (`ps -axo pid,etime,command | grep GradleDaemon`). Parallelle bygg i samme arbeidskopi gir falske feil (MissingFileSnapshot, Kover-brudd). Konsist-tester feiler i en worktree (`.git` er en fil, fixturstien filtreres) – verifiser dem i en rsync-kopi under `~/.cache` med `git init`.
- **Kjør Gradle-bygg som én kø, aldri parallelt.** Fang exit-koden fra byggkommandoen og les sluttlinja i loggen før du melder resultat.
- Endre bare det som trengs for oppdateringen, tilhørende migrering og opprydding i utdaterte låser.

## 1. Kartlegg omfang og versjonseierskap

Hele flåten skal med:

| Område | Repoer |
|---|---|
| Fellesbiblioteker og plattform | `tiltakspenger-libs` |
| Seks JVM-apper | `tiltakspenger-arena`, `tiltakspenger-datadeling`, `tiltakspenger-journalposthendelser`, `tiltakspenger-meldekort-api`, `tiltakspenger-saksbehandling-api`, `tiltakspenger-soknad-api` |
| Frontender | `tiltakspenger-soknad`, `tiltakspenger-saksbehandling`, `tiltakspenger-meldekort`, `tiltakspenger-meldekort-microfrontend` |
| Øvrig | `tiltakspenger-pdfgenrs`, `tiltakspenger-workflows`, `tiltakspenger-iac` og metarepoet |

Finn versjonskataloger, publisert plattform-BOM, lokale overrides og constraints, plugins, Gradle-wrapper, GitHub Actions, pnpm-manifester og lockfiler, Dockerfile-basebilder og øvrige avhengighetsdeklarasjoner.

Bruk `rg` til å finne hvor versjonene faktisk styres. Skill mellom deklarert versjon, resolved versjon og versjonen som er i produksjon.

**Versjonseierskap:**

- JVM-tredjepartsversjoner bumpes kun i `tiltakspenger-libs` og metarepoet/workflows, etter hvor de eies.
- De seks JVM-appene bumper bare `felleslibVersion`.
- Ikke innfør app-lokale tredjepartsbumps for å omgå sentral styring. Nødvendige sikkerhetsconstraints og opprydding i eksisterende unntak håndteres etter steg 7 og 9.
- Frontendpakker, basebilder og øvrige avhengigheter oppdateres i deklarasjonen som eier dem.

## 2. Bruk versjonspolicyen på alle kandidater

Finn først høyeste **stabile og tillatte** versjon per koordinat; kompatibilitet og migrering vurderes etterpå (steg 8), ikke ved å hoppe over major-versjoner i sveipet.

- **Cooldown er 168 timer fra publiseringsklokkeslettet i UTC.** Dette gjelder også manuelle bumps. Tidligste oppdatering er `publisert + 168 timer`.
- **«Nyeste versjon» betyr høyeste stabile versjon som er ute av cooldown.** Ferskere versjoner holdes utenfor overalt: når du velger mål, når du avgjør om en PR er utdatert, og når du melder at noe er oppdatert. Unntakene under er de eneste.
- **Nav-unntak:** Maven-gruppene `com.github.navikt.*` og `no.nav.*`, Actions under `navikt/*` og `nais/*`, npm-pakkene `@navikt/*` og `@nais/*` og bilder under `ghcr.io/navikt/*` har ingen cooldown.
- **Kritisk sikkerhetsunntak:** En fiks for CRITICAL/HIGH kan tas innenfor cooldown ved kjent utnyttelse eller eksponert kode i produksjon. Dokumenter beslutningen med CVE-id og konkret begrunnelse i commit-meldingen.
- Dependabots cooldown gjelder ikke security updates. Sjekk teamets regel manuelt også for disse.

Frontendene skal ha dette i `pnpm-workspace.yaml`:

```yaml
minimumReleaseAge: 10080
minimumReleaseAgeExclude: ["@navikt/*", "@nais/*"]
```

Velg målversjoner etter policyen, oppdater manifestene, og oppdater lockfila med alderspolicyen aktiv. Kontroller resolved versjon; faste versjoner, overrides og eksisterende lockfil kan holde igjen oppdateringer.

Registerkall mot `@navikt` krever token: `with-npm-token sh -c 'pnpm install && pnpm outdated'`. Hvert kall gir én passorddialog, så samle alt i én økt; aldri «Always Allow».

## 3. Finn alle oppdateringer

Åpne PR-er er innspill, ikke fasit eller avgrensning.

Kjør inne i hvert repo, eller med `--repo navikt/<repo>`:

```bash
gh pr list --author "app/dependabot" --state open --limit 100 \
  --json number,title,headRefName,baseRefName,createdAt,labels

gh pr view <nr> --json title,body,files,headRefName,headRefOid,commits
gh pr diff <nr>
```

Sammenlign PR-lista med manifestene: PR-er som allerede er tatt manuelt, men står åpne, tyder på at Dependabot-jobben feiler i repoet (i pnpm-repoene er registeroppslaget mot `npm.pkg.github.com` en kjent årsak).

### Be Dependabot gjenskape utdaterte PR-er

Les målversjonen per koordinat fra PR-diffen, ikke fra tittelen, og versjonen på main fra deklarasjonen som eier den (manifest, katalog, lockfil). PR-en er utdatert når

- **a)** main har samme eller nyere versjon enn PR-en foreslår, eller
- **b)** nyeste versjon (steg 2, med publiseringstid fra steg 4) er høyere enn PR-ens mål.

I en gruppert PR holder det at én koordinat treffer. Kan versjonene ikke sammenlignes (intervaller, SHA-låste Actions), rapporter PR-en som uavklart.

```bash
gh pr comment <nr> --repo navikt/<repo> --body "@dependabot recreate"
```

- Kommentaren er en skrivehandling på GitHub. List PR-ene med begrunnelse (a eller b, versjon på main, nyeste versjon og publiseringstid), og post når brukeren har bestilt det. Bruk maskinens skrivewrapper for `gh` der agenten bare har lesetoken.
- `recreate` overskriver grenen. Avklar PR-er med commits fra andre enn Dependabot med brukeren først.
- Noter `headRefOid` og målversjoner før kommentaren. Les Dependabots svar, `state`, `headRefOid` og diffen etterpå. PR-en kan bli lukket, få nytt mål eller stå uendret; i en gruppe kan noen koordinater falle ut mens resten blir stående. Kan ingen behandling bekreftes, rapporter utfallet som uavklart. Ikke post samme kommando på nytt.
- Dependabot følger `cooldown` og `ignore` i `dependabot.yml`, ikke denne policyen. Kontroller det nye målet mot steg 2. Security-PR-er følger ikke cooldown og kan få et mål yngre enn 168 timer; vurder det etter sikkerhetsunntaket.
- Rapporter PR-er med mål en versjonslås i steg 7 forbyr separat, også når verken a eller b treffer. `recreate` gjør ikke målet tillatt.
- `@dependabot rebase` oppdaterer PR-en mot main uten å velge versjon på nytt, og løser verken a eller b.

Kjør et selvstendig sveip:

- `nyeste-versjoner.py` (kjøres fra libs-rota; skriptene ligger i `scripts/` ved siden av denne fila) slår opp nyeste versjon per nøkkel i `gradle/libs.versions.toml`; `app-utdatert.py <build.gradle.kts>` gjør det samme for direkte deklarerte koordinater i app-repoene. Begge går mot Maven Central, Plugin Portal, Confluent og Navs speil, følger cooldown og Nav-unntaket, og lister ferskere versjoner med tidligste tillatte tidspunkt i kolonnen «holdt utenfor».
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
| GitHub Actions | `gh release view <tag> --repo <o>/<r> --json publishedAt` |
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
gh repo view <o>/<r> --json isArchived
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
| `io.netty:netty-bom` som plattform i JVM-appene og `netty42` i libs-katalogen | `ktor-server-netty` drar inn en Netty 4.2 med åpne CVE-er, og r2dbc/reactor-netty drar 4.1, så begge linjene havner ellers på classpath. BOM-en holder alle `io.netty:*` på én fikset versjon; bump den som en vanlig koordinat. Fjern når `dependencyInsight` viser én Netty-linje uten funn uten BOM-en. |
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
| Ktor | Samordne via BOM, og bump `netty-bom` i samme runde |
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
gh release list --repo <owner>/<repo> --limit 100 --json tagName,name,publishedAt
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
curl -fsSL https://api.github.com/repos/navikt/<repo>/dependency-graph/sbom | jq .sbom > <repo>.sbom.json
trivy sbom <repo>.sbom.json
```

Kjør `sbom-skann.sh [repo ...]` fra samme `scripts/`, med en scratch-mappe som arbeidskatalog (uten argumenter: hele flåten); den skriver `<repo>-sbom.json`, `<repo>-trivy.json` og én linje per funn. API-et svarer tomt på raske påfølgende kall, derfor pauser skriptet mellom repoene; kjør et repo som feiler, på nytt.

Dette bruker samme graf som Dependabot-alerts og gir fiksversjon per funn. Repoene er offentlige, så endepunktet leses uten token (60 kall i timen per IP); alert-API-et krever derimot et token med alert-scope. Grafen sendes inn ved push til main, så den viser main, verken arbeidskopien eller det som er deployet.

SBOM-en bærer ikke scope. Avgjør scope per funn: for JVM-appene havner `runtimeClasspath` i imaget, så et funn er runtime når `dependencyInsight --configuration runtimeClasspath` finner koordinaten, eller når `trivy rootfs` på sluttbildet under viser det samme funnet. Resten er buildscript eller test; rapporter dem separat. Metarepoet har ingen innsendt graf og er ikke med.

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
2. Kompiler og test berørte moduler. Klargjør diff og commit-melding for brukeren.
3. Etter brukerens push: **vent på faktisk publisering**. Det tar normalt rundt 13 minutter. Finn versjonen i «Build and deploy»-loggen: `0.0.<yyyyMMddHHmmss>`. Ikke gjett versjonen fra klokkeslettet.
4. Bump `felleslibVersion` i **alle seks JVM-appene**. Bruk fellesvariabelen, ikke separate artefaktversjoner.
5. Verifiser at konsumentene får riktig BOM, constraints og resolved versjoner.
6. Oppdater og verifiser frontendene og øvrige berørte repoer etter deres versjonseierskap.
7. Når endringene er på main i hvert berørt repo: kontroller de åpne Dependabot-PR-ene på nytt (steg 3). Er endringene fortsatt lokale, rapporter kontrollen som gjenstående.
8. Kjør sluttkontroll med SBOM/Trivy og Nais. En lokal fiks er ikke lukket i produksjon før riktig image er deployet og kontrollert.

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
- PR-er som er bedt gjenskapt, med årsak (a eller b) og utfall: lukket, nytt mål, uendret eller uavklart. Før PR-er med forbudt mål i en egen bolk.
- Utsatte kandidater med årsak og tidligste tillatte UTC-dato **og klokkeslett**.
- Låser og unntak som er fjernet, flyttet eller beholdt, med fjerningsvilkår.
- Uavklarte funn, utilgjengelige kilder og kontroller som ikke kunne kjøres.
- Forslag til commit-melding per repo. Sikkerhetsunntak innenfor cooldown må ha CVE-id og begrunnelse.

List klare PR-er og foreslå neste kommandoer ved behov. Brukeren kjører commit, push og merge.
