# Documentation organisateurs : build mkdocs (stage separe, mkdocs-material demande python >= 3.8)
FROM python:3.12-slim AS docs
WORKDIR /build
COPY requirements_docs.txt .
RUN pip install --no-cache-dir -r requirements_docs.txt
COPY mkdocs.yml .
COPY docs/wiki docs/wiki
RUN mkdocs build --strict -d /site

FROM python:3.9

ARG DEBUG

RUN apt-get update && apt-get install -y \
    libpq-dev

WORKDIR /app/

RUN pip install psycopg2==2.9.9 uwsgi

RUN mkdir -p /var/log/uwsgi /shared/static /shared/media

RUN ln -sf /dev/stdout /var/log/uwsgi/djangoapp.log \
	&& ln -sf /dev/stdout /var/log/uwsgi/emperor.log

# servi par uwsgi sous /documentation (hors de /app, qui est monte en volume)
COPY --from=docs /site /srv/documentation

COPY requirements.txt /app/
COPY requirements_dev.txt /app/

RUN pip install -r requirements.txt && if [ "$DEBUG" = "True" ]; then pip install -r requirements_dev.txt; fi

VOLUME /app

EXPOSE 29000

CMD ./docker-start.sh
