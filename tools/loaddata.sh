#!/bin/bash

dropdb inscription_roller2
createdb inscription_roller2
./manage.py syncdb
psql inscription_roller2 < truncate.sql 
./manage.py loaddata data.json 
echo "update inscriptions_categorie set numero_fin=399 where course_id=4 AND code like 'ID%';" | psql inscription_roller2

