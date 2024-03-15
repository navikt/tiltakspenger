#!/usr/bin/env bash
# Script for å stoppe alle apper i docker-compose
# Bruk:
#   ./down.sh for ta ned kjørende compose med default-profil (mockpdf)
#   ./down.sh -f for å ta ned kjørende compose med pdfgen (livepdf)

livepdf=false

while getopts f flag
do
    case "${flag}" in
		f) livepdf=true;;
    esac
done

if $livepdf; then
	echo -e "\033[31m*** Bruker LIVE pdfgen! ***\033[0m"
	profiles="livepdf"
else
	echo -e "\033[36m*** Bruker MOCK pdfgen! ***\033[0m"
	profiles="mockpdf"
fi

docker_cmd="docker compose --profile $profiles down"

# Sjekk om docker-compose finnes; bruk i så fall den
if command -v docker-compose &> /dev/null
then
    echo "Bruker docker-compose"
    docker_cmd="docker-compose --profile $profiles down"
fi

$docker_cmd