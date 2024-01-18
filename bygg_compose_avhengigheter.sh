#!/usr/bin/env bash
cd tiltakspenger-vedtak
ECHO "Bygger komponent $PWD"
./gradlew clean build installDist
cd ../tiltakspenger-meldekort-api
ECHO "Bygger komponent $PWD"
./gradlew clean build installDist
cd ../tiltakspenger-vedtak-rivers
ECHO "Bygger komponent $PWD"
./gradlew clean build installDist
cd ../tiltakspenger-utbetaling
ECHO "Bygger komponent $PWD"
./gradlew clean build installDist
ECHO "du er flink :)"