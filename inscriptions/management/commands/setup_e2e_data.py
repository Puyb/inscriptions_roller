from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from django.contrib.auth.models import User

from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory
from inscriptions.models import Accreditation, Course, Paiement, PaiementRepartition, Ville

COURSE_UID = 'e2e'
ADMIN_USERNAME = 'e2e-admin'
ADMIN_PASSWORD = 'e2e-password'
# Teams reserved for the backoffice payment tests: "Paiement 1".."Paiement 8",
# price 40 for odd numbers, 60 for even ones. Each test uses its own teams.
PAIEMENT_TEAMS = 8


class Command(BaseCommand):
    """(Re)create a known-good 'e2e' course for the Playwright suite to run
    against. Idempotent: safe to run before every e2e run.

    Also seeds a `Ville` matching the city the e2e tests type into the
    registration form ("Paris"), so `Equipe.save()` -> `lookup_ville()`
    hits the DB cache instead of calling the real MapQuest API.
    """
    help = "Seed a fixed 'e2e' course + categories for the Playwright suite."

    def handle(self, *args, **options):
        Course.objects.filter(uid__in=[COURSE_UID, 'e2enew']).delete()  # e2enew: made by tests
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
            dates_augmentation=[date.today() + timedelta(days=30)],
        )
        CategorieFactory(
            course=course, code='SOLO', nom='Solo', min_equipiers=1, max_equipiers=1,
            min_age=15, sexe='', numero_debut=100, numero_fin=199,
            prices_base=[Decimal('30.00'), Decimal('35.00')], prices_equipier=[],
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

        categorie = course.categories.get(code='SOLO')
        for i in range(1, PAIEMENT_TEAMS + 1):
            EquipeFactory(
                course=course, categorie=categorie, nom='Paiement %d' % i,
                prix=Decimal('40.00') if i % 2 else Decimal('60.00'),
            )

        # An existing payment (20 EUR by cheque) on "Paiement 8", to edit
        paiement = Paiement.objects.create(type='chèque', montant=Decimal('20.00'))
        PaiementRepartition.objects.create(
            paiement=paiement, equipe=course.equipe_set.get(nom='Paiement 8'),
            montant=Decimal('20.00'))

        # Backoffice organizer: staff + admin accreditation on the e2e course
        User.objects.filter(username=ADMIN_USERNAME).delete()
        user = User.objects.create_user(
            ADMIN_USERNAME, 'e2e-admin@example.com', ADMIN_PASSWORD)
        Accreditation.objects.create(user=user, course=course, role='admin')

        self.stdout.write(self.style.SUCCESS('e2e course ready: /%s/' % COURSE_UID))
