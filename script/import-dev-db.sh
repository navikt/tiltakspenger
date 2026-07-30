#!/usr/bin/env bash
#
# import-dev-db.sh — kopierer en dev-database ned i den tilsvarende lokale
# docker-compose-databasen.
#
# Scriptet gjør hele jobben som er beskrevet i README-seksjonen
# «Import av data til lokale databaser»:
#   1) starter den lokale postgres-containeren hvis den ikke kjører
#   2) starter en `nais postgres proxy` mot dev
#   3) `pg_dump` fra dev til en midlertidig mappe under /tmp
#   4) dropper og oppretter den lokale databasen på nytt (tom)
#   5) `pg_restore` inn i den tomme databasen
#
# Bruk (vanligvis via wrapperne):
#   ./script/import-dev-db-saksbehandling.sh <GCP-brukernavn>
#   ./script/import-dev-db-meldekort.sh <GCP-brukernavn>
#
#   ./script/import-dev-db.sh <app-nøkkel> <GCP-brukernavn>
#
# <GCP-brukernavn> er e-posten din slik CloudSQL kjenner den, f.eks.
# `fornavn.etternavn@nav.no`. Kjør `gcloud config get-value account` hvis du er usikker.
#
# Forutsetninger: `pg_dump`/`pg_restore` versjon 17+ (for `--exclude-extension`),
# `psql`, `docker`, og innlogget nais CLI (`nais login`).
#
set -uo pipefail

TEAM="tpts"
ENVIRONMENT="dev-gcp"
# NB: nais CLI krever at begrunnelsen er minst 10 tegn.
REASON="import dev-data til lokal database"
LOCAL_USER="postgres"
LOCAL_PASSWORD="test"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- farger (slås av hvis ikke tty) ---------------------------------------
if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'
    GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
else
    BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; RESET=""
fi

info() { printf '%s==>%s %s\n' "${BOLD}" "${RESET}" "$*"; }
ok() { printf '%s  ✔%s %s\n' "${GREEN}" "${RESET}" "$*"; }
warn() { printf '%s  !%s %s\n' "${YELLOW}" "${RESET}" "$*" >&2; }
die() { printf '%s  ✖ %s%s\n' "${RED}" "$*" "${RESET}" >&2; exit 1; }

# --- appkonfigurasjon ------------------------------------------------------
# nøkkel|nais-app|dev-database|compose-tjeneste|lokal port|standard proxy-port
APPS=(
    "saksbehandling|tiltakspenger-saksbehandling-api|saksbehandling|postgresSaksbehandling|5433|5444"
    "meldekort|tiltakspenger-meldekort-api|meldekort|postgresMeldekort|5435|5445"
)

usage() {
    echo "Bruk: $(basename "$0") <app-nøkkel> <GCP-brukernavn>" >&2
    echo "Gyldige app-nøkler:" >&2
    for rad in "${APPS[@]}"; do
        echo "  - ${rad%%|*}" >&2
    done
}

if [[ $# -ne 2 ]]; then
    usage
    exit 1
fi

APP_KEY="$1"
GCP_USER="$2"

NAIS_APP=""; DEV_DB=""; COMPOSE_SERVICE=""; LOCAL_PORT=""; DEFAULT_PROXY_PORT=""
for rad in "${APPS[@]}"; do
    IFS='|' read -r nokkel app db tjeneste port proxyport <<<"${rad}"
    if [[ "${nokkel}" == "${APP_KEY}" ]]; then
        NAIS_APP="${app}"; DEV_DB="${db}"; COMPOSE_SERVICE="${tjeneste}"
        LOCAL_PORT="${port}"; DEFAULT_PROXY_PORT="${proxyport}"
        break
    fi
done
[[ -n "${NAIS_APP}" ]] || { echo "Ukjent app-nøkkel: ${APP_KEY}" >&2; usage; exit 1; }

PROXY_PORT="${PROXY_PORT:-${DEFAULT_PROXY_PORT}}"

# Port 8085 er reservert for `nais login` sin callback og skal aldri bindes.
[[ "${PROXY_PORT}" != "8085" ]] || die "PROXY_PORT=8085 er reservert for \`nais login\`."
[[ "${PROXY_PORT}" != "${LOCAL_PORT}" ]] || die "PROXY_PORT kan ikke være den lokale databaseporten (${LOCAL_PORT})."

# --- sjekk av verktøy ------------------------------------------------------
for verktoy in pg_dump pg_restore psql pg_isready docker nais; do
    command -v "${verktoy}" >/dev/null 2>&1 || die "Fant ikke '${verktoy}' på PATH."
done

# `--exclude-extension` kom i pg_dump 17. Uten den feiler restoren på pgaudit,
# som finnes i CloudSQL, men ikke i det lokale postgres-imaget.
pg_dump_major="$(pg_dump --version | grep -oE '[0-9]+' | head -1)"
[[ "${pg_dump_major}" -ge 17 ]] ||
    die "pg_dump er versjon ${pg_dump_major}; trenger 17 eller nyere for --exclude-extension."

# --- opprydding ------------------------------------------------------------
PROXY_PID=""
PROXY_LOG=""
DUMP_DIR=""
opprydding() {
    if [[ -n "${PROXY_PID}" ]] && kill -0 "${PROXY_PID}" 2>/dev/null; then
        kill "${PROXY_PID}" 2>/dev/null
        wait "${PROXY_PID}" 2>/dev/null
    fi
    [[ -n "${PROXY_LOG}" ]] && rm -f "${PROXY_LOG}"
    if [[ -n "${DUMP_DIR}" && -d "${DUMP_DIR}" ]]; then
        rm -rf "${DUMP_DIR}"
    fi
}
trap opprydding EXIT

port_i_bruk() {
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

# Skriver ut det nais CLI sa, slik at den egentlige feilen ikke drukner i en
# generisk timeout (typisk «reason must be at least 10 characters», manglende
# `nais login`, eller at porten er opptatt).
vis_proxy_logg() {
    if [[ -s "${PROXY_LOG}" ]]; then
        echo "--- utdata fra nais postgres proxy ---" >&2
        sed 's/^/    /' "${PROXY_LOG}" >&2
        echo "--------------------------------------" >&2
    fi
}

# Venter til proxyen svarer. Gir opp umiddelbart hvis nais-prosessen dør, i
# stedet for å vente ut hele tidsvinduet.
vent_pa_proxy() {
    local port="$1" forsok=0
    while (( forsok < 60 )); do
        if pg_isready --host=127.0.0.1 --port="${port}" --timeout=2 --quiet; then
            return 0
        fi
        if ! kill -0 "${PROXY_PID}" 2>/dev/null; then
            warn "nais postgres proxy avsluttet etter ${forsok}s."
            vis_proxy_logg
            return 1
        fi
        sleep 1
        forsok=$((forsok + 1))
    done
    warn "Proxyen svarte ikke innen 60s."
    vis_proxy_logg
    return 1
}

echo
info "${BOLD}Importerer ${DEV_DB} fra ${ENVIRONMENT} (${NAIS_APP}) til lokal port ${LOCAL_PORT}${RESET}"

# --- 1) lokal database -----------------------------------------------------
info "Starter lokal database (${COMPOSE_SERVICE}) …"
(cd "${ROOT}" && docker compose up -d "${COMPOSE_SERVICE}") >/dev/null ||
    die "Klarte ikke starte compose-tjenesten ${COMPOSE_SERVICE}."

export PGPASSWORD="${LOCAL_PASSWORD}"
for _ in $(seq 1 30); do
    psql --host=localhost --port="${LOCAL_PORT}" --username="${LOCAL_USER}" \
        --dbname=postgres -tAc 'select 1' >/dev/null 2>&1 && break
    sleep 1
done
psql --host=localhost --port="${LOCAL_PORT}" --username="${LOCAL_USER}" \
    --dbname=postgres -tAc 'select 1' >/dev/null 2>&1 ||
    die "Får ikke kontakt med lokal database på port ${LOCAL_PORT}."
ok "Lokal database svarer på port ${LOCAL_PORT}"

# --- 2) proxy mot dev ------------------------------------------------------
if port_i_bruk "${PROXY_PORT}"; then
    die "Port ${PROXY_PORT} er allerede i bruk. Stopp en eventuell proxy som kjører fra før, eller sett PROXY_PORT til en ledig port."
fi

unset PGPASSWORD
info "Starter nais postgres proxy mot ${NAIS_APP} på port ${PROXY_PORT} …"
PROXY_LOG="$(mktemp "/tmp/tiltakspenger-${APP_KEY}-proxy-XXXXXXXX.log")"
nais postgres proxy "${NAIS_APP}" \
    --port "${PROXY_PORT}" \
    --team "${TEAM}" \
    --environment "${ENVIRONMENT}" \
    --reason "${REASON}" >"${PROXY_LOG}" 2>&1 </dev/null &
PROXY_PID=$!

vent_pa_proxy "${PROXY_PORT}" ||
    die "Fikk ikke opp proxy mot ${NAIS_APP}. Sjekk at du er logget inn (\`nais login\`) og at naisdevice er tilkoblet (\`nais device status\`)."
ok "Proxy oppe på port ${PROXY_PORT}"

# --- 3) dump fra dev -------------------------------------------------------
DUMP_DIR="$(mktemp -d "/tmp/tiltakspenger-${APP_KEY}-dump-XXXXXXXX")"
info "Dumper ${DEV_DB} til ${DUMP_DIR} …"

# Ingen --schema-filtrering: cast-er tilhører ikke noe schema og hadde blitt
# utelatt. --exclude-extension dropper CloudSQL-utvidelser som pgaudit, som
# ikke finnes lokalt. Se README for detaljer.
pg_dump \
    --host=127.0.0.1 \
    --port="${PROXY_PORT}" \
    --dbname="${DEV_DB}" \
    --username="${GCP_USER}" \
    --format=directory \
    --no-owner \
    --no-privileges \
    --exclude-extension='*' \
    --file="${DUMP_DIR}/${DEV_DB}" || {
    vis_proxy_logg
    die "pg_dump feilet. Stemmer brukernavnet (${GCP_USER})? Kjør \`gcloud config get-value account\`."
}
ok "Dump ferdig ($(du -sh "${DUMP_DIR}" | cut -f1))"

# --- 4) tøm lokal database -------------------------------------------------
export PGPASSWORD="${LOCAL_PASSWORD}"
info "Tømmer lokal database ${DEV_DB} …"
psql --host=localhost --port="${LOCAL_PORT}" --username="${LOCAL_USER}" --dbname=postgres --quiet \
    -c "DROP DATABASE IF EXISTS \"${DEV_DB}\" WITH (FORCE);" \
    -c "CREATE DATABASE \"${DEV_DB}\";" ||
    die "Klarte ikke å opprette lokal database på nytt. Kjører appen og holder tilkoblinger åpne?"
ok "Lokal database ${DEV_DB} er tom"

# --- 5) restore ------------------------------------------------------------
info "Importerer dumpen …"
pg_restore \
    --host=localhost \
    --port="${LOCAL_PORT}" \
    --dbname="${DEV_DB}" \
    --username="${LOCAL_USER}" \
    --single-transaction \
    --no-owner \
    --no-privileges \
    "${DUMP_DIR}/${DEV_DB}" ||
    die "pg_restore feilet."

antall_tabeller="$(psql --host=localhost --port="${LOCAL_PORT}" --username="${LOCAL_USER}" \
    --dbname="${DEV_DB}" -tAc \
    "select count(*) from information_schema.tables where table_schema='public'")"
ok "Import ferdig — ${antall_tabeller} tabeller i public"
echo
