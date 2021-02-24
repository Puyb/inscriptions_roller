#!/bin/bash

pip install -r requirements.txt
if [ "$DEBUG" = "True" ]; then
    pip install -r requirements_dev.txt
fi
./manage.py migrate
uwsgi --socket 0.0.0.0:29000 \
               --protocol uwsgi \
               --processes 4 \
               --wsgi django.wsgi:application
# /usr/local/bin/uwsgi --emperor docker/uwsgi --gid www-data --logto /var/log/uwsgi/emperor.log
