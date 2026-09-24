#!/bin/bash
# Henter GitHubs dependency-graph-SBOM for hvert repo og skanner den med trivy.
# Samme graf som Dependabot-alerts bygger på, men med fiksversjon per funn. Repoene er offentlige, så endepunktet leses uten token.
#
# Bruk: sbom-skann.sh [repo ...]      (uten argumenter: hele flåten)
# Skriver <repo>-sbom.json og <repo>-trivy.json i gjeldende mappe, og én linje per funn til stdout.
# Krever curl og trivy. SBOM-en bærer ikke scope; funn i buildscript og test havner ikke i imaget – avgjør scope etterpå (se SKILL.md).
# Metarepoet har ingen innsendt graf og er ikke med.
set -u
REPOER=("$@")
if [ ${#REPOER[@]} -eq 0 ]; then
  REPOER=(tiltakspenger-libs tiltakspenger-arena tiltakspenger-datadeling tiltakspenger-journalposthendelser
    tiltakspenger-meldekort-api tiltakspenger-saksbehandling-api tiltakspenger-soknad-api
    tiltakspenger-soknad tiltakspenger-saksbehandling tiltakspenger-meldekort tiltakspenger-meldekort-microfrontend
    tiltakspenger-pdfgenrs tiltakspenger-workflows tiltakspenger-iac)
fi
for r in "${REPOER[@]}"; do
  # Pause mellom kallene: uten den svarer API-et tomt på hvert andre repo.
  sleep 3
  if ! curl -fsSL "https://api.github.com/repos/navikt/$r/dependency-graph/sbom" 2>/dev/null | python3 -c "import json,sys; json.dump(json.load(sys.stdin)['sbom'], open('$r-sbom.json','w'))" 2>/dev/null; then
    echo "$r: SBOM kunne ikke hentes (prøv igjen)"; continue
  fi
  # Et gammelt resultat skal ikke leses som nytt når trivy feiler.
  rm -f "$r-trivy.json"
  if ! trivy sbom --quiet --format json -o "$r-trivy.json" "$r-sbom.json"; then
    echo "$r: trivy feilet"; continue
  fi
  python3 - "$r" <<'PY'
import json, sys
r = sys.argv[1]
d = json.load(open(f"{r}-trivy.json"))
sett = set()
for res in d.get("Results", []):
    for v in res.get("Vulnerabilities") or []:
        n = (v["VulnerabilityID"], v["PkgName"], v["InstalledVersion"])
        if n in sett:
            continue
        sett.add(n)
        print(f"{r:40} {v['Severity']:8} {v['VulnerabilityID']:22} {v['PkgName']}@{v['InstalledVersion']} -> {v.get('FixedVersion', '-')} | {(v.get('Title') or '')[:70]}")
PY
done
