# Delte GitHub Actions-workflows

Workflowene i denne mappa er [reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows) som kalles fra `tiltakspenger*`-repoene.
Arbeidet spores i [navikt/tiltakspenger#31](https://github.com/navikt/tiltakspenger/issues/31).

## Bruk fra et repo

Calleren er en tynn workflow med trigger, rettigheter og et `uses`-kall:

```yaml
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

Se toppen av hver workflow-fil for hvilke rettigheter, secrets og inputs akkurat den krever.

## Hvilke repoer dekkes

`lint-workflows.yml` (actionlint + zizmor) er språkagnostisk og kan kalles fra alle repoene; metarepoet kaller den selv fra `lint.yml` med lokal sti, slik at PR-er som endrer delte workflows testes med sin egen versjon.
zizmor kjører ikke-blokkerende inntil unntak er nedfelt i en `zizmor.yml` med begrunnelse; da settes `zizmor-blokkerende: true` i callerne.

`dependabot-auto-merge.yml` er verifisert kompatibel med alle de 8 Kotlin/JVM-backend-repoene (libs, arena, saksbehandling-api, tiltak, soknad-api, datadeling, meldekort-api, journalposthendelser) — per 2026-07-17 kjører alle Java 25, `./gradlew build --configuration-cache`, og har `SLACK_VARSEL_WEBHOOK_URL` som Dependabot-secret.
Frontend-repoene, pdfgen/pdfgenrs og iac har ingen auto-merge-workflow i dag; byggesteget her er Gradle-spesifikt, så de trenger i så fall en egen delt variant (f.eks. `dependabot-auto-merge-npm.yml`) — ikke flere inputs på denne.

## Forholdet til Nais-dokumentasjonen og Golden Path

Nav har to delvis divergerende referanser for workflows: [Nais-dokumentasjonen](https://docs.nais.io/build/how-to/build-and-deploy/) og [`navikt/backend-golden-path`](https://github.com/navikt/backend-golden-path) (jf. Slack-diskusjon 2026-07-17; nais-teamet bekrefter at Golden Path er «best practices», ikke fasit).
Kjente forskjeller: Nais-doc bruker `nais/what-changed` (skip av unødige bygg) og GitHubs innebygde automerge for Dependabot, Golden Path bruker `navikt/automerge-dependabot`, har deploy i egen jobb, gjør dependency submission og secret-scanning etter image-bygg, og legger på herding som `persist-credentials: false`.

Der vi avviker, er det bevisst:

- **Dependabot-merging:** vi bruker verken GitHubs automerge (krever påkrevde sjekker på main, som vi ikke har — og har kjente begrensninger rundt scheduling/options, jf. nais-teamet) eller `navikt/automerge-dependabot`, men direkte `gh pr merge` etter grønt bygg i samme workflow.
  Det gir oss byggegate + den bevisste egenskapen at merge med `GITHUB_TOKEN` aldri trigger publisering/deploy.
- **Herdingen** (SHA-pinning, `persist-credentials: false`, minste privilegium, dependency submission) følger vi Golden Path på — se sikkerhetsreview-notatet under Konvensjoner.
- `nais/what-changed` er mest relevant for image-bygg og er ikke tatt i bruk; vurder ved behov.

## Konvensjoner

- Callere pinner til `@main` (navikt-eid repo); tredjeparts-actions inne i de delte workflowene SHA-pinnes med `# vX.Y.Z`-kommentar.
  `@main` betyr at metarepoets main er en tillitsgrense: write-tilgang hit gir innflytelse på callernes CI, så endringer i delte workflows skal reviewes deretter.
- Send secrets eksplisitt fra calleren, aldri `secrets: inherit` — inherit eksponerer alle repoets og org-delte secrets for den delte workflowen.
- Repo-variasjon håndteres med `inputs` (f.eks. `java-version`), ikke ved å forgrene workflowen.
- `permissions: {}` på toppnivå i callere; jobbrettigheter settes i calleren, og den delte workflowen kan kun nedgradere dem (aldri utvide) — den delte deklarerer derfor sitt eget eksplisitte behov som cap.
- Metarepoets `dependabot.yml` holder SHA-pinnene her ferske.
- Filene her er sikkerhetsreviewet mot GitHubs hardening-guide, zizmor-sjekkene og sikkerhet.nav.no (2026-07-17) — hold nye workflows til samme standard (kontekst via env i run-steg, jq for payload-bygging, aktør- og forfatter-gating for bot-workflows).
  `lint.yml` håndhever dette maskinelt: actionlint og zizmor (begge blokkerende) kjører på alle endringer under `.github/`.
- Repo som kaller delte workflows trenger en `.github/zizmor.yml` med `unpinned-uses`-policyen `"navikt/tiltakspenger/*": ref-pin` (ellers flagges `@main`-referansen) — kopier fra dette repoet eller libs, og behold begrunnelseskommentarene.
  Zizmor-unntak skal alltid ha en begrunnelse i konfigen; informational-funn rapporteres ikke (`min-severity: low` i den delte workflowen).

## Ingen publisering

Delte workflows er ikke artefakter: callerne henter fila direkte fra `main` ved kjøring.
Eneste krav er at endringer er pushet hit, og at filene ligger flatt i `.github/workflows/` (GitHub tillater ikke undermapper).

## Hvorfor metarepoet?

Kort: metarepoet er allerede det tverrgående koordineringspunktet, og porteføljen er liten — se seksjonen «Delte GitHub Actions-workflows» i [rot-README-en](../../README.md) for hele begrunnelsen (inkl. hvorfor ikke tiltakspenger-libs).
Vokser porteføljen, kan workflowene flyttes til et eget `tiltakspenger-workflows`-repo (normen i Nav, jf. `aap-workflows` m.fl.) — flyttingen er én endret linje per caller-repo.
