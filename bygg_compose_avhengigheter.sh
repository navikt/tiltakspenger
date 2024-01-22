#!/usr/bin/env bash
cd tiltakspenger-vedtak
echo "Bygger komponent $PWD"
./gradlew clean build installDist
cd ../tiltakspenger-meldekort-api
echo "Bygger komponent $PWD"
./gradlew clean build installDist
cd ../tiltakspenger-vedtak-rivers
echo "Bygger komponent $PWD"
./gradlew clean build installDist
cd ../tiltakspenger-utbetaling
echo "Bygger komponent $PWD"
./gradlew clean build installDist
cd ../tiltakspenger-dokument
echo "Bygger komponent $PWD"
./gradlew clean build installDist
echo "du er flink :)"