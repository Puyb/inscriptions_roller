#!/bin/bash

if [ "$1" == "" ] || [ "$2" == "" ]; then
    echo "$0 <database> <data.json>"
    exit 1
fi;

./manage.py syncdb
psql $1 < $(dirname $0)/truncate.sql 
./manage.py loaddata $2
echo "update inscriptions_categorie set numero_fin=399 where course_id=4 AND code like 'ID%';" | psql $1

