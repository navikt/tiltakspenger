#!/usr/bin/env bash
# Script for å bygge og starte alle apper i docker-compose
# Bruk:
#   ./up.sh for å bare kjøre opp
#   ./up.sh -b for å bygge og kjøre opp
#   ./up.sh -p -b for å pulle, bygge og kjøre opp
#   ./up.sh -c -p -b for å pulle, clean-bygge og kjøre opp
#   ./up.sh -f for å kjøre opp med tiltakspenger-soknad-api

bygg=false
git_pull=false
run_api=false
repoer=(
	"tiltakspenger-soknad-api"
	"tiltakspenger-soknad-mock-api"
)
build_cmd="./gradlew build installDist -x test -x spotlessCheck -x spotlessApply"

hjelpetekst="# Bruk: \
\n \
\n./up.sh for å bare kjøre opp \
\n-b for å bygge og kjøre opp \
\n-p -b for å pulle, bygge og kjøre opp \
\n-c -p -b for å pulle, clean-bygge og kjøre opp \
\n-f for å kjøre opp med tiltakspenger-soknad-api \
\n \
\n *** \
\n"

hjelp() {
  printf "$hjelpetekst"
}

while getopts bcpfh flag
do
    case "${flag}" in
        b) bygg=true;;
        p) git_pull=true;;
		c) build_cmd="./gradlew clean build installDist -x test -x spotlessCheck -x spotlessApply";;
		f) run_api=true;;
		h) hjelp
		   exit 1 ;;
    esac
done

if $run_api; then
	echo -e "\033[31m*** Kjører opp med tiltakspenger-soknad-api! ***\033[0m"
	profiles="--profile api"
else
	profiles=""
fi

docker_cmd="docker compose $profiles -f docker-compose-soknad.yml up --build -d"

# Sjekk om docker-compose finnes; bruk i så fall den
if command -v docker-compose &> /dev/null
then
    echo "Bruker docker-compose"
    docker_cmd="docker-compose $profiles -f docker-compose-soknad.yml up --build -d"
fi

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
