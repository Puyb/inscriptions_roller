"""Referentiel local de codes postaux : normalisation et import GeoNames."""
import io
import os
import tempfile
import zipfile

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from inscriptions.geocoding import normaliser_cp, normaliser_nom
from inscriptions.models import CodePostal

# pays, cp, nom, admin1, code1, admin2, code2, admin3, code3, lat, lng, precision
GEONAMES = """\
FR\t75015\tParis 15\tÎle-de-France\t11\tParis\t75\tParis\t751\t48.8421\t2.3003\t5
FR\t58000\tNevers\tBourgogne-Franche-Comté\t27\tNièvre\t58\tNevers\t581\t46.9894\t3.1581\t5
FR\t10000\tTroyes\tGrand Est\t44\tAube\t10\tTroyes\t101\t48.2973\t4.0744\t5
BE\t1000\tBruxelles\tBruxelles\tBRU\t\t\t\t\t50.8466\t4.3517\t5
DE\t10115\tBerlin\tBerlin\tBE\t\t\t\t\t52.532\t13.3849\t5
FR\tXXXXX\tPoubelle\t\t\t\t\t\t\tabc\tdef\t5
"""


class NormalisationTestCase(SimpleTestCase):
    def test_nom(self):
        self.assertEqual(normaliser_nom('St Étienne'), 'saint etienne')
        self.assertEqual(normaliser_nom('Saint-Étienne'), 'saint etienne')
        self.assertEqual(normaliser_nom('STE-Foy-lès-Lyon'), 'sainte foy les lyon')
        self.assertEqual(normaliser_nom('Paris 15e'), 'paris')
        self.assertEqual(normaliser_nom('Paris 15'), 'paris')
        self.assertEqual(normaliser_nom('Lyon 3eme'), 'lyon')
        self.assertEqual(normaliser_nom('Troyes Cedex 9'), 'troyes')
        self.assertEqual(normaliser_nom("L'Isle-d'Abeau"), 'l isle d abeau')
        self.assertEqual(normaliser_nom(None), '')

    def test_cp(self):
        self.assertEqual(normaliser_cp(' 75 015 ', 'FR'), '75015')
        self.assertEqual(normaliser_cp('F-75015', 'fr'), '75015')
        self.assertEqual(normaliser_cp('2a000', 'FR'), '2A000')
        self.assertEqual(normaliser_cp('1234 ab', 'NL'), '1234')
        self.assertEqual(normaliser_cp('SW1A 1AA', 'GB'), 'SW1A')
        self.assertEqual(normaliser_cp('sw1a1aa', 'GB'), 'SW1A')
        self.assertEqual(normaliser_cp('K1A 0B1', 'CA'), 'K1A')
        self.assertEqual(normaliser_cp('CH-1000', 'CH'), '1000')
        self.assertEqual(normaliser_cp(None, 'FR'), '')


class ImportTestCase(TestCase):
    def _zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('FR.txt', GEONAMES)
            z.writestr('readme.txt', 'ignore')
        f = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        f.write(buf.getvalue())
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def _run(self, *args):
        call_command('import_codes_postaux', *args, stdout=io.StringIO())

    def test_import_zip_filtre_pays(self):
        self._run('--fichier', self._zip(), '--pays', 'FR')
        self.assertEqual(CodePostal.objects.count(), 3)
        paris = CodePostal.objects.get(code_postal='75015')
        self.assertEqual((paris.nom, paris.nom_normalise, paris.region, paris.departement),
                         ('Paris 15', 'paris', 'Île-de-France', 'Paris'))
        self.assertFalse(CodePostal.objects.filter(pays='BE').exists())

    def test_import_idempotent_et_ne_touche_pas_les_autres_pays(self):
        CodePostal.objects.create(pays='ES', code_postal='28001', nom='Madrid', nom_normalise='madrid',
                                  lat=40.4, lng=-3.7)
        chemin = self._zip()
        self._run('--fichier', chemin, '--pays', 'FR')
        self._run('--fichier', chemin, '--pays', 'FR')
        self.assertEqual(CodePostal.objects.filter(pays='FR').count(), 3)
        self.assertEqual(CodePostal.objects.filter(pays='ES').count(), 1)

    def test_import_txt_tous_pays(self):
        f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
        f.write(GEONAMES)
        f.close()
        self.addCleanup(os.unlink, f.name)
        self._run('--fichier', f.name)
        self.assertEqual(sorted(CodePostal.objects.values_list('pays', flat=True)),
                         ['BE', 'DE', 'FR', 'FR', 'FR'])
