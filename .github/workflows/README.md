# Delte GitHub Actions-workflows

Workflowene i denne mappa er [reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows) som kalles fra `tiltakspenger*`-repoene.
Arbeidet spores i [navikt/tiltakspenger#31](https://github.com/navikt/tiltakspenger/issues/31).

## Bruk fra et repo

Calleren er en tynn, komplett workflow — trigger, rettigheter og et `uses`-kall:

```yaml
name: Dependabot auto-merge
on:
  pull_request:
    branches:
      - main

# Minste privilegium: toppnivået nullstiller alle token-rettigheter, hver jobb deklarerer eksplisitt det den trenger.
permissions: {}

# Kansellerer utdaterte kjøringer på samme PR (falske feilvarsler ved rebase midt i bygg).
# Concurrency må stå i calleren - en delt workflow lager ingen egen run.
concurrency:
  group: dependabot-auto-merge-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  dependabot:
    permissions:
      contents: write
      pull-requests: write
    uses: navikt/tiltakspenger/.github/workflows/dependabot-auto-merge.yml@main
    secrets:
      SLACK_VARSEL_WEBHOOK_URL: ${{ secrets.SLACK_VARSEL_WEBHOOK_URL }}
```

De faktiske callerne i repoene er den kanoniske malen — kopier derfra, ikke herfra.
Se toppen av hver workflow-fil for hvilke rettigheter, secrets og inputs akkurat den krever.
Input-defaultene i de delte workflowene ER flåtestandarden (`java-version: '25'`, `node-version: '24'`, blokkerende zizmor osv.) — callerne sender kun inputs ved reelt repo-avvik, slik at en standardendring (f.eks. Java-bump) er én metarepo-endring.

## Porteføljen

| Delt workflow | For | Nøkkel-inputs/secrets |
| --- | --- | --- |
| `lint-workflows.yml` | alle repoer (språkagnostisk) | `zizmor-blokkerende`, `zizmor-mal-sjekk`, `dependabot-mal` |
| `dependabot-auto-merge.yml` | Kotlin/JVM-repoene | `java-version` |
| `dependabot-auto-merge-node.yml` | frontend-repoene (saksbehandling, soknad, meldekort, meldekort-microfrontend); npm/pnpm detekteres fra lockfila | `node-version`, `test-kommando`; secret `READER_TOKEN` (@navikt-pakker) |
| `test-og-bygg-gradle.yml` | JVM-app-repoene (erstatter lokal `.test-and-build.yml`; PR-gate med `bygg-image: false`) | `java-version`, `gradle-kommando`, `bygg-image` |
| `dependency-submission-gradle.yml` | JVM-app-repoene (Dependabot-synlighet for transitive avhengigheter; libs sender inn fra publiseringsbygget sitt) | `java-version` |
| `test-og-bygg-node.yml` | frontend-repoenes test-/verifiseringsgate (PR/branch; image-bygg forblir lokale); npm/pnpm detekteres fra lockfila | `node-version`, `kommando`; secrets `READER_TOKEN`, `SLACK_VARSEL_WEBHOOK_URL` |
| `bygg-image.yml` | repo der Dockerfilen er hele bygget (pdfgen, pdfgenrs) | ingen inputs; output `IMAGE` |
| `deploy-nais.yml` | alle repoer som deployer image til nais (erstatter lokal `.deploy-to-nais.yml`; bruker GitHub environment per miljø) | `NAIS_ENV`, `IMAGE`, `cluster-suffiks` (arena: `fss`), `nais-ressurs`, `nais-vars` (`ingen` deployer uten vars-fil) |
| `codeql-gradle.yml` | Kotlin/JVM-repoene (caller eier schedule + concurrency) | `java-version` |
| `codeql-node.yml` | TypeScript/JavaScript-repoene (build-mode none; caller eier schedule + concurrency) | ingen inputs |

Utrullingsstatus per repo spores i [#31](https://github.com/navikt/tiltakspenger/issues/31) — tabellen sier hvem workflowen er for, ikke hvem som bruker den i dag.

`lint-workflows.yml`: metarepoet kaller den selv fra `lint.yml` med lokal sti, slik at PR-er som endrer delte workflows testes med sin egen versjon.
zizmor er blokkerende som default (flåtestandarden); et repo som ennå ikke har nedfelt unntakene sine i `zizmor.yml` setter `zizmor-blokkerende: false` midlertidig i calleren.

**Fork-PR-er** testes av gatene: pushes i forks trigger aldri workflows i base-repoet, så gate-callerne trigger på både `push` og `pull_request`, og guarden i delt workflow slipper kun gjennom fork-PR-events (interne brancher dekkes av push-triggeren — én kjøring per endring, ikke to).
Fork-kjøringer får read-only token og ingen secrets: Slack-varsling skjer uansett kun på main-ref, og node-gaten faller tilbake på `github.token` for lesing av public @navikt-pakker.

`dependabot-auto-merge.yml` og `-node.yml` er tekstlig parallelle - kun byggejobben (og dens inputs/secrets, bl.a. `READER_TOKEN`) skiller dem; endres den ene, oppdater den andre tilsvarende.
Node-varianten dekker både npm og pnpm ved å detektere pakkehåndterer fra lockfila (`pnpm-lock.yaml` → pnpm) — npm→pnpm-migreringen (jf. nais-doc) krever dermed ingen caller-endring, bare bytte av lockfil i repoet.
Testene ligger i byggegatene: gradle-varianten kjører `./gradlew build` (inkl. tester), node-varianten kjører `npm ci`/`pnpm install --frozen-lockfile` + `test-kommando` (lint/tsc/test etter hva repoet har; `$PAKKEHANDTERER` er tilgjengelig i kommandoen).

`test-og-bygg-gradle.yml` eksponerer imaget som workflow-output `IMAGE`; deploy-calleren sender den videre til `deploy-nais.yml` via `needs.<jobb>.outputs.IMAGE` — det er komposisjonsmønsteret for bygg-og-deploy-pipelines.

**Bevisst ikke delt** (repo-spesifikk variasjon overstiger gevinsten i dag): frontendenes lokale image-byggeworkflows (`.build-app.yml` m.fl. — ENV-matrise, env-filer, CDN-opplasting, `image_suffix`), microfrontendens deploy (Astro + CDN), pdfgenrs' `.test.yml` (brevtester) og iac (rene manifest-deployer — kan adoptere `deploy-nais.yml` ved behov).
CDN-opplasting: hele Nav (inkl. nais-doc og dagpenger) bruker `nais/deploy/actions/cdn-upload/v2@master` — vi SHA-pinner den i stedet (`@2d18f050f07b6a007864c6a57070ed915d571beb`-familien; actionen bor i nais/deploy-repoet, versjonen ligger i stien `/v2`).

## Maler for repo-config

Standard `zizmor.yml` og `dependabot.yml`-varianter (gradle/node/kun-actions) ligger i [`../maler/`](../maler/README.md) — kanonisk kilde, kopier derfra ved utrulling (jf. #39: standardene eies i metarepoet).
GitHub kan ikke lenke config-filer på tvers av repo (ingen include-mekanisme; tilleggsstønader har f.eks. usynkroniserte kopier), så lenke-semantikken håndheves i stedet av **drift-vaktene** i `lint-workflows.yml`: repoets `zizmor.yml` må være lik malen, og repoets `dependabot.yml` må være lik riktig mal-variant (auto-detektert fra repo-innhold, eller eksplisitt via `dependabot-mal`), ellers feiler linten.
Begrunnet avvik = `zizmor-mal-sjekk: false` / `dependabot-mal: ingen` i calleren med kommentar (metarepoet gjør begge deler — zizmor-configen er et supersett med unntak for de delte workflowene, og dependabot-fila er bevisst kun github-actions; soknad-api setter `dependabot-mal: ingen` pga. registries-blokka for libs-bumps).

## Vakter mot upinnede actions i metarepoet

Metarepo-main er tillitsgrensen for all CI (`@main`-callere), og CI-lint rekker bare å farge en dårlig push rød *etterpå*.
Derfor to lag:

1. **Pre-push-hook** (`.gitHooks/pre-push`): kjører samme actionlint + zizmor som CI (pinnede verktøy) før push slipper ut. Aktiveres per klone med `git config core.hooksPath .gitHooks`; bevisst omgåelse er `git push --no-verify`.
2. **Blokkerende lint i CI** med `unpinned-uses`-policy `"*": hash-pin` — fanger alt hooken ikke så (verifisert: en upinnet action gir exit 14 med eksplisitt funn).

Vurder repo-ruleset med påkrevd lint-sjekk på metarepo-main som tredje lag — metarepoet har ingen auto-merge, så det kolliderer ikke med automerge-designet.

## Standard paths-ignore

Standardlistene eies her (jf. #39); repoene kopierer og avviker kun med begrunnelse.

- **JVM-app** (`Build and deploy` + `Test/build on feature branch push`): `**.md`, `.gitattributes`, `.gitHooks/**`, `.gitignore`, `.idea/**`, `.nais/alerts.yml`, `clean_lint_and_build.sh`, `CODEOWNERS`, `doc/**`, `docker-compose/**`, `docs/**`, `LICENSE`, `lint_and_build.sh`
- **Frontend**: `**.md`, `.env-template`, `.gitattributes`, `.gitignore`, `.husky/**`, `CODEOWNERS`, `docker-compose/**`, `LICENSE`
- Alerts-deploy bruker positive `paths` (`.nais/alerts.yml` + workflow-fila selv) — endringer der skal ikke bygge appen.
- Åpne beslutninger (bl.a. `.github/**` i bygge-/publiserings-workflows) spores i [#39](https://github.com/navikt/tiltakspenger/issues/39).

## Forholdet til Nais-dokumentasjonen og Golden Path

Nav har to delvis divergerende referanser for workflows: [Nais-dokumentasjonen](https://docs.nais.io/build/how-to/build-and-deploy/) og [`navikt/backend-golden-path`](https://github.com/navikt/backend-golden-path) (jf. Slack-diskusjon 2026-07-17; nais-teamet bekrefter at Golden Path er «best practices», ikke fasit).
Kjente forskjeller: Nais-doc bruker `nais/what-changed` (skip av unødige bygg) og GitHubs innebygde automerge for Dependabot, Golden Path bruker `navikt/automerge-dependabot`, har deploy i egen jobb, gjør dependency submission og secret-scanning etter image-bygg, og legger på herding som `persist-credentials: false`.

Der vi avviker, er det bevisst:

- **Dependabot-merging:** vi bruker verken GitHubs automerge (krever påkrevde sjekker på main, som vi ikke har — og har kjente begrensninger rundt scheduling/options, jf. nais-teamet) eller `navikt/automerge-dependabot`, men direkte `gh pr merge` etter grønt bygg i samme workflow.
  Det gir oss byggegate + den bevisste egenskapen at merge med `GITHUB_TOKEN` aldri trigger publisering/deploy.
- **Branch protection:** sikkerhet.nav.no anbefaler påkrevde sjekker og obligatorisk PR-review på main; repoene våre har ingen av delene, og hele auto-merge-designet forutsetter det.
  Det er et bevisst avvik (liten team-flate, høy endringstakt) — innføres branch protection, må auto-merge-designet revurderes samtidig.
- **Herdingen** (SHA-pinning, `persist-credentials: false`, minste privilegium per jobb) følger vi Golden Path på — og er strengere enn den på noen punkter: jobbsplitt så untrusted kode og write-token aldri deler jobb (Golden Path bygger med `contents: write` i samme jobb), kun patch-automerge (Golden Path automerger også minor/major), aktør+forfatter-gating og TOCTOU-lukking med `--match-head-commit`.
- **Golden Path-elementer vi ikke har tatt inn (ennå):** dependency submission via `gradle/actions/dependency-submission` i app-repoene (libs har det i publiserings-workflowen sin; appene mangler det, så deres Dependabot-alerts dekker ikke transitive avhengigheter), `dependency-review-action` på PR-er, Trivy secret-scan etter image-bygg, og CodeQL på `actions`-språket med `security-extended` (delvis dekket av actionlint+zizmor).
  Vurderingene spores i #31.
- `nais/what-changed` er mest relevant for image-bygg og er ikke tatt i bruk; vurder ved behov.

## Konvensjoner

- **Caller-filene skal være like på tvers av repoene**: samme filnavn, samme `name:`, samme struktur og kommentarer.
  Kun det som reelt er repo-spesifikt (f.eks. `java-version`-input) får avvike — en diff mellom to repos callere skal kunne leses som en liste over reelle forskjeller mellom repoene.
  Navnestandard: calleren heter det samme som funksjonen (`Dependabot auto-merge`, `Lint workflows`), den delte workflowen har `(delt)`-suffiks i `name:`.
- Callere pinner til `@main` (navikt-eid repo); tredjeparts-actions inne i de delte workflowene SHA- eller digest-pinnes med versjonstag/-kommentar (`# vX.Y.Z`, `# v0` for nais-actions, `docker://…:tag@sha256:…` for images).
  `@main` betyr at metarepoets main er en tillitsgrense: write-tilgang hit gir innflytelse på callernes CI, så endringer i delte workflows skal reviewes deretter.
- Send secrets eksplisitt fra calleren, aldri `secrets: inherit` — inherit eksponerer alle repoets og org-delte secrets for den delte workflowen.
- Repo-variasjon håndteres med `inputs` (f.eks. `gradle-kommando`), ikke ved å forgrene workflowen.
  Defaultene i delt workflow er flåtestandarden — callerne sender kun inputs ved reelt avvik (ingen `java-version: '25'`-duplisering i callerne).
- Gate-callerne trigger på både `push` (interne brancher) og `pull_request` (fork-PR-er); guarden som hindrer dobbeltkjøring bor i delt workflow, siden `github`-konteksten der reflekterer callerens event.
  Det samme gjelder Dependabot-skippen i gradle-gaten (auto-merge tester de branchene) — triggere må bo i calleren, all guard-logikk bor sentralt.
- `permissions: {}` på toppnivå i callere; jobbrettigheter settes i calleren, og den delte workflowen kan kun nedgradere dem (aldri utvide) — den delte deklarerer derfor sitt eget eksplisitte behov som cap.
- Metarepoets `dependabot.yml` holder `uses:`-SHA-ene ferske; zizmor-versjonen (`version:`-input) og actionlint-taggen i `docker://`-referansen er egne, manuelle vedlikeholdspunkter.
- Workflows her sikkerhetsreviewes mot GitHubs hardening-guide, zizmor-sjekkene og sikkerhet.nav.no før merge — reviewlogg og funn ligger i #31.
  Hold nye workflows til samme standard: kontekst via env i run-steg (også inputs — bruk env+eval), jq for payload-bygging, aktør- og forfatter-gating for bot-workflows.
  `lint.yml` håndhever dette maskinelt: actionlint og zizmor (begge blokkerende) kjører på alle endringer under `.github/`.
- Workflows som kjører untrusted kode (f.eks. bygg av en Dependabot-bumpet avhengighet) splittes i jobber slik at write-token og tredjepartskode aldri deler jobb; jobben med write-token skal ikke ha checkout.
  Se sikkerhetsdesign-kommentaren øverst i `dependabot-auto-merge.yml`.
- Repo som kaller delte workflows trenger en `.github/zizmor.yml` med `unpinned-uses`-policyen `"navikt/tiltakspenger/*": ref-pin` (ellers flagges `@main`-referansen) — kopier fra dette repoet eller libs, og behold begrunnelseskommentarene.
  Zizmor-unntak skal alltid ha en begrunnelse i konfigen; informational-funn rapporteres ikke (`min-severity: low` i den delte workflowen).

## Ingen publisering

Delte workflows er ikke artefakter: callerne henter fila direkte fra `main` ved kjøring.
Eneste krav er at endringer er pushet hit, og at filene ligger flatt i `.github/workflows/` (GitHub tillater ikke undermapper).

## Hvorfor metarepoet?

Kort: metarepoet er allerede det tverrgående koordineringspunktet, og porteføljen er liten — se seksjonen «Delte GitHub Actions-workflows» i [rot-README-en](../../README.md) for hele begrunnelsen (inkl. hvorfor ikke tiltakspenger-libs).
Vokser porteføljen, kan workflowene flyttes til et eget `tiltakspenger-workflows`-repo (normen i Nav, jf. `aap-workflows` m.fl.) — flyttingen er én endret linje per caller-repo.
