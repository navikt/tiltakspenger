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
	"tiltakspenger-saksbehandling-api"
)
build_cmd="./gradlew build installDist -x test -x gitHooks -x spotlessCheck -x spotlessApply"

hjelpetekst="# Bruk: \
\n \
\n./up.sh for å bare kjøre opp \
\n-b for å bygge og kjøre opp \
\n-p -b for å pulle, bygge og kjøre opp \
\n-c -p -b for å pulle, clean-bygge og kjøre opp \
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
        c) build_cmd="./gradlew clean build installDist -x test -x gitHooks -x spotlessCheck -x spotlessApply";;
        h) hjelp
		   exit 1 ;;
    esac
done

docker_cmd="docker compose up --build -d"

# Sjekk om docker-compose finnes; bruk i så fall den
if command -v docker-compose &> /dev/null
then
    echo "Bruker docker-compose"
    docker_cmd="docker-compose up --build -d"
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
