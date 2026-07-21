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

docker-compose --profile test run --rm test ./manage.py test "${@:-inscriptions}"
