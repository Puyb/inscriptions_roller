# Inscriptions Roller

Registration site for 6h roller races by team

## Getting Started with docker

Install docker and docker-compose

```
npm install
npm run build
docker-compose up
docker-compose exec django ./manage.py loaddata sites
docker-compose exec django ./manage.py createsuperuser
```
connect to http://localhost:8000

## Getting Started with virtualenv

Make sure you are using a virtual environment of some sort (e.g. `virtualenv` or
`pyenv`).

```
pip install -r requirements.txt
npm install
npm run build
./manage.py migrate
./manage.py loaddata sites
./manage.py createsuperuser
./manage.py runserver
```
connect to http://localhost:8000
