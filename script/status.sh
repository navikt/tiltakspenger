#!/usr/bin/env bash
#
# status.sh — gir et hurtigblikk på tilstanden til tiltakspenger:
#   1) Siste byggstatus på main for alle våre GitHub-repoer (via `gh`)
#   2) Status på alle pods i namespace `tpts` i dev og prod (via `kubectl`)
#
# Forventer at du allerede er logget inn:
#   - GitHub:  `gh auth login`
#   - NAIS:    `nais kubeconfig`  (gir kubectl-contexts som dev-gcp/prod-gcp/…)
# Scriptet sjekker ikke innlogging — kommandoene feiler på vanlig måte hvis du
# ikke er logget inn, og det er greit.
#
# NB: on-prem-klyngene (*-fss) krever naisdevice. Er ikke 'onprem-k8s-dev'/
# 'onprem-k8s-prod' huket av i naisdevice, gir scriptet en kort melding om det
# i stedet for å henge — se KUBE_TIMEOUT.
#
# Miljøvariabler (valgfrie overstyringer):
#   NAMESPACE       namespace å se på            (default: tpts)
#   GH_ORG          GitHub-organisasjon          (default: navikt)
#   DEV_CLUSTERS    kubectl-contexts for dev     (default: "dev-gcp dev-fss")
#   PROD_CLUSTERS   kubectl-contexts for prod    (default: "prod-gcp prod-fss")
#   KUBE_TIMEOUT    sekunder før en treg/utilgjengelig klynge gis opp (default: 8)
#   GH_TIMEOUT      sekunder per gh-kall (kjøres parallelt)      (default: 20)
#   DEPLOY_WORKFLOW navn på deploy-workflowen som rapporteres    (default: "Build and deploy")
#   REPOS           mellomromsseparert liste av  (default: oppdages fra git-remotes
#                   navikt/<repo> å sjekke                under monorepo-rota)

set -uo pipefail

NAMESPACE="${NAMESPACE:-tpts}"
GH_ORG="${GH_ORG:-navikt}"
DEV_CLUSTERS="${DEV_CLUSTERS:-dev-gcp dev-fss}"
PROD_CLUSTERS="${PROD_CLUSTERS:-prod-gcp prod-fss}"

# Rota til monorepoet (mappa over script/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- farger (slås av hvis ikke tty) ---------------------------------------
if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'
    YELLOW=$'\033[33m'; BLUE=$'\033[34m'; RESET=$'\033[0m'
else
    BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi

header() { printf '\n%s━━━ %s ━━━%s\n' "$BOLD$BLUE" "$1" "$RESET"; }

# printf sin %-Ns teller BYTES, ikke tegn — multibyte-tegn (✓, ✗, —) gjør at
# kolonnene forskyves. pad fyller til ønsket antall tegn i stedet.
pad() {
    local s="$1" w="$2"
    local fill=$(( w - ${#s} ))
    (( fill < 0 )) && fill=0
    printf '%s%*s' "$s" "$fill" ''
}

# --- tid: GitHub gir ISO-8601 i UTC; vis lokal tid + alder -----------------
# BSD- (macOS) og GNU-date har ulik syntaks for parsing — sjekk én gang.
if date -j >/dev/null 2>&1; then
    iso_to_epoch()   { date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%s 2>/dev/null; }
    epoch_to_local() { date -r "$1" "+%Y-%m-%d %H:%M"; }
else
    iso_to_epoch()   { date -d "$1" +%s 2>/dev/null; }
    epoch_to_local() { date -d "@$1" "+%Y-%m-%d %H:%M"; }
fi

NOW_EPOCH="$(date +%s)"

fmt_when() {  # "2026-07-22T13:36:01Z" → "2026-07-22 15:36 (2 t)"
    local iso="$1" epoch diff age
    [[ -z "$iso" ]] && return 0
    epoch="$(iso_to_epoch "$iso")"
    if [[ -z "$epoch" ]]; then printf '%s' "$iso"; return 0; fi
    diff=$(( NOW_EPOCH - epoch ))
    if   (( diff < 90 ));     then age="nå"
    elif (( diff < 5400 ));   then age="$(( (diff + 30) / 60 )) min"
    elif (( diff < 129600 )); then age="$(( (diff + 1800) / 3600 )) t"
    else                           age="$(( (diff + 43200) / 86400 )) d"
    fi
    printf '%s (%s)' "$(epoch_to_local "$epoch")" "$age"
}

# --- verktøysjekk ----------------------------------------------------------
for tool in gh kubectl jq; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "${RED}Mangler '$tool' på PATH.${RESET}" >&2; exit 1; }
done

# --- finn repoer ----------------------------------------------------------
# Bruk REPOS hvis satt, ellers oppdag navikt/tiltakspenger*-repoer fra git-remotes
# i monorepo-rota (selve rota + alle sub-repoer som har egen origin).
discover_repos() {
    {
        for d in "$ROOT" "$ROOT"/*/; do
            url="$(git -C "$d" remote get-url origin 2>/dev/null)" || continue
            # git@github.com:navikt/foo.git  /  https://github.com/navikt/foo
            echo "$url" | grep -oE "$GH_ORG/[A-Za-z0-9._-]+"
        done
    } | sed 's/\.git$//' | sort -u
}

if [[ -n "${REPOS:-}" ]]; then
    read -r -a repo_list <<< "$REPOS"
else
    mapfile -t repo_list < <(discover_repos)
fi

# ==========================================================================
# 1) Byggstatus på main
# ==========================================================================
header "Siste bygg på main (${#repo_list[@]} repoer)"
printf '%s%-44s %-14s %-22s %-26s %s%s\n' "$DIM" "REPO" "STATUS" "WORKFLOW" "NÅR" "LENKE" "$RESET"

# Vi vil vise SISTE UTRULLING (alle repoer kaller deploy-workflowen "Build and
# deploy") — ikke siste CodeQL/Dependabot-kjøring. Repoer uten en slik workflow
# (metarepoet, tiltakspenger-iac) faller tilbake til én rad per workflow.
DEPLOY_WORKFLOW="${DEPLOY_WORKFLOW:-Build and deploy}"
GH_TIMEOUT="${GH_TIMEOUT:-20}"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

gh_to=""
command -v timeout  >/dev/null 2>&1 && gh_to="timeout $GH_TIMEOUT"
[[ -z "$gh_to" ]] && command -v gtimeout >/dev/null 2>&1 && gh_to="gtimeout $GH_TIMEOUT"

# Henter status for ett repo; skriver en JSON-array til stdout (én rad per
# workflow som skal vises).
#
# NB: vi henter de siste kjøringene UFILTRERT og velger ut deploy-workflowen
# selv. GitHubs filtrerte endepunkter (--workflow/--branch) går via en
# søkeindeks som kan henge etter og servere en gammel kjøring som «siste»,
# mens den ufiltrerte lista leses ferskt. (Observert i praksis: en to uker
# gammel kjøring rapportert som siste, minutter etter en deploy.)
fetch_repo() {
    local repo="$1" runs deploy row
    runs="$($gh_to gh run list --repo "$repo" --limit 100 \
        --json status,conclusion,workflowName,createdAt,url,headBranch 2>/dev/null)"
    [[ -z "$runs" ]] && runs="[]"

    deploy="$(jq -c --arg wf "$DEPLOY_WORKFLOW" \
        '[.[] | select(.headBranch == "main" and .workflowName == $wf)][:1]' \
        <<<"$runs" 2>/dev/null)"
    if [[ -n "$deploy" && "$deploy" != "[]" ]]; then
        printf '%s\n' "$deploy"
        return
    fi

    # Ingen deploy blant de 100 ferskeste kjøringene — spør målrettet i
    # tilfelle siste deploy bare er eldre enn vinduet. (Dette kallet kan gi
    # foreldet svar pga. søkeindeksen, men da er deployen uansett gammel.)
    deploy="$($gh_to gh run list --repo "$repo" --branch main \
        --workflow "$DEPLOY_WORKFLOW" --limit 1 \
        --json status,conclusion,workflowName,createdAt,url 2>/dev/null)"
    if [[ -n "$deploy" && "$deploy" != "[]" ]]; then
        printf '%s\n' "$deploy"
        return
    fi

    # Repoer uten én samlende deploy-workflow har flere selvstendige workflows.
    # Enumerer de definerte og vis siste kjøring av HVER (også aldri kjørte).
    #  - dynamic/-workflows (Dependabot Updates, Copilot, …) er GitHub-interne
    #    og ikke bygg — hopp over.
    #  - Delte reusable workflows («(delt)»-suffiks, jf. .github/workflows/
    #    README.md) kjører aldri selvstendig og ville stått som evige
    #    «ingen kjøringer»-rader.
    $gh_to gh workflow list --repo "$repo" --json name,path \
        -q '.[] | select(.path | startswith("dynamic/") | not) | .name' 2>/dev/null \
    | while IFS= read -r wf; do
        [[ -z "$wf" || "$wf" == *"(delt)" ]] && continue
        row="$(jq -c --arg wf "$wf" \
            'first(.[] | select(.headBranch == "main" and .workflowName == $wf)) // empty' \
            <<<"$runs" 2>/dev/null)"
        if [[ -z "$row" ]]; then
            row="$($gh_to gh run list --repo "$repo" --branch main \
                --workflow "$wf" --limit 1 \
                --json status,conclusion,workflowName,createdAt,url 2>/dev/null \
                | jq -c '.[0] // empty')"
        fi
        [[ -z "$row" ]] && row="$(jq -nc --arg w "$wf" \
            '{status:"", conclusion:"", workflowName:$w, createdAt:"", url:""}')"
        printf '%s\n' "$row"
    done | jq -s 'sort_by(.workflowName)'
}

# Hent alle repoer parallelt — gh-kallene er uavhengige, så vi slipper å vente
# sekvensielt på de tregeste. Resultatet skrives til en temp-fil per repo og
# rendres etterpå i opprinnelig (sortert) rekkefølge.
i=0
for repo in "${repo_list[@]}"; do
    fetch_repo "$repo" > "$tmpdir/$i.json" &
    i=$((i + 1))
done
wait

i=0
for repo in "${repo_list[@]}"; do
    run_json="$(cat "$tmpdir/$i.json" 2>/dev/null)"
    i=$((i + 1))

    if [[ -z "$run_json" || "$run_json" == "[]" ]]; then
        printf '%-44s %s%s %s%s\n' "$repo" "$DIM" "$(pad "—" 14)" "ingen kjøringer / utilgjengelig" "$RESET"
        continue
    fi

    # Ett repo kan gi flere rader (én per workflow, jf. tiltakspenger-iac).
    # Vis repo-navnet kun på første rad; resten innrykkes under.
    n="$(echo "$run_json" | jq 'length')"
    for ((r = 0; r < n; r++)); do
        # Feltene skilles med unit separator (0x1f) — en non-whitespace separator
        # som hindrer at read kollapser tomme felt (f.eks. tom conclusion mens en
        # kjøring pågår, eller en workflow som aldri har kjørt). Med tab/space ville
        # tomme felt forsvinne og kolonnene forskyves.
        IFS=$'\x1f' read -r status conclusion workflow created url < <(
            echo "$run_json" | jq -r --argjson r "$r" '.[$r] | [.status, (.conclusion // ""), .workflowName, .createdAt, .url] | join("\u001f")')

        # Velg det mest beskrivende statusordet + farge
        state="$conclusion"
        [[ "$status" != "completed" || -z "$state" ]] && state="$status"
        case "$state" in
            success)            color="$GREEN"; icon="✓" ;;
            failure|startup_failure|timed_out|cancelled|action_required)
                                color="$RED";   icon="✗" ;;
            in_progress|queued|requested|waiting|pending)
                                color="$YELLOW"; icon="•" ;;
            *)                  color="$YELLOW"; icon="?" ;;
        esac

        label="$repo"
        [[ "$r" -gt 0 ]] && label=""

        # Workflow definert, men aldri kjørt på main
        if [[ -z "$status" && -z "$created" ]]; then
            printf '%-44s %s%s%s %-22s %singen kjøringer%s\n' \
                "$label" "$DIM" "$(pad "—" 14)" "$RESET" "$workflow" "$DIM" "$RESET"
            continue
        fi

        printf '%-44s %s%s%s %-22s %s%s %s%s\n' \
            "$label" "$color" "$(pad "$icon $state" 14)" "$RESET" \
            "$workflow" "$DIM" "$(pad "$(fmt_when "$created")" 26)" "$url" "$RESET"
    done
done

# ==========================================================================
# 2) Pod-status i dev og prod
# ==========================================================================

# Kort timeout slik at en utilgjengelig klynge ikke henger lenge. kubectl sin
# `--request-timeout` stopper IKKE den gjentatte API-discovery-retryen (kan ta
# ~40s mot en uoppnåelig on-prem-klynge), og `timeout`-binæren finnes ikke alltid
# på macOS — så vi bruker en egen bash-watchdog som ytre grense.
KUBE_TIMEOUT="${KUBE_TIMEOUT:-8}"

# run_capped <sekunder> <kommando...> : kjører kommandoen, dreper den hvis den
# bruker mer enn <sekunder>. Stdout+stderr samles i $RUN_OUT, returkode i $RUN_RC
# (124 = timeout, som GNU `timeout`).
run_capped() {
    local secs="$1"; shift
    local outfile; outfile="$(mktemp)"
    "$@" >"$outfile" 2>&1 &
    local pid=$!
    local waited=0
    while kill -0 "$pid" 2>/dev/null; do
        if (( waited >= secs )); then
            kill "$pid" 2>/dev/null
            sleep 1
            kill -9 "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            RUN_OUT="$(cat "$outfile")"; rm -f "$outfile"
            RUN_RC=124
            return 124
        fi
        sleep 1
        waited=$(( waited + 1 ))
    done
    wait "$pid" 2>/dev/null; RUN_RC=$?
    RUN_OUT="$(cat "$outfile")"; rm -f "$outfile"
    return "$RUN_RC"
}

pods_for_env() {
    local env_label="$1"; shift
    local clusters=("$@")
    header "Pods i $env_label (namespace: $NAMESPACE)"
    for ctx in "${clusters[@]}"; do
        printf '%s· context %s%s\n' "$BOLD" "$ctx" "$RESET"

        # `--request-timeout` kapper hver enkelt request; watchdogen er den harde
        # ytre grensen så en uoppnåelig klynge ikke henger på retry-loopen.
        local out rc
        run_capped "$KUBE_TIMEOUT" kubectl --context "$ctx" -n "$NAMESPACE" \
            --request-timeout="${KUBE_TIMEOUT}s" get pods
        out="$RUN_OUT"; rc="$RUN_RC"

        if [[ $rc -eq 0 ]]; then
            echo "$out" | sed 's/^/    /'
            continue
        fi

        # Feilet — gi en kort, handlingsrettet melding i stedet for rå støy.
        if [[ "$ctx" == *-fss ]] && \
           { [[ $rc -eq 124 ]] || echo "$out" | grep -qiE "i/o timeout|deadline exceeded|dial tcp|no route to host|connection refused"; }; then
            echo "    ${YELLOW}⚠ Får ikke kontakt med $ctx (on-prem).${RESET}"
            echo "    ${YELLOW}  on-prem-klyngene krever naisdevice — huk av '${BOLD}onprem-k8s-${env_label,,}${RESET}${YELLOW}' i naisdevice og prøv igjen.${RESET}"
        elif echo "$out" | grep -qiE "forbidden|unauthorized|Unable to connect to the server.*credentials|error: You must be logged in"; then
            echo "    ${YELLOW}⚠ Ikke autorisert mot $ctx — kjør 'nais kubeconfig' eller logg inn på nytt.${RESET}"
        elif echo "$out" | grep -qiE "context .* does not exist|no context exists"; then
            echo "    ${YELLOW}⚠ Contexten '$ctx' finnes ikke i kubeconfig — kjør 'nais kubeconfig'.${RESET}"
        else
            # Ukjent feil: vis første linje så man ikke mister info helt.
            echo "    ${RED}✗ Feil mot $ctx:${RESET} $(echo "$out" | head -1)"
        fi
    done
}

# shellcheck disable=SC2086
pods_for_env "DEV"  $DEV_CLUSTERS
# shellcheck disable=SC2086
pods_for_env "PROD" $PROD_CLUSTERS

echo
