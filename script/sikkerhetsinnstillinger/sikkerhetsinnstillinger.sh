#!/usr/bin/env bash
#
# sikkerhetsinnstillinger.sh — sammenligner utvalgte sikkerhetsinnstillinger fra GitHubs REST-API på tvers av
# teamets repoer, én Markdown-rad per repo, slik at avvik er synlige. Bruker bare GET og setter ingenting.
# Arkiverte repoer listes under tabellen. Verdier som mangler eller ikke kan leses markeres som ukjente («?»),
# aldri som «av».
#
# Kolonner (kilde i parentes):
#   synlighet     public/private                                          (/repos/{r})
#   codeql        default = GitHubs default setup er konfigurert; workflow = en fil .github/workflows/*codeql* med
#                 egen trigger; begge = begge deler, og da avviser GitHub opplastingen fra workflowen. Navnesøket
#                 og trigger-sjekken er heuristikk: en CodeQL-workflow med annet navn, eller en codeql-fil som gjør
#                 noe annet, blir feilklassifisert. Filene listes, så grunnlaget er synlig.
#                                                                          (/repos/{r}/code-scanning/default-setup
#                                                                           + /repos/{r}/contents/.github/workflows)
#   dep-alerts    Dependabot alerts                                        (/repos/{r}/vulnerability-alerts: 204 = på, 404 = av)
#   sec-updates   Dependabot security updates, evt. pauset                 (/repos/{r}/automated-security-fixes)
#   dependabot-config  .github/dependabot.yml eller .yaml finnes; sier ikke at innholdet virker
#                                                                          (/repos/{r}/contents/.github/dependabot.y*ml)
#   secret-scan   secret scanning / push protection / validity checks      (security_and_analysis i /repos/{r})
#   secret-mer    generic patterns / AI-detected / delegert dismissal / delegert bypass med godkjennere (samme objekt)
#   pvr           private vulnerability reporting                          (/repos/{r}/private-vulnerability-reporting)
#   org-config    org-nivå security configuration knyttet til repoet       (/repos/{r}/code-security-configuration; 204 = ingen)
#   token         default GITHUB_TOKEN-rettigheter for workflows, og om Actions kan godkjenne PR-er (+approve/-approve)
#                                                                          (/repos/{r}/actions/permissions/workflow)
#   rulesets      aktive rulesets, alle sider                              (/repos/{r}/rulesets)
#
# Skriptet dekker ikke det som ikke er funnet i REST-API-et: Copilot Autofix, grouped security updates, malware
# alerts, extended metadata, automatic dependency submission, custom patterns og «prevent direct alert dismissals»
# for Dependabot og code scanning. Les dem i UI-et.
#
# Tilgang: alt utenom synlighet, filer, pvr og rulesets krever repo-tillatelsen «Administration» (lesing); det
# vanlige gh-lesetokenet mangler den og gir 403. Med et fine-grained token med Administration: read og Metadata:
# read leses alle kolonnene unntatt org-config, som svarer 403 også da; hvilken tillatelse den krever er ikke kjent.
# Private repoer krever i tillegg Contents: read for filene.
#
# Tokenet skal aldri stå på kommandolinja: shell-historikk, prosessliste og terminallogger ville lagret det.
# Scriptet henter det slik, i denne rekkefølgen:
#   1. GH_TOKEN finnes alt i miljøet (satt av en wrapper, ikke skrevet i terminalen).
#   2. TOKEN_KOMMANDO er satt til en kommando som skriver tokenet til stdout, f.eks. fra Keychain
#      (`security find-generic-password -s <navn> -w`) eller en age-fil. Kommandoen kjøres som betrodd shell-kode
#      med brukerens rettigheter og må ikke selv logge tokenet. Hver utvikler velger selv hvor tokenet ligger.
#   3. Ellers, når stdin er en terminal, limes tokenet inn skjult. Tomt svar betyr gh sin vanlige innlogging.
# UTEN_TOKEN=1 hopper over alt dette og bruker gh sin vanlige innlogging.
# Tokenet gis videre til gh som GH_TOKEN i miljøet til skriptets egne prosesser, ikke via argv, og skriptet
# skriver det ikke til stdout eller til fil. Miljøet arves også av jq, python3 og base64 som skriptet starter.
#
# Bruk:
#   ./script/sikkerhetsinnstillinger/sikkerhetsinnstillinger.sh                                   (oppdager repoene som status.sh)
#   REPOS="navikt/tiltakspenger-libs navikt/tiltakspenger-iac" ./script/sikkerhetsinnstillinger/sikkerhetsinnstillinger.sh
#
# Utskriften er en Markdown-tabell, klar til å limes inn i arbeidsboka eller en issue.

set -uo pipefail
set +x # xtrace ville skrevet tokenverdien til stderr ved tilordning

GH_ORG="${GH_ORG:-navikt}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

for tool in gh jq python3 base64; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Mangler '$tool' på PATH." >&2; exit 1; }
done

# Token uten å legge det på kommandolinja; se rekkefølgen i toppen av fila.
if [[ "${UTEN_TOKEN:-0}" == "1" ]]; then
    unset GH_TOKEN GITHUB_TOKEN
elif [[ -z "${GH_TOKEN:-}" ]]; then
    if [[ -n "${TOKEN_KOMMANDO:-}" ]]; then
        GH_TOKEN="$(bash -c "$TOKEN_KOMMANDO")" || { echo "TOKEN_KOMMANDO feilet." >&2; exit 1; }
        [[ -n "$GH_TOKEN" ]] || { echo "TOKEN_KOMMANDO ga tomt svar." >&2; exit 1; }
    elif [[ -t 0 ]]; then
        read -rs -p "Fine-grained token med Administration: read (tomt = gh sin innlogging): " GH_TOKEN || GH_TOKEN=""
        echo >&2
    fi
    if [[ -n "${GH_TOKEN:-}" ]]; then
        export GH_TOKEN
    else
        unset GH_TOKEN
    fi
fi

# Samme oppdagelse som status.sh: origin-remotene i rota og alle sub-repoene.
discover_repos() {
    {
        for d in "$ROOT" "$ROOT"/*/; do
            url="$(git -C "$d" remote get-url origin 2>/dev/null)" || continue
            echo "$url" | grep -oE "$GH_ORG/[A-Za-z0-9._-]+"
        done
    } | sed 's/\.git$//' | sort -u
}

if [[ -n "${REPOS:-}" ]]; then
    read -r -a repo_list <<< "$REPOS"
else
    mapfile -t repo_list < <(discover_repos)
fi

tmpdir="$(mktemp -d)" || { echo "Kunne ikke opprette temp-mappe." >&2; exit 1; }
trap 'rm -rf "$tmpdir"' EXIT
# Bakgrunnsjobber i et ikke-interaktivt skript ignorerer Ctrl+C. Jobbene får TERM og ventes inn før EXIT-trappen
# rydder; gh-prosesser jobbene alt har startet får fullføre kallet sitt.
trap 'kill $(jobs -p) 2>/dev/null; wait; exit 130' INT TERM

# api <sti> [gh api-flagg]: body på stdout og exit 0, ellers «HTTP <status>» (eller «feil» uten status) på stdout og
# exit 1. gh skriver f.eks. «gh: Not Found (HTTP 404)» på stderr; statusen skiller «av» fra «ingen tilgang».
# stderr holdes utenfor body-en, siden gh også kan skrive varsler der ved suksess. Et 204-svar gir tom body og exit 0.
api() {
    local sti="$1" ut feilfil status
    shift
    feilfil="$(mktemp "$tmpdir/gh-feil.XXXXXX")" || { printf 'feil'; return 1; }
    if ut="$(gh api "$sti" "$@" 2>"$feilfil")"; then
        rm -f "$feilfil"
        printf '%s' "$ut"
        return 0
    fi
    status="$(grep -oE '\(HTTP [0-9]+\)' "$feilfil" | grep -oE '[0-9]+' | head -1)"
    rm -f "$feilfil"
    if [[ -n "$status" ]]; then
        printf 'HTTP %s' "$status"
    else
        printf 'feil'
    fi
    return 1
}

# gyldig_json <body>: 0 når body er et JSON-objekt eller en JSON-liste. Et tomt eller ødelagt svar med exit 0 fra gh
# ville ellers gitt tomme celler eller «av» uten forklaring.
gyldig_json() { jq -e 'type == "object" or type == "array"' <<< "$1" >/dev/null 2>&1; }

# ukjent «HTTP 403» -> «?HTTP 403»
ukjent() { printf '?%s' "$1"; }

# Tekst fra API-et (ruleset- og konfigurasjonsnavn) går rett inn i TSV; tab og linjeskift må ut før det.
rens() { tr '\t\r\n' '   ' <<< "$1"; }

# jq-hjelpere som skiller på/av fra ukjent: null, manglende felt og andre verdier blir «?».
JQ_HJELPERE='
    def st(f): if f.status == "enabled" then "på" elif f.status == "disabled" then "av" else "?" end;
    def bool: if . == true then "på" elif . == false then "av" else "?" end;
'

# Én rad per repo, tab-separert. Kjøres i bakgrunnen per repo; rekkefølgen gjenopprettes etterpå.
hent_repo() {
    local repo="$1" navn="${1#*/}" repo_json feil
    local synlighet codeql dep sec dependabot_config secret secret_mer pvr org token rulesets

    if ! repo_json="$(api "/repos/$repo")"; then
        printf '%s\t%s\n' "$navn" "$(ukjent "$repo_json")"
        return
    fi
    if ! gyldig_json "$repo_json"; then
        printf '%s\t?ugyldig svar\n' "$navn"
        return
    fi
    if [[ "$(jq -r '.archived' <<< "$repo_json")" == "true" ]]; then
        printf '%s\tarkivert\n' "$navn"
        return
    fi
    synlighet="$(jq -r '.visibility // "?"' <<< "$repo_json")"

    # CodeQL: default setup og egne workflow-filer, hver for seg, så konflikten blir synlig.
    local default_state="" workflow_fil="" egen_skanning="nei" fil innhold_json innhold
    if feil="$(api "/repos/$repo/code-scanning/default-setup")" && gyldig_json "$feil"; then
        default_state="$(jq -r '.state // "?"' <<< "$feil")"
    else
        default_state="$(ukjent "$feil")"
    fi
    # En fil som bare har `workflow_call` er en delt mal (tiltakspenger-workflows) og kjører ikke i repoet selv;
    # den teller ikke som egen skanning. Innholdet leses per fil, base64 fra contents-API-et.
    if feil="$(api "/repos/$repo/contents/.github/workflows")" && gyldig_json "$feil"; then
        for fil in $(jq -r '.[].name | select(test("codeql"; "i"))' <<< "$feil"); do
            if ! innhold_json="$(api "/repos/$repo/contents/.github/workflows/$fil")"; then
                workflow_fil="${workflow_fil:+$workflow_fil,}$fil ($(ukjent "$innhold_json"))"
                continue
            fi
            if ! innhold="$(jq -er 'select(.encoding == "base64") | .content | select(type == "string" and length > 0)' <<< "$innhold_json" | base64 -d 2>/dev/null)"; then
                workflow_fil="${workflow_fil:+$workflow_fil,}$fil (?innhold)"
                continue
            fi
            # Triggere både som nøkler under `on:` og i kortformen `on: [push, pull_request]` / `on: push`.
            if grep -qE '^\s*(schedule|push|pull_request|pull_request_target|workflow_dispatch|merge_group):|^on:\s*\[?[^]]*\b(push|pull_request|schedule|workflow_dispatch)\b' <<< "$innhold"; then
                workflow_fil="${workflow_fil:+$workflow_fil,}$fil"
                egen_skanning="ja"
            elif grep -qE '^\s*workflow_call:' <<< "$innhold"; then
                workflow_fil="${workflow_fil:+$workflow_fil,}$fil (bare workflow_call)"
            else
                workflow_fil="${workflow_fil:+$workflow_fil,}$fil (ukjent trigger)"
            fi
        done
    elif [[ "$feil" != "HTTP 404" ]]; then
        workflow_fil="$(ukjent "$feil")"
    fi
    case "$default_state:$egen_skanning:$workflow_fil" in
        configured:ja:*)      codeql="begge ⚠ ($workflow_fil)" ;;
        configured:nei:)      codeql="default" ;;
        configured:nei:*)     codeql="default ($workflow_fil)" ;;
        not-configured:ja:*)  codeql="workflow ($workflow_fil)" ;;
        not-configured:nei:)  codeql="ingen" ;;
        not-configured:nei:*) codeql="ingen ($workflow_fil)" ;;
        *)                    codeql="$default_state / ${workflow_fil:-ingen fil}" ;;
    esac

    if feil="$(api "/repos/$repo/vulnerability-alerts")"; then
        dep="på"
    else
        [[ "$feil" == "HTTP 404" ]] && dep="av" || dep="$(ukjent "$feil")"
    fi

    if feil="$(api "/repos/$repo/automated-security-fixes")" && gyldig_json "$feil"; then
        sec="$(jq -r "$JQ_HJELPERE"'
            if .enabled == true then (if .paused == true then "pauset" elif .paused == false then "på" else "på (pause ?)" end)
            elif .enabled == false then "av" else "?" end' <<< "$feil")"
    else
        sec="$(ukjent "$feil")"
    fi

    # Version updates har ingen bryter; de finnes når fila finnes. Begge filnavnene GitHub godtar sjekkes.
    dependabot_config=""
    for fil in dependabot.yml dependabot.yaml; do
        if feil="$(api "/repos/$repo/contents/.github/$fil")"; then
            dependabot_config="${dependabot_config:+$dependabot_config,}$fil"
        elif [[ "$feil" != "HTTP 404" ]]; then
            dependabot_config="${dependabot_config:+$dependabot_config,}$fil $(ukjent "$feil")"
        fi
    done
    dependabot_config="${dependabot_config:-nei}"

    # security_and_analysis krever Administration; null betyr manglende tilgang, ikke av. Feltnavnene er fra
    # REST-dokumentasjonen for «Update a repository».
    secret="$(jq -r "$JQ_HJELPERE"'
        if .security_and_analysis == null then "?admin"
        else (.security_and_analysis | st(.secret_scanning) + "/" + st(.secret_scanning_push_protection) + "/" + st(.secret_scanning_validity_checks))
        end' <<< "$repo_json")"
    secret_mer="$(jq -r "$JQ_HJELPERE"'
        if .security_and_analysis == null then "?admin"
        else (.security_and_analysis |
            "generic " + st(.secret_scanning_non_provider_patterns) +
            " · ai " + st(.secret_scanning_ai_detection) +
            " · dismissal " + st(.secret_scanning_delegated_alert_dismissal) +
            " · bypass " + st(.secret_scanning_delegated_bypass) +
            (if (.secret_scanning_delegated_bypass_options.reviewers | length) > 0 then
                " (" + ([.secret_scanning_delegated_bypass_options.reviewers[] | (.reviewer_type // "?") + ":" + ((.reviewer_id // "?") | tostring)] | join(",")) + ")"
             else "" end))
        end' <<< "$repo_json")"

    if feil="$(api "/repos/$repo/private-vulnerability-reporting")" && gyldig_json "$feil"; then
        pvr="$(jq -r "$JQ_HJELPERE"'.enabled | bool' <<< "$feil")"
    else
        pvr="$(ukjent "$feil")"
    fi

    # 204 uten body når ingen konfigurasjon er knyttet til repoet; ellers et objekt med state og configuration.
    if feil="$(api "/repos/$repo/code-security-configuration")"; then
        if [[ -z "$feil" ]]; then
            org="ingen"
        elif gyldig_json "$feil"; then
            org="$(jq -r '(.configuration.name // "?") + " (" + (.state // .status // "?") + ")"' <<< "$feil")"
        else
            org="?ugyldig svar"
        fi
    else
        org="$(ukjent "$feil")"
    fi

    if feil="$(api "/repos/$repo/actions/permissions/workflow")" && gyldig_json "$feil"; then
        token="$(jq -r "$JQ_HJELPERE"'
            (.default_workflow_permissions // "?") + " " +
            (.can_approve_pull_request_reviews | if . == true then "+approve" elif . == false then "-approve" else "?approve" end)' <<< "$feil")"
    else
        token="$(ukjent "$feil")"
    fi

    # Alle sider, siden ett kall bare gir de første 30. Navnene kan selv inneholde komma («main, andre»).
    if feil="$(api "/repos/$repo/rulesets" --paginate --slurp)" && gyldig_json "$feil"; then
        rulesets="$(jq -r '[.[][] | select(.enforcement == "active") | .name] | if length == 0 then "ingen" else join(" · ") end' <<< "$feil")"
    else
        rulesets="$(ukjent "$feil")"
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$navn" "$synlighet" "$(rens "$codeql")" "$dep" "$sec" "$dependabot_config" "$secret" "$secret_mer" "$pvr" "$(rens "$org")" "$token" "$(rens "$rulesets")"
}

# Én bakgrunnsjobb per repo, radfil per jobb. En jobb som dør uten å skrive rad gir en synlig feilrad, ikke et hull.
i=0
for repo in "${repo_list[@]}"; do
    hent_repo "$repo" > "$tmpdir/$i.tsv" &
    i=$((i + 1))
done
wait
for ((j = 0; j < i; j++)); do
    [[ -s "$tmpdir/$j.tsv" ]] || printf '%s\t?ingen rad\n' "${repo_list[$j]#*/}" > "$tmpdir/$j.tsv"
done

{
    printf 'repo\tsynlighet\tcodeql\tdep-alerts\tsec-updates\tdependabot-config\tsecret-scan\tsecret-mer\tpvr\torg-config\ttoken\trulesets\n'
    for ((j = 0; j < i; j++)); do
        cat "$tmpdir/$j.tsv"
    done
} | python3 -c '
# Markdown-tabell med kolonnebredder etter innholdet. python3 framfor awk fordi awk på macOS teller bytes,
# så «å» og «⚠» ville forskjøvet kolonnene. Rader med færre felt (utilgjengelig repo) fylles ut med tomme
# celler, så tabellen forblir gyldig; «|» i verdier escapes.
import re, sys
rader = [[c.replace("|", "\\|") for c in linje.rstrip("\n").split("\t")] for linje in sys.stdin]
# Arkiverte repoer er ikke noe å rette; de nevnes under tabellen så det er synlig hvorfor de mangler.
arkiverte = [r[0] for r in rader if len(r) > 1 and r[1] == "arkivert"]
rader = [r for r in rader if not (len(r) > 1 and r[1] == "arkivert")]
antall = max(len(r) for r in rader)
rader = [r + [""] * (antall - len(r)) for r in rader]
bredde = [max(len(r[k]) for r in rader) for k in range(antall)]
for i, r in enumerate(rader):
    print("| " + " | ".join(c.ljust(bredde[k]) for k, c in enumerate(r)) + " |")
    if i == 0:
        print("|" + "|".join("-" * (b + 2) for b in bredde) + "|")
tekst = "\n".join("\t".join(r) for r in rader[1:])
forklaring = {
    "HTTP 403": "403: forespørselen ble avvist; tokenet mangler tillatelsen endepunktet krever (oftest Administration: read), eller GitHub bremser.",
    "HTTP 404": "404: ressursen finnes ikke, eller tokenet ser den ikke (private repoer).",
    "?admin": "?admin: security_and_analysis mangler i svaret; krever Administration: read på tokenet.",
    "?feil": "feil: gh svarte uten HTTP-status (nettverk eller innlogging); kjør på nytt.",
    "?ugyldig svar": "ugyldig svar: gh ga exit 0 uten gyldig JSON; kjør på nytt.",
    "?innhold": "innhold: fila kunne ikke dekodes fra contents-API-et.",
    "?ingen rad": "ingen rad: jobben for repoet døde uten å skrive resultat; kjør på nytt.",
}
noter = [melding for nokkel, melding in forklaring.items() if nokkel in tekst]
for status in sorted(set(re.findall(r"\?HTTP (\d+)", tekst))):
    if "HTTP " + status not in forklaring:
        noter.append("HTTP " + status + ": se GitHubs dokumentasjon for endepunktet.")
if arkiverte:
    noter.append("Arkivert og utelatt: " + ", ".join(arkiverte) + ".")
if noter:
    print()
    for n in noter:
        print("- " + n)
'
