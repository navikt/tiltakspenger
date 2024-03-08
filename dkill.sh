#!/usr/bin/env bash
docker ps -aq | xargs docker stop | xargs docker rm
docker network ls | grep tiltakspenger | sed 's/ .*//' | xargs docker network rm