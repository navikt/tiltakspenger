#!/usr/bin/env bash
# Script for å stoppe alle apper i docker-compose
# Bruk:
#   ./down.sh for ta ned kjørende compose

docker_cmd="docker compose -f docker-compose-soknad.yml down"

# Sjekk om docker-compose finnes; bruk i så fall den
if command -v docker-compose &> /dev/null
then
    echo "Bruker docker-compose"
    docker_cmd="docker-compose -f docker-compose-soknad.yml down"
fi

$docker_cmd
