# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Enduroller: a Django site for managing registrations ("inscriptions") for team-based endurance roller-skating races. Single Django app named `inscriptions` doubling as the project package (settings/urls/wsgi/asgi live inside `inscriptions/`, not in a separate project dir). French is the primary language of the domain model (field names, admin labels) and `fr` is the default `LANGUAGE_CODE`; `en` is also supported via `inscriptions/locale`.

Two audiences share one codebase:
- **Public site** (`views.py`, templates outside `templates/admin`): list races, register a team, pay, view participant lists/results, edit an existing registration.
- **Organizer backoffice** (`admin_course.py`, mounted at `/course/`): a heavily customized Django admin scoped to a single race, for validating registrations, entering payments, managing categories/results.
- There's also the superuser-only default Django admin (`admin_main.py`, mounted at `/admin/`) for cross-race/global objects (courses, challenges, logs).

## Commands

### Setup / run (virtualenv)
```
pip install -r requirements.txt          # add requirements_dev.txt too for debug_toolbar/django-extensions
npm install && npm run build             # builds static/dist via webpack (static/webpack.config.js)
./manage.py migrate
./manage.py loaddata sites
./manage.py createsuperuser
./manage.py runserver
```

### Setup / run (docker)
```
docker-compose up
docker-compose exec django ./manage.py loaddata sites
docker-compose exec django ./manage.py createsuperuser
```
`docker-compose.yml` hardcodes dev credentials/env vars for the `django`, `bounce`, `db` (postgres) and `redis` services. Local overrides go in `docker-compose.override.yml` (see `.dist` template).

### Tests
Tests always run through docker-compose (real PostgreSQL + Redis — some model logic, e.g. `Challenge` fuzzy-matching, only works on Postgres, see Architecture notes below), never on the host directly:
```
scripts/test.sh                                            # unit/functional/integration suite (inscriptions/tests/)
scripts/test.sh inscriptions.tests.test_pricing             # a single test module/class/method
scripts/test-e2e.sh                                          # Playwright e2e suite (e2e/), brings its own throwaway app+db up and tears it down after
```
Both scripts are thin wrappers around `docker-compose --profile test ...` (services `test`, `django-e2e`, `e2e` — gated behind the `test` compose profile so they never start on a plain `docker-compose up`). Test data is built with `inscriptions/factories.py` (factory_boy), not fixtures — the old `fixtures/course1.json` was removed after it silently bit-rotted out of sync with the model schema (a schema change stops `manage.py test` cold; a factory just fails loudly at the specific field that changed). The e2e stack seeds its own fixed `'e2e'` course via the `setup_e2e_data` management command.

Lint config is in `tox.ini` ([flake8] section) — max-line-length 100, complexity 10, E265/E501 ignored. There's no flake8/tox invocation wired up beyond that config; run `flake8` manually if needed.

### Frontend assets
```
npm run build     # one-off production build (webpack -p)
npm run watch     # rebuild on change
```

### Background workers
The app sends email through a Django Channels worker, not synchronously in the request:
```
./manage.py runworker mail       # consumes the "mail" channel (inscriptions/consumers.py, routing.py)
```
`docker-start.sh` runs this in a loop alongside the web process. `start-consumers.sh` / `start-bounce.sh` are the equivalent entry points used by systemd units in `deploy.sh` (`django-consumers@`, `django-bounce@`, `uwsgi@`).

The `bounce-service/` directory is a separate Node service (IMAP + `bounce-handler` + `knex`/Postgres) that reads bounce notifications from the mailbox and writes them back to the same database (`Mail` model). It's deployed and run independently of the Django app.

### Settings selection
`DJANGO_SETTINGS_MODULE=inscriptions.settings` → `inscriptions/settings/__init__.py` loads `default.py`, then either `LOCAL_SETTINGS` env var (dotted module, e.g. `.docker`) or falls back to importing `.local` (copy `local.py.example` → `local.py` for a plain virtualenv setup). Env-driven settings (DB, email, Turnstile captcha keys, Mapquest key, etc.) live in `settings/docker.py`.

## Architecture notes

- **Data model** (`inscriptions/models.py`, ~1500 lines) centers on `Course` (a single race event) → `Categorie`, `Equipe` (a registered team) → `Equipier` (team member), `Paiement`/`PaiementRepartition` (payments, possibly split across teams/methods), `ExtraQuestion`/`ExtraQuestionChoice` (per-race custom signup questions), `Accreditation` (per-user, per-course backoffice roles), `TemplateMail`/`Mail` (outgoing email templates + sent-mail log with open tracking), `Challenge`/`ChallengeCategorie`/`ParticipationChallenge`/`EquipeChallenge`/`ParticipationEquipier` (a multi-race ranking computed across several `Course`s), `LiveSnapshot`/`LiveResult`/`Tour` (live race timing/results).
- **URL scoping by `course_uid`**: almost every public URL is prefixed with `<str:course_uid>` (`inscriptions/urls.py`); views look up the `Course` by its `uid` slug per request rather than assuming a single global race.
- **Two independent `AdminSite` instances**, not one: `admin_main.site` (plain `django.contrib.admin.site`, mounted at `/admin/`, superuser-only) and `admin_course.site` (`CourseAdminSite`, mounted at `/course/`). The organizer picks a race first — `admin.course_setter` (`inscriptions/admin.py`) sets a `course_uid`/`course_id` cookie — and `CourseAdminSite`/`CourseFilteredObjectAdmin` (`admin_course.py`) then filter every queryset to that cookie's course and enforce access through `Accreditation` (unless `request.user.is_superuser`). Don't assume Django's normal per-model permission system alone controls what an organizer can see; check `getCourse()`/`CourseFilteredObjectAdmin` for the course-scoping layer on top of it.
- **Payments**: multiple methods are integrated directly in `views.py` — Paypal-style IPN (`ipn`), Stripe (`stripe_webhook`, `intent_paiement`, `get_intent`), HelloAsso (`helloasso_webhook`, `get_helloasso_token`). Payment amounts can be split across teams via `PaiementRepartition`.
- **Email is always async**: code should send mail by creating a `Mail`/dispatching to the `mail` channel (see `utils.send_mail`, `consumers.MailConsumer`), not by calling Django's `send_mail`/`EmailMessage` directly in a request. `middleware.tracking_middleware` marks a `Mail` as read via a `message_id` query param appended to links/the tracking pixel injected by `MailConsumer`.
- **New-user permission bootstrapping**: `receivers.py` (wired via `AppConfig.ready` in `apps.py`) auto-grants a fixed set of course-management permissions to every new `User` on `post_save` — if you add a new model organizers should manage, add its permissions there too.
- **Challenges** are the one cross-course concept: a `Challenge` aggregates results from several `Course`s via `ChallengeCategorie`, recomputed by `Challenge.compute_challenge()` (triggered from the `admin_main.ChallengeAdmin` actions).
- Custom DB functions: `functions.py`'s `DayOfWeek`/`Hour` have both `as_sqlite`/`as_postgresql` implementations. `models.py`'s `Levenshtein`/`Unaccent`/`RegexpReplace`/`CompareNames` (used for the `Challenge` fuzzy name/participant matching) do **not** — they only work against PostgreSQL with the `unaccent`/`fuzzystrmatch` extensions enabled (see migrations `0022_unaccent`/`0023_fuzzystrmatch`), which is why tests always run through docker-compose against real Postgres rather than SQLite.
- `tools/` has raw SQL helpers (`recreate_sequences.sql`, `truncate.sql`) and `loaddata.sh` for working with production-like data dumps.
- **Tests** (`inscriptions/tests/`, one module per concern: `test_pricing.py`, `test_dossier.py`, `test_numbering.py`, `test_paiements.py`, `test_registration.py`, `test_payment_webhooks.py`, `test_challenges.py`) build data with `inscriptions/factories.py`, not fixtures. `inscriptions/tests/base.py`'s `BaseTestCase` patches `models.lookup_ville` (an unconditional MapQuest HTTP call inside `Equipe.save()`) and redirects `MEDIA_ROOT` to a temp dir — inherit from it instead of `django.test.TestCase` whenever a test creates an `Equipe`/uploads a file. The e2e suite (`e2e/`, Playwright via `pytest-playwright`) drives the actual multi-page JS registration wizard (`inscriptions/static/form.js`) — the one place category-eligibility logic lives client-side only (a per-category JS snippet, `Categorie.validation`, evaluated in the browser; there's no server-side equivalent by design, see `views.form()`), so it's the only test layer that can exercise it.
