import psycopg2
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create the configured 'default' database if it doesn't exist yet.

    Only useful for the e2e docker-compose setup: `manage.py test` creates
    its own throwaway `test_<name>` database regardless of whether `<name>`
    exists, but the e2e stack runs a real `runserver` against a persistent
    database that has to exist upfront.
    """
    help = "Create the configured database if it does not already exist."

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        conn = psycopg2.connect(dbname='postgres', user=db['USER'], password=db['PASSWORD'], host=db['HOST'])
        conn.autocommit = True
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', [db['NAME']])
                if cursor.fetchone():
                    self.stdout.write('Database %s already exists' % db['NAME'])
                    return
                cursor.execute('CREATE DATABASE "%s"' % db['NAME'])
                self.stdout.write(self.style.SUCCESS('Created database %s' % db['NAME']))
        finally:
            conn.close()
