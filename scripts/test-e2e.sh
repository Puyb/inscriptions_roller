#!/bin/bash
# Run the Playwright end-to-end suite against a real (throwaway) instance of
# the app: brings up `django-e2e` (migrates, seeds a fixed 'e2e' course,
# runs the dev server against a dedicated `enduroller_e2e` database), then
# runs the `e2e` container against it. Tears everything down afterwards.
set -euo pipefail
cd "$(dirname "$0")/.."

cleanup() {
    docker-compose --profile test down
}
trap cleanup EXIT

docker-compose --profile test up -d db redis
echo -n "Waiting for postgres..."
until docker-compose --profile test exec -T db pg_isready -U enduroller >/dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo " ready."

docker-compose --profile test up -d --build django-e2e
docker-compose --profile test build e2e

echo -n "Waiting for django-e2e (migrate/collectstatic/seed can take a bit)..."
for _ in $(seq 1 120); do
    if docker-compose --profile test logs django-e2e 2>&1 | grep -q "Starting development server"; then
        echo " ready."
        break
    fi
    echo -n "."
    sleep 1
done

docker-compose --profile test run --rm e2e pytest e2e -v "$@"
