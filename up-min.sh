#!/usr/bin/env bash
# Script for å starte et minimalt docker-compose-oppsett:
#   - postgresSaksbehandling  (port 5433)
#   - postgresMeldekort       (port 5435)
#   - pdfgen-service          (port 8081)
#   - pdfgenrs-service        (port 8084)
#   - wiremock                (port 8091)
#
# Nyttig når du kjører saksbehandling-api og meldekort-api fra IDE-en og bare
# trenger databasene og de eksterne avhengighetene. Bruk ./up.sh hvis du vil ha
# hele oppsettet (inkludert appene, authserver, texas og wonderwall).
#
# Bruk:
#   ./up-min.sh      for å bare kjøre opp
#   ./up-min.sh -b   for å bygge imagene på nytt og kjøre opp
#   ./up-min.sh -h   for hjelp

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

tjenester=(
	"postgresSaksbehandling"
	"postgresMeldekort"
	"pdfgen-service"
	"pdfgenrs-service"
	"wiremock"
)

bygg=false

hjelp() {
	printf "# Bruk: \
\n \
\n./up-min.sh for å bare kjøre opp \
\n-b for å bygge imagene på nytt og kjøre opp \
\n \
\nStarter kun: %s \
\n \
\nTa ned igjen med ./down.sh \
\n *** \
\n" "${tjenester[*]}"
}

while getopts bh flag; do
	case "${flag}" in
	b) bygg=true ;;
	h)
		hjelp
		exit 1
		;;
	*)
		hjelp
		exit 1
		;;
	esac
done

docker_cmd=(docker compose)

# Sjekk om docker-compose finnes; bruk i så fall den
if command -v docker-compose &>/dev/null; then
	echo "Bruker docker-compose"
	docker_cmd=(docker-compose)
fi

opp=(up -d)
if [ "$bygg" = true ]; then
	echo -e "\033[44m*** Bygger imagene på nytt ***\033[0m"
	opp+=(--build)
fi

echo -e "\033[36m*** Starter: ${tjenester[*]} ***\033[0m"
"${docker_cmd[@]}" "${opp[@]}" "${tjenester[@]}"
