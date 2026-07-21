"""factory_boy factories used to build valid model instances for tests and for
seeding the e2e environment (see management command `setup_e2e_data`).

Kept independent from `inscriptions/tests/` so both the test suite and the
e2e data-seeding management command can import from a single place.
"""
from datetime import date, timedelta
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from .models import Categorie, Equipe, Equipier, ExtraQuestion, ExtraQuestionChoice, Ville


class CourseFactory(DjangoModelFactory):
    class Meta:
        model = 'inscriptions.Course'

    nom = factory.Sequence(lambda n: 'Course %d' % n)
    uid = factory.Sequence(lambda n: 'course%d' % n)
    organisateur = 'Club Test'
    ville = 'Paris'
    date = factory.LazyFunction(lambda: date.today() + timedelta(days=60))
    url = 'http://example.com'
    url_reglement = 'http://example.com/reglement'
    email_contact = 'organisation@example.com'
    date_ouverture = factory.LazyFunction(lambda: date.today() - timedelta(days=1))
    date_fermeture = factory.LazyFunction(lambda: date.today() + timedelta(days=30))
    limite_participants = 700
    frais_paypal_inclus = False
    frais_stripe_inclus = False
    helloasso_sandbox = True
    ordre = 'Club Test'
    active = True


class CategorieFactory(DjangoModelFactory):
    class Meta:
        model = Categorie

    course = factory.SubFactory(CourseFactory)
    nom = factory.Sequence(lambda n: 'Categorie %d' % n)
    code = factory.Sequence(lambda n: 'CAT%d' % n)
    prices_base = [Decimal('40.00')]
    prices_equipier = [Decimal('10.00')]
    min_equipiers = 1
    max_equipiers = 1
    min_age = 18
    sexe = ''
    validation = 'function(data) { return true; }'
    numero_debut = 0
    numero_fin = 999


class VilleFactory(DjangoModelFactory):
    class Meta:
        model = Ville

    nom = 'paris'
    region = 'Ile-de-France'
    pays = 'FR'
    lat = Decimal('48.8566')
    lng = Decimal('2.3522')


class EquipeFactory(DjangoModelFactory):
    class Meta:
        model = Equipe

    course = factory.SubFactory(CourseFactory)
    categorie = factory.SubFactory(CategorieFactory, course=factory.SelfAttribute('..course'))
    nom = factory.Sequence(lambda n: 'Equipe %d' % n)
    club = ''
    gerant_nom = 'Dupont'
    gerant_prenom = 'Jean'
    gerant_ville = 'Paris'
    gerant_code_postal = '75000'
    gerant_pays = 'FR'
    gerant_email = factory.Sequence(lambda n: 'gerant%d@example.com' % n)
    gerant_telephone = '0102030405'
    nombre = 1
    prix = Decimal('40.00')


class EquipierFactory(DjangoModelFactory):
    class Meta:
        model = Equipier

    equipe = factory.SubFactory(EquipeFactory)
    numero = factory.Sequence(lambda n: n + 1)
    nom = 'Dupont'
    prenom = 'Jean'
    sexe = 'H'
    date_de_naissance = date(1990, 1, 1)
    justificatif = 'certificat'
    piece_jointe_valide = True


class ExtraQuestionFactory(DjangoModelFactory):
    class Meta:
        model = ExtraQuestion

    course = factory.SubFactory(CourseFactory)
    page = 'Equipe'
    type = 'text'
    label = 'Question'
    help_text = ''
    prices = []
    required = False


class ExtraQuestionChoiceFactory(DjangoModelFactory):
    class Meta:
        model = ExtraQuestionChoice

    question = factory.SubFactory(ExtraQuestionFactory)
    label = factory.Sequence(lambda n: 'Choix %d' % n)
    prices = []
    order = 0
