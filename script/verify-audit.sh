#!/usr/bin/env bash
#
# verify-audit.sh — verifiserer pgaudit-oppsettet for appene med database.
#
# Dokumentasjon:
#   https://doc.nais.io/persistence/cloudsql/how-to/enable-auditing/
#   https://cloud.google.com/sql/docs/postgres/pg-audit
#
# Bruk:
#   ./script/verify-audit.sh [app ...]
#
# Miljøvariabler (valgfrie):
#   TEAM        team/namespace å bruke (default: tpts)
#   REASON      begrunnelse for NAIS CLI (default: verify audit config)
#   CONTEXTS    mellomromsseparert liste med GCP-contexts (default: "dev-gcp prod-gcp")
#
# Merk: denne versjonen bruker NAIS CLI's `-e`-flag for å velge miljø/context.
#
set -uo pipefail

TEAM="${TEAM:-tpts}"
REASON="${REASON:-verify audit config}"
CONTEXTS="${CONTEXTS:-dev-gcp prod-gcp}"

if [[ $# -gt 0 ]]; then
    apps=("$@")
else
    apps=(
        "tiltakspenger-datadeling"
        "tiltakspenger-journalposthendelser"
        "tiltakspenger-meldekort-api"
        "tiltakspenger-saksbehandling-api"
        "tiltakspenger-soknad-api"
    )
fi

if ! command -v nais >/dev/null 2>&1; then
    echo "Mangler 'nais' på PATH." >&2
    exit 1
fi

printf 'Verifiserer audit-oppsett for %d app(er) i %s\n' "${#apps[@]}" "$TEAM"

failed=0
for app in "${apps[@]}"; do
    for context in $CONTEXTS; do
        echo
        echo "=== $app [$context] ==="
        output="$(nais postgres verify-audit "$app" -t "$TEAM" -e "$context" -r "$REASON" 2>&1)"
        rc=$?
        printf '%s\n' "$output"
        if [[ $rc -eq 0 ]] && grep -q 'All audit configurations are correct!' <<<"$output"; then
            echo "[OK] $app [$context]"
        else
            echo "[FAIL] $app [$context]"
            echo "  Se dokumentasjonen: https://doc.nais.io/persistence/cloudsql/how-to/enable-auditing/"
            echo "  Hvis extension mangler, kjør: nais postgres enable-audit $app --team $TEAM --environment $context"
            failed=$((failed + 1))
        fi
    done
done

echo
if (( failed > 0 )); then
    echo "Ferdig med $failed feil." >&2
    exit 1
fi

echo "Alle verifikasjoner fullført uten feil."
