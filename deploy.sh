#!/bin/bash

set -e

source env/bin/activate
pip install -r requirements.txt
./manage.py compilemessages -l fr -l en
./manage.py migrate
npm install
npm run build
./manage.py collectstatic --no-input
deactivate

cd bounce-service
npm install
cd ..

sudo systemctl restart django-consumers@$(basename $(pwd))
sudo systemctl restart django-bounce@$(basename $(pwd))
sudo systemctl restart uwsgi@$(basename $(pwd))
