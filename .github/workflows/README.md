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
    with:
      java-version: '25'
```

De faktiske callerne i repoene er den kanoniske malen — kopier derfra, ikke herfra.
Se toppen av hver workflow-fil for hvilke rettigheter, secrets og inputs akkurat den krever.

## Porteføljen

| Delt workflow | For | Nøkkel-inputs/secrets |
| --- | --- | --- |
| `lint-workflows.yml` | alle repoer (språkagnostisk) | `zizmor-blokkerende` |
| `dependabot-auto-merge.yml` | Kotlin/JVM-repoene | `java-version` |
| `dependabot-auto-merge-node.yml` | frontend-repoene (saksbehandling, soknad, meldekort, meldekort-microfrontend); npm/pnpm detekteres fra lockfila | `node-version`, `test-kommando`; secret `READER_TOKEN` (@navikt-pakker) |
| `test-og-bygg-gradle.yml` | JVM-app-repoene (erstatter lokal `.test-and-build.yml`; PR-gate med `bygg-image: false`) | `java-version`, `gradle-kommando`, `bygg-image` |
| `deploy-nais.yml` | alle repoer som deployer image til nais (erstatter lokal `.deploy-to-nais.yml`; bruker GitHub environment per miljø) | `NAIS_ENV`, `IMAGE`, `cluster-suffiks` (arena: `fss`), `nais-ressurs`, `nais-vars` (`ingen` deployer uten vars-fil) |
| `codeql-gradle.yml` | Kotlin/JVM-repoene (caller eier schedule + concurrency) | `java-version` |

Utrullingsstatus per repo spores i [#31](https://github.com/navikt/tiltakspenger/issues/31) — tabellen sier hvem workflowen er for, ikke hvem som bruker den i dag.

`lint-workflows.yml`: metarepoet kaller den selv fra `lint.yml` med lokal sti, slik at PR-er som endrer delte workflows testes med sin egen versjon.
zizmor kjører ikke-blokkerende i et repo inntil unntak er nedfelt i repoets `zizmor.yml` med begrunnelse; da settes `zizmor-blokkerende: true` i calleren.

`dependabot-auto-merge.yml` og `-node.yml` er tekstlig parallelle - kun byggejobben (og dens inputs/secrets, bl.a. `READER_TOKEN`) skiller dem; endres den ene, oppdater den andre tilsvarende.
Node-varianten dekker både npm og pnpm ved å detektere pakkehåndterer fra lockfila (`pnpm-lock.yaml` → pnpm) — npm→pnpm-migreringen (jf. nais-doc) krever dermed ingen caller-endring, bare bytte av lockfil i repoet.
Testene ligger i byggegatene: gradle-varianten kjører `./gradlew build` (inkl. tester), node-varianten kjører `npm ci`/`pnpm install --frozen-lockfile` + `test-kommando` (lint/tsc/test etter hva repoet har; `$PAKKEHANDTERER` er tilgjengelig i kommandoen).

`test-og-bygg-gradle.yml` eksponerer imaget som workflow-output `IMAGE`; deploy-calleren sender den videre til `deploy-nais.yml` via `needs.<jobb>.outputs.IMAGE` — det er komposisjonsmønsteret for bygg-og-deploy-pipelines.

**Bevisst ikke delt** (repo-spesifikk variasjon overstiger gevinsten i dag): frontendenes lokale byggeworkflows (`.build-app.yml` m.fl. — ENV-matrise, env-filer, CDN-opplasting, `image_suffix`), microfrontendens deploy (Astro + CDN), pdfgenrs' `.test.yml` (brevtester i Rust) og iac (rene manifest-deployer — kan adoptere `deploy-nais.yml` ved behov).

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
- Repo-variasjon håndteres med `inputs` (f.eks. `java-version`), ikke ved å forgrene workflowen.
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
