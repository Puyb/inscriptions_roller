FROM python:3.8

RUN apt-get update && apt-get install -y \
    python-dev libpq-dev

WORKDIR /app/

RUN pip install setuptools==45
RUN pip install psycopg2 uwsgi

RUN mkdir -p /var/log/uwsgi /shared/static /shared/media

RUN ln -sf /dev/stdout /var/log/uwsgi/djangoapp.log \
	&& ln -sf /dev/stdout /var/log/uwsgi/emperor.log

VOLUME /app

EXPOSE 29000

CMD ./docker-start.sh
