# Maler for repo-config

Kanonisk kilde for konfigfiler som skal være like på tvers av `tiltakspenger*`-repoene (jf. [#39](https://github.com/navikt/tiltakspenger/issues/39): standardene eies i metarepoet).
Kopier fila til repoets `.github/`, behold begrunnelseskommentarene, og gjør kun reelle repo-tilpasninger (med kommentar).

| Mal | Kopieres til | For |
| --- | --- | --- |
| `zizmor.yml` | `.github/zizmor.yml` | alle repo som kaller delte workflows |
| `dependabot-gradle.yml` | `.github/dependabot.yml` | Kotlin/JVM-repoene (gradle + actions) |
| `dependabot-node.yml` | `.github/dependabot.yml` | TypeScript/JavaScript-repoene (npm/pnpm + actions) |
| `dependabot-actions.yml` | `.github/dependabot.yml` | repo uten kodeavhengigheter (iac, pdfgen) |

Endres en mal her, oppdater repoene som bruker den (samme regel som for caller-workflows — se [workflows-README](../workflows/README.md)).
For `zizmor.yml` og `dependabot.yml` håndheves dette maskinelt: drift-vaktene i den delte lint-workflowen feiler hvis et repos kopi avviker fra malen (lenke-semantikk — GitHub kan ikke lenke config-filer på tvers av repo).
Dependabot-malen velges automatisk fra repo-innhold (gradle-fil → gradle, `package.json` → node, ellers actions); begrunnet avvik = `dependabot-mal: ingen` i lint-calleren med kommentar.
Standard `paths-ignore`-lister per repo-type står i workflows-README-ens konvensjonsseksjon.
