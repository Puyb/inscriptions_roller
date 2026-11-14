import os
from datetime import date, timedelta
from django.core.files.base import ContentFile
from decimal import Decimal

from django.core.management.base import BaseCommand

from django.contrib.auth.models import User

from inscriptions.geocoding import normaliser_nom
from inscriptions.factories import (
    CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory, ExtraQuestionFactory,
)
from inscriptions.models import (
    Accreditation, Challenge, ChallengeCategorie, CodePostal, Edition, Mail, Paiement, PaiementRepartition, TemplateMail,
)

COURSE_UID = 'e2e'
STATS_UID = 'e2estats'  # second accredited course, to compare in the stats page
NOGEO_UID = 'e2enogeo'  # public stats page of a course whose teams have no known city
STRIPE_UID = 'e2estripe'  # course with Stripe test keys (only seeded when E2E_STRIPE_* are set)
STRIPE_TEAMS = 8  # "Stripe 1".."Stripe 8", price 40, one per test
STRIPE_ENDPOINT_SECRET = 'whsec_e2e_local'  # webhooks are signed locally by the tests
OTHER_UID = 'e2eother'  # course the organizer has NO accreditation on
ADMIN_USERNAME = 'e2e-admin'
SUPER_USERNAME = 'e2e-super'
ADMIN_PASSWORD = 'e2e-password'
# Teams reserved for the backoffice payment tests: "Paiement 1".."Paiement 8",
# price 40 for odd numbers, 60 for even ones. Each test uses its own teams.
PAIEMENT_TEAMS = 8
DOCUMENT_TEAMS = 5  # "Document N" teams, pending document review


class Command(BaseCommand):
    """(Re)create a known-good 'e2e' course for the Playwright suite to run
    against. Idempotent: safe to run before every e2e run.

    Also seeds a few `CodePostal` rows (local geocoding reference, normally
    loaded by `import_codes_postaux`) so teams get a city on the stats pages.
    """
    help = "Seed a fixed 'e2e' course + categories for the Playwright suite."

    def handle(self, *args, **options):
        Challenge.objects.filter(uid__in=['e2echal', 'e2enewchal']).delete()
        Edition.objects.filter(uid__in=[COURSE_UID, 'e2enew', OTHER_UID, STATS_UID, STRIPE_UID, NOGEO_UID]).delete()  # e2enew: made by tests
        CodePostal.objects.filter(pays__in=['FR', 'BE']).delete()
        for pays, cp, nom, region, lat, lng in [
                ('FR', '75000', 'Paris', 'Île-de-France', '48.8566', '2.3522'),
                ('FR', '10000', 'Troyes', 'Grand Est', '48.2973', '4.0744'),
                ('FR', '58000', 'Nevers', 'Bourgogne-Franche-Comté', '46.9894', '3.1581'),
                ('BE', '1000', 'Bruxelles', 'Bruxelles-Capitale', '50.8466', '4.3517')]:
            CodePostal.objects.create(
                pays=pays, code_postal=cp, nom=nom, nom_normalise=normaliser_nom(nom), region=region,
                departement='', lat=Decimal(lat), lng=Decimal(lng))

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

        # Teams whose equipier has an uploaded document waiting for review
        for i in range(1, DOCUMENT_TEAMS + 1):
            equipe = EquipeFactory(course=course, categorie=categorie, nom='Document %d' % i)
            equipier = EquipierFactory(equipe=equipe, numero=1, piece_jointe_valide=None)
            equipier.piece_jointe.save('certificat%d.pdf' % i, ContentFile(b'%PDF-1.4\n%%EOF\n'))

        # A minor equipier (parental authorisation row must stay visible)
        equipe = EquipeFactory(course=course, categorie=categorie, nom='Mineur 1')
        EquipierFactory(equipe=equipe, numero=1, date_de_naissance=date(date.today().year - 12, 1, 1))

        # A mail template, and a team that answered an extra question
        TemplateMail.objects.create(
            course=course, nom='e2e', sujet='Bonjour {{ instance.nom }}',
            message='<p>Equipe numero {{ instance.numero }}</p>')
        question = ExtraQuestionFactory(course=course, label='Taille t-shirt', page='Equipe')
        EquipeFactory(
            course=course, categorie=categorie, nom='Extra 1',
            extra={'extra%d' % question.id: 'XL'})

        Mail.objects.create(
            course=course, equipe=course.equipe_set.get(nom='Extra 1'), emetteur='orga@example.com',
            destinataires=['gerant@example.com'], bcc=[], sujet='Sujet e2e', uid='e2e-mail',
            message='<p id="mail-body">Contenu <b>riche</b></p>')

        # An existing payment (20 EUR by cheque) on "Paiement 8", to edit
        paiement = Paiement.objects.create(type='chèque', montant=Decimal('20.00'))
        PaiementRepartition.objects.create(
            paiement=paiement, equipe=course.equipe_set.get(nom='Paiement 8'),
            montant=Decimal('20.00'))

        # A challenge with one category, for the superuser admin
        challenge = Challenge.objects.create(nom='Challenge E2E', uid='e2echal', mode='nord2017')
        ChallengeCategorie.objects.create(
            challenge=challenge, nom='Solo', code='SOLO', min_equipiers=1, max_equipiers=1,
            validation='function(data) { return true; }')

        # Backoffice organizer: staff + admin accreditation on the e2e course
        User.objects.filter(username=ADMIN_USERNAME).delete()
        user = User.objects.create_user(
            ADMIN_USERNAME, 'e2e-admin@example.com', ADMIN_PASSWORD)
        Accreditation.objects.create(user=user, course=course.course, role='admin')
        stats_course = CourseFactory(
            uid=STATS_UID, nom='Course Stats E2E',
            date=date.today() + timedelta(days=120),
            date_ouverture=date.today() - timedelta(days=5),
            date_fermeture=date.today() + timedelta(days=90),
            dates_augmentation=[date.today() + timedelta(days=d) for d in (20, 45, 70)])
        stats_categorie = CategorieFactory(course=stats_course, code='S', nom='S', numero_debut=1, numero_fin=99)
        EquipierFactory(equipe=EquipeFactory(course=stats_course, categorie=stats_categorie, nom='Stats 1',
                                             club='Club Paris'), numero=1)
        # geocoded teams (local CodePostal reference): France, Belgium, and an unknown city
        for nom, ville, cp, pays in [('Stats 2', 'Troyes', '10000', 'FR'), ('Stats 3', 'St Troyes Cedex', '10000', 'FR'),
                                     ('Stats 4', 'Bruxelles', '1000', 'BE'), ('Stats 5', '?', '?', 'FR')]:
            EquipierFactory(equipe=EquipeFactory(
                course=stats_course, categorie=stats_categorie, nom=nom, club='Club ' + ville,
                gerant_ville=ville, gerant_code_postal=cp, gerant_pays=pays), numero=1)
        nogeo = CourseFactory(uid=NOGEO_UID, nom='Course Sans Ville E2E', ville='Zzzzz',
                              date=date.today() + timedelta(days=60),
                              date_ouverture=date.today() - timedelta(days=5),
                              date_fermeture=date.today() + timedelta(days=30))
        nogeo_categorie = CategorieFactory(course=nogeo, code='N', nom='N', numero_debut=1, numero_fin=99)
        EquipierFactory(equipe=EquipeFactory(course=nogeo, categorie=nogeo_categorie, nom='Sans ville',
                                             gerant_ville='?', gerant_code_postal='?'), numero=1)
        Accreditation.objects.create(user=user, course=stats_course.course, role='admin')
        User.objects.filter(username=SUPER_USERNAME).delete()
        User.objects.create_superuser(SUPER_USERNAME, 'e2e-super@example.com', ADMIN_PASSWORD)
        CourseFactory(uid=OTHER_UID, nom='Course Autre E2E',
                      date=date.today() + timedelta(days=90),
                      date_ouverture=date.today() - timedelta(days=1),
                      date_fermeture=date.today() + timedelta(days=60))

        stripe_public = os.environ.get('E2E_STRIPE_PUBLIC')
        stripe_secret = os.environ.get('E2E_STRIPE_SECRET')
        if stripe_public and stripe_secret:
            stripe_course = CourseFactory(
                uid=STRIPE_UID, nom='Course Stripe E2E',
                date=date.today() + timedelta(days=90),
                date_ouverture=date.today() - timedelta(days=1),
                date_fermeture=date.today() + timedelta(days=60),
                stripe_public=stripe_public, stripe_secret=stripe_secret,
                stripe_endpoint_secret=STRIPE_ENDPOINT_SECRET)
            stripe_categorie = CategorieFactory(
                course=stripe_course, code='SOLO', nom='Solo', numero_debut=1, numero_fin=99,
                prices_base=[Decimal('40.00')], prices_equipier=[])
            for i in range(1, STRIPE_TEAMS + 1):
                EquipeFactory(course=stripe_course, categorie=stripe_categorie,
                              nom='Stripe %d' % i, numero=i, password='e2e-pass', prix=Decimal('40.00'))
            Accreditation.objects.create(user=user, course=stripe_course.course, role='admin')

        self.stdout.write(self.style.SUCCESS('e2e course ready: /%s/' % COURSE_UID))
