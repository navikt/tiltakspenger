#!/usr/bin/env bash
docker_cmd="docker compose down"
if command -v docker-compose &> /dev/null
then
    echo "Bruker docker-compose"
    docker_cmd="docker-compose down"
fi
$docker_cmd
docker ps -aq | xargs docker stop | xargs docker rm
docker network ls | grep tiltakspenger | sed 's/ .*//' | xargs docker network rm