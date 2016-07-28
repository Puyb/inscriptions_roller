#!/bin/bash

set -e

source env/bin/activate
pip install -r requirements.txt
./manage.py compilemessages
./manage.py migrate
npm install
npm run build
./manage.py collectstatic
deactivate

sudo service uwsgi restart
