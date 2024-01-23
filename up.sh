#!/usr/bin/env bash
# Script for å bygge og starte alle apper i docker-compose
# Bruk:
#   ./up.sh for å bare kjøre opp
#   ./up.sh -b for å bygge og kjøre opp
#   ./up.sh -p -b for å pulle, bygge og kjøre opp
#   ./up.sh -c -p -b for å pulle, clean-bygge og kjøre opp

bygg=false
git_pull=false
repoer=(
	"tiltakspenger-vedtak"
	"tiltakspenger-meldekort-api"
	"tiltakspenger-vedtak-rivers"
	"tiltakspenger-utbetaling"
	"tiltakspenger-dokument"
)
docker_cmd="docker compose up --build -d"
build_cmd="./gradlew build installDist"

# Sjekk om docker-compose finnes; bruk i så fall den
if command -v docker-compose &> /dev/null
then
    echo "Bruker docker-compose"
    docker_cmd="docker-compose up --build -d"
fi

while getopts bcp flag
do
    case "${flag}" in
        b) bygg=true;;
        p) git_pull=true;;
		c) build_cmd="./gradlew clean build installDist"
    esac
done

for repo in "${repoer[@]}"
do
	cdin="cd $repo"
		$cdin
		if [ "$git_pull" = true ] ; then
			echo -e "\033[32m*** Puller $repo ***\033[0m"
			git pull
			if [ $? -ne 0 ]; then 
				echo -e "\033[31mPull feilet på $repo\033[0m"
				exit 1
			fi 
		fi
		if [ "$bygg" = true ] ; then
			echo -e "\033[44m*** Bygger $repo ***\033[0m"
			$build_cmd
			if [ $? -ne 0 ]; then 
				echo -e "\033[31mBygg feilet på $repo\033[0m"
				exit 1
			fi 
		fi
		cd ..
done

$docker_cmd
