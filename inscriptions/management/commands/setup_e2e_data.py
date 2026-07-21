from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from inscriptions.factories import CategorieFactory, CourseFactory
from inscriptions.models import Course, Ville

COURSE_UID = 'e2e'


class Command(BaseCommand):
    """(Re)create a known-good 'e2e' course for the Playwright suite to run
    against. Idempotent: safe to run before every e2e run.

    Also seeds a `Ville` matching the city the e2e tests type into the
    registration form ("Paris"), so `Equipe.save()` -> `lookup_ville()`
    hits the DB cache instead of calling the real MapQuest API.
    """
    help = "Seed a fixed 'e2e' course + categories for the Playwright suite."

    def handle(self, *args, **options):
        Course.objects.filter(uid=COURSE_UID).delete()
        Ville.objects.get_or_create(nom='paris', defaults=dict(
            region='Ile-de-France', pays='FR', lat=Decimal('48.8566'), lng=Decimal('2.3522'),
        ))

        course = CourseFactory(
            uid=COURSE_UID,
            nom='Course E2E',
            date=date.today() + timedelta(days=90),
            date_ouverture=date.today() - timedelta(days=1),
            date_fermeture=date.today() + timedelta(days=60),
            limite_participants=700,
            active=True,
        )
        CategorieFactory(
            course=course, code='SOLO', nom='Solo', min_equipiers=1, max_equipiers=1,
            min_age=15, sexe='', numero_debut=100, numero_fin=199,
            prices_base=[Decimal('30.00')], prices_equipier=[],
            validation='function(data) { return true; }',
        )
        CategorieFactory(
            course=course, code='DUO', nom='Duo', min_equipiers=2, max_equipiers=2,
            min_age=15, sexe='', numero_debut=200, numero_fin=299,
            prices_base=[Decimal('40.00')], prices_equipier=[Decimal('10.00')],
            validation='function(data) { return true; }',
        )
        CategorieFactory(
            course=course, code='TRIO', nom='Trio a cinq', min_equipiers=3, max_equipiers=5,
            min_age=12, sexe='', numero_debut=300, numero_fin=399,
            prices_base=[Decimal('60.00')], prices_equipier=[Decimal('15.00')],
            validation='function(data) { return true; }',
        )

        self.stdout.write(self.style.SUCCESS('e2e course ready: /%s/' % COURSE_UID))
