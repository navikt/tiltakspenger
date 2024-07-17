#!/usr/bin/env bash
# Script for å stoppe alle apper i docker-compose
# Bruk:
#   ./down.sh for ta ned kjørende compose
#   ./down.sh -f for å ta ned kjørende compose med tiltakspenger-soknad-api

stop_api=false

while getopts f flag
do
    case "${flag}" in
		f) stop_api=true;;
    esac
done

if $stop_api; then
	echo -e "\033[31m*** Stopper tiltakspenger-soknad-api! ***\033[0m"
	profile="--profile api"
else
	profile=""
fi

docker_cmd="docker compose $profile -f docker-compose-soknad.yml down"

# Sjekk om docker-compose finnes; bruk i så fall den
if command -v docker-compose &> /dev/null
then
    echo "Bruker docker-compose"
    docker_cmd="docker-compose $profile -f docker-compose-soknad.yml down"
fi

$docker_cmd
