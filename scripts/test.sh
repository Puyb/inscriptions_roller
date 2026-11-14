#!/bin/bash
# Run the unit/functional/integration test suite (Django test runner) inside
# docker-compose, against real PostgreSQL + Redis. Independent of whatever
# Python/Postgres/Redis is (or isn't) installed on the host.
#
# Usage:
#   scripts/test.sh                                  # run everything
#   scripts/test.sh inscriptions.tests.test_pricing   # run a subset
set -euo pipefail
cd "$(dirname "$0")/.."

docker-compose --profile test up -d db redis
echo -n "Waiting for postgres..."
until docker-compose --profile test exec -T db pg_isready -U enduroller >/dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo " ready."

# PYTHONWARNINGS est transmis au conteneur, ex. pour promouvoir les
# DeprecationWarning en erreurs :
#   PYTHONWARNINGS=error::DeprecationWarning scripts/test.sh
WARN_ENV=()
if [ -n "${PYTHONWARNINGS:-}" ]; then
    WARN_ENV=(-e "PYTHONWARNINGS=$PYTHONWARNINGS")
fi

# Migrations manquantes (changement de type de champ, etc.)
docker-compose --profile test run --rm test ./manage.py ensure_database
docker-compose --profile test run --rm "${WARN_ENV[@]}" test ./manage.py makemigrations --check --dry-run

docker-compose --profile test run --rm "${WARN_ENV[@]}" test ./manage.py test "${@:-inscriptions}"
