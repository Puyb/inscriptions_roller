"""Referentiel local de codes postaux : normalisation et import GeoNames."""
import io
import os
import tempfile
import zipfile

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from inscriptions.geocoding import normaliser_cp, normaliser_nom
from inscriptions.tests.base import BaseTestCase
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

    def test_pays_absent_de_geonames_ignore(self):
        import urllib.error
        from unittest import mock
        chemin = self._zip()

        def urlopen(url, timeout=None):
            if url.endswith('/ZZ.zip'):
                raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
            return open(chemin, 'rb')

        with mock.patch('urllib.request.urlopen', urlopen):
            self._run('--pays', 'FR,ZZ')
        self.assertEqual(CodePostal.objects.filter(pays='FR').count(), 3)

    def test_import_txt_tous_pays(self):
        f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
        f.write(GEONAMES)
        f.close()
        self.addCleanup(os.unlink, f.name)
        self._run('--fichier', f.name)
        self.assertEqual(sorted(CodePostal.objects.values_list('pays', flat=True)),
                         ['BE', 'DE', 'FR', 'FR', 'FR'])


from decimal import Decimal  # noqa: E402

from inscriptions.factories import EquipeFactory  # noqa: E402
from inscriptions.geocoding import nom_affichage, trouver  # noqa: E402
from inscriptions.models import Ville, lookup_ville  # noqa: E402


def cp(pays, code, nom, lat, lng, region='Region', dep='Dep'):
    return CodePostal.objects.create(
        pays=pays, code_postal=code, nom=nom, nom_normalise=normaliser_nom(nom),
        region=region, departement=dep, lat=Decimal(lat), lng=Decimal(lng))


class LookupTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cp('FR', '58000', 'Nevers', '46.99', '3.16', 'Bourgogne-Franche-Comté', 'Nièvre')
        cp('FR', '58180', 'Marzy', '47.0', '3.1', 'Bourgogne-Franche-Comté', 'Nièvre')
        cp('FR', '42000', 'Saint-Étienne', '45.43', '4.39', 'Auvergne-Rhône-Alpes', 'Loire')
        cp('FR', '75015', 'Paris 15', '48.84', '2.30', 'Île-de-France', 'Paris')
        cp('FR', '75016', 'Paris 16', '48.86', '2.27', 'Île-de-France', 'Paris')
        cp('FR', '10000', 'Troyes', '48.29', '4.07', 'Grand Est', 'Aube')
        cp('FR', '10300', 'Sainte-Savine', '48.29', '4.04', 'Grand Est', 'Aube')
        cp('FR', '10440', 'La Rivière-de-Corps', '48.28', '4.03', 'Grand Est', 'Aube')
        # homonymes eloignes
        cp('FR', '93200', 'Saint-Denis', '48.93', '2.35', 'Île-de-France', 'Seine-Saint-Denis')
        cp('FR', '97400', 'Saint-Denis', '-20.88', '55.45', 'La Réunion', 'La Réunion')
        # homonymes proches
        cp('FR', '10001', 'Doublon', '48.0', '4.0', 'Grand Est', 'Aube')
        cp('FR', '10002', 'Doublon', '48.01', '4.0', 'Grand Est', 'Aube')
        cp('NL', '1012', 'Amsterdam', '52.37', '4.89')
        cp('GB', 'SW1A', 'London', '51.5', '-0.13')

    def nom(self, *args):
        r = trouver(*args)
        return r and r.nom

    def test_exact(self):
        self.assertEqual(self.nom('Nevers', '58000', 'FR'), 'Nevers')

    def test_nom_approximatif(self):
        self.assertEqual(self.nom('St Etienne', '42000', 'FR'), 'Saint-Étienne')
        self.assertEqual(self.nom('Nevers ', '58 000', 'fr'), 'Nevers')

    def test_arrondissement_et_cedex(self):
        self.assertEqual(self.nom('Paris 15e', '75015', 'FR'), 'Paris 15')
        self.assertEqual(self.nom('Troyes Cedex', '10000', 'FR'), 'Troyes')
        self.assertEqual(nom_affichage('Paris 15'), 'Paris')
        self.assertEqual(nom_affichage('Troyes'), 'Troyes')

    def test_code_postal_seul_une_commune(self):
        self.assertEqual(self.nom('Nom faux', '58000', 'FR'), 'Nevers')
        self.assertEqual(self.nom('', '58000', 'FR'), 'Nevers')

    def test_code_postal_plusieurs_communes(self):
        cp('FR', '58000', 'Challuy', '46.95', '3.12')
        self.assertEqual(self.nom('Challuy', '58000', 'FR'), 'Challuy')
        self.assertEqual(self.nom('Chaluy', '58000', 'FR'), 'Challuy')  # proche
        self.assertEqual(self.nom('Zzz', '58000', 'FR'), 'Challuy')  # repli alphabetique

    def test_nom_sans_code_postal(self):
        self.assertEqual(self.nom('Troyes', '', 'FR'), 'Troyes')
        self.assertEqual(self.nom('Troyes', '99999', 'FR'), 'Troyes')

    def test_homonymes_eloignes_pas_de_devinette(self):
        self.assertIsNone(trouver('Saint-Denis', '', 'FR'))
        # ... mais le code postal tranche
        self.assertEqual(trouver('Saint-Denis', '97400', 'FR').region, 'La Réunion')

    def test_homonymes_proches(self):
        self.assertEqual(self.nom('Doublon', '', 'FR'), 'Doublon')

    def test_repli_departement(self):
        r = trouver('Inconnue', '10999', 'FR')
        self.assertTrue(r.approximatif)
        self.assertEqual((r.nom, r.region), ('Aube', 'Grand Est'))
        self.assertTrue(Decimal('47.9') < r.lat < Decimal('48.4'))

    def test_pays_etrangers(self):
        self.assertEqual(self.nom('Amsterdam', '1012 AB', 'NL'), 'Amsterdam')
        self.assertEqual(self.nom('London', 'SW1A 1AA', 'GB'), 'London')

    def test_sentinelle_et_vide(self):
        self.assertIsNone(trouver('?', '?', 'FR'))
        self.assertIsNone(trouver('', '', 'FR'))
        self.assertIsNone(trouver('Nevers', '58000', ''))
        self.assertIsNone(trouver('Nulle part', '00000', 'FR'))
        self.assertIsNone(trouver('Nevers', '58000', 'ES'))


class LookupVilleTestCase(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        cp('FR', '75015', 'Paris 15', '48.84', '2.30', 'Île-de-France', 'Paris')
        cp('FR', '75016', 'Paris 16', '48.86', '2.27', 'Île-de-France', 'Paris')

    def test_ville_creee_puis_reutilisee(self):
        v1 = lookup_ville('Paris 15', '75015', 'FR')
        v2 = lookup_ville('Paris', '75016', 'FR')
        self.assertEqual((v1.nom, v1.pays, v1.region), ('Paris', 'FR', 'Île-de-France'))
        self.assertEqual(v1.pk, v2.pk)
        self.assertEqual(Ville.objects.count(), 1)

    def test_aucune_ville(self):
        self.assertIsNone(lookup_ville('Nulle part', '00000', 'FR'))

    def test_equipe_geocodee_a_la_creation_et_quand_l_adresse_change(self):
        cp('FR', '10000', 'Troyes', '48.29', '4.07', 'Grand Est', 'Aube')
        equipe = EquipeFactory(gerant_ville='Paris', gerant_code_postal='75015')
        self.assertEqual(equipe.gerant_ville2.nom, 'Paris')
        equipe = type(equipe).objects.get(pk=equipe.pk)
        equipe.gerant_ville, equipe.gerant_code_postal = 'Troyes', '10000'
        equipe.save()
        self.assertEqual(type(equipe).objects.get(pk=equipe.pk).gerant_ville2.nom, 'Troyes')

    def test_ville_fournie_explicitement_est_conservee(self):
        ville = Ville.objects.create(nom='Ailleurs', pays='FR', region='X', lat=1, lng=1)
        equipe = EquipeFactory(gerant_ville2=ville)
        self.assertEqual(equipe.gerant_ville2, ville)
        equipe = type(equipe).objects.get(pk=equipe.pk)
        equipe.nom = 'Autre nom'
        equipe.save()
        self.assertEqual(type(equipe).objects.get(pk=equipe.pk).gerant_ville2, ville)
