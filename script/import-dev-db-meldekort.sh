#!/usr/bin/env bash
#
# import-dev-db-meldekort.sh — importerer dev-databasen til
# tiltakspenger-meldekort-api ned i den lokale docker-compose-databasen
# (port 5435).
#
# Bruk:
#   ./script/import-dev-db-meldekort.sh <GCP-brukernavn>
#
# Se import-dev-db.sh for miljøvariabler og detaljer.
#
set -uo pipefail

exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/import-dev-db.sh" meldekort "$@"
