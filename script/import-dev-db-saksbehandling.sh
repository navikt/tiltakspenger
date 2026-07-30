#!/usr/bin/env bash
#
# import-dev-db-saksbehandling.sh — importerer dev-databasen til
# tiltakspenger-saksbehandling-api ned i den lokale docker-compose-databasen
# (port 5433).
#
# Bruk:
#   ./script/import-dev-db-saksbehandling.sh <GCP-brukernavn>
#
# Se import-dev-db.sh for miljøvariabler og detaljer.
#
set -uo pipefail

exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/import-dev-db.sh" saksbehandling "$@"
