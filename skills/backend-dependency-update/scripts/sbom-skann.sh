#!/bin/bash
# Henter GitHubs dependency-graph-SBOM for hvert repo og skanner den med trivy.
# Samme graf som Dependabot-alerts bygger på, men med fiksversjon per funn og uten krav om alert-scope på tokenet.
#
# Bruk: sbom-skann.sh [repo ...]      (uten argumenter: hele flåten)
# Skriver <repo>-sbom.json og <repo>-trivy.json i gjeldende mappe, og én linje per funn til stdout.
# Krever gh (innlogget) og trivy. Funn i scope development (buildscript/test) havner ikke i imaget – triager på scope etterpå.
set -u
REPOER=("$@")
if [ ${#REPOER[@]} -eq 0 ]; then
  REPOER=(tiltakspenger-libs tiltakspenger-arena tiltakspenger-datadeling tiltakspenger-journalposthendelser
    tiltakspenger-meldekort-api tiltakspenger-saksbehandling-api tiltakspenger-soknad-api tiltakspenger-tiltak
    tiltakspenger-soknad tiltakspenger-saksbehandling tiltakspenger-meldekort tiltakspenger-meldekort-microfrontend
    tiltakspenger-pdfgenrs tiltakspenger-workflows tiltakspenger-iac)
fi
for r in "${REPOER[@]}"; do
  # Pause mellom kallene: uten den svarer API-et tomt på hvert andre repo.
  sleep 3
  if ! gh api "/repos/navikt/$r/dependency-graph/sbom" 2>/dev/null | python3 -c "import json,sys; json.dump(json.load(sys.stdin)['sbom'], open('$r-sbom.json','w'))" 2>/dev/null; then
    echo "$r: SBOM kunne ikke hentes (prøv igjen)"; continue
  fi
  trivy sbom --quiet --format json -o "$r-trivy.json" "$r-sbom.json" 2>/dev/null
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
