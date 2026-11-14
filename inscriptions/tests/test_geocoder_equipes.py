import io
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError

from inscriptions.factories import CourseFactory, EquipeFactory
from inscriptions.models import CodePostal, Equipe, Ville
from inscriptions.tests.base import BaseTestCase


class GeocoderEquipesTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.c1 = CourseFactory(uid='geo1')
        self.c2 = CourseFactory(uid='geo2')
        # equipes creees AVANT le referentiel : pas de ville
        self.paris = EquipeFactory(course=self.c1, gerant_ville='Paris', gerant_code_postal='75015')
        self.paris2 = EquipeFactory(course=self.c1, gerant_ville='paris', gerant_code_postal='75015')
        self.ailleurs = EquipeFactory(course=self.c2, gerant_ville='Nulle part', gerant_code_postal='00000')
        self.autre = EquipeFactory(course=self.c2, gerant_ville='Paris', gerant_code_postal='75015')
        CodePostal.objects.create(pays='FR', code_postal='75015', nom='Paris 15', nom_normalise='paris',
                                  region='Île-de-France', departement='Paris', lat=Decimal('48.84'), lng=Decimal('2.3'))

    def run_cmd(self, *args):
        out = io.StringIO()
        call_command('geocoder_equipes', *args, stdout=out)
        return out.getvalue()

    def ville(self, e):
        return Equipe.objects.get(pk=e.pk).gerant_ville2

    def test_exige_un_perimetre(self):
        with self.assertRaises(CommandError):
            self.run_cmd()

    def test_dry_run_n_ecrit_rien(self):
        out = self.run_cmd('--toutes', '--dry-run')
        self.assertIn('[dry-run] 4 equipes traitees, 3 localisees, 1 non resolues', out)
        self.assertIsNone(self.ville(self.paris))
        self.assertEqual(Ville.objects.count(), 0)

    def test_toutes(self):
        out = self.run_cmd('--toutes')
        self.assertIn('4 equipes traitees, 3 localisees, 1 non resolues', out)
        self.assertIn('geo2 #%s' % self.ailleurs.numero, out)
        self.assertEqual(self.ville(self.paris).nom, 'Paris')
        self.assertEqual(self.ville(self.paris).pk, self.ville(self.paris2).pk)
        self.assertIsNone(self.ville(self.ailleurs))
        self.assertEqual(Ville.objects.count(), 1)

    def test_par_course(self):
        self.run_cmd('--course', 'geo1')
        self.assertIsNotNone(self.ville(self.paris))
        self.assertIsNone(self.ville(self.autre))

    def test_localise_aussi_les_courses(self):
        self.c1.ville = 'Paris'
        type(self.c1).objects.filter(pk=self.c1.pk).update(ville='Paris', ville2=None)
        out = self.run_cmd('--course', 'geo1')
        self.assertIn('1 courses localisees', out)
        self.assertEqual(type(self.c1).objects.get(pk=self.c1.pk).ville2.nom, 'Paris')

    def test_force_recalcule_et_sans_force_conserve(self):
        ancienne = Ville.objects.create(nom='Ancienne', pays='FR', region='X', lat=1, lng=1)
        Equipe.objects.filter(pk=self.paris.pk).update(gerant_ville2=ancienne)
        self.run_cmd('--toutes')
        self.assertEqual(self.ville(self.paris), ancienne)
        self.run_cmd('--toutes', '--force')
        self.assertEqual(self.ville(self.paris).nom, 'Paris')
