FROM python:3.7

ARG DEBUG

RUN apt-get update && apt-get install -y \
    libpq-dev

WORKDIR /app/

RUN pip install psycopg2==2.8.6 uwsgi

RUN mkdir -p /var/log/uwsgi /shared/static /shared/media

RUN ln -sf /dev/stdout /var/log/uwsgi/djangoapp.log \
	&& ln -sf /dev/stdout /var/log/uwsgi/emperor.log

COPY requirements.txt /app/
COPY requirements_dev.txt /app/

RUN pip install -r requirements.txt && [ "$DEBUG" = "True" ] && pip install -r requirements_dev.txt || true

VOLUME /app

EXPOSE 29000

CMD ./docker-start.sh
