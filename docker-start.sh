#!/bin/bash
set -e

pip install -r requirements.txt
if [ "$DEBUG" = "True" ]; then
    pip install -r requirements_dev.txt
fi
./manage.py migrate

bash -c 'while true; do ./manage.py runworker mail; done' &
#bash -c 'while true; do ./start-bounce.sh; done' &

uwsgi --socket 0.0.0.0:29000 \
      --protocol uwsgi \
      --enable-threads \
      --processes 4 \
      --wsgi inscriptions.wsgi:application
# /usr/local/bin/uwsgi --emperor docker/uwsgi --gid www-data --logto /var/log/uwsgi/emperor.log
