"""Statistiques : structure de `Course.stats()` et rendu de la page publique."""
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.models import PAYS_INCONNU, Paiement, PaiementRepartition
from inscriptions.tests.base import BaseTestCase


class CourseStatsTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='st1')
        self.cat = CategorieFactory(course=self.course)
        self.equipe = EquipeFactory(course=self.course, categorie=self.cat, club='Club S')
        EquipierFactory(equipe=self.equipe, numero=1)

    def _pay(self, equipe, type_, montant):
        paiement = Paiement.objects.create(type=type_, montant=Decimal(montant))
        PaiementRepartition.objects.create(paiement=paiement, equipe=equipe, montant=Decimal(montant))

    def test_equipe_sans_ville_est_pays_inconnu(self):
        stats = self.course.stats()
        self.assertEqual(list(stats['pays']), [PAYS_INCONNU])
        self.assertEqual(stats['pays'][PAYS_INCONNU]['equipes'], 1)
        self.assertEqual(stats['villes'], [])

    def test_paiements_par_type(self):
        self.assertEqual(self.course.stats()['course']['paiements_par_type'], {})
        self._pay(self.equipe, 'stripe', '40.00')
        autre = EquipeFactory(course=self.course, categorie=self.cat)
        EquipierFactory(equipe=autre, numero=2)
        self._pay(autre, 'chèque', '20.00')
        self._pay(autre, 'chèque', '20.00')
        self.assertEqual(self.course.stats()['course']['paiements_par_type'],
                         {'stripe': 1, 'chèque': 1})

    def test_dates_augmentation_null(self):
        self.course.dates_augmentation = None
        self.course.save()
        self.course.refresh_from_db()
        self.assertEqual(self.course.augmentations, [])
        self.assertIsNone(self.course.date_augmentation)
        self.assertEqual(self.cat.prix(date.today(), 1), Decimal('50.00'))
        self.assertEqual(self.course.stats()['course']['equipes'], 1)

    def test_augmentations_triees(self):
        d1, d2 = date.today() + timedelta(days=5), date.today() + timedelta(days=15)
        self.course.dates_augmentation = [d2, d1]
        self.assertEqual(self.course.augmentations, [d1, d2])


class StatsPageTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='st2')
        cat = CategorieFactory(course=self.course)
        EquipierFactory(equipe=EquipeFactory(course=self.course, categorie=cat), numero=1)
        self.url = reverse('inscriptions_stats', kwargs={'course_uid': 'st2'})

    def test_sans_ville_pas_de_carte(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('Localisation indisponible', html)
        self.assertNotIn('id="map"', html)
        self.assertNotIn('id="canvas_distance"', html)
        self.assertNotIn('tile.osm.org', html)
        self.assertIn('Non localisé', html)
        self.assertNotIn('flags/.png', html)


from inscriptions.models import CodePostal, REGION_NORMALISATION  # noqa: E402


def commune(pays, code, nom, lat, lng, region):
    from inscriptions.geocoding import normaliser_nom
    return CodePostal.objects.create(
        pays=pays, code_postal=code, nom=nom, nom_normalise=normaliser_nom(nom),
        region=region, departement='D', lat=Decimal(lat), lng=Decimal(lng))


class StatsGeographieTestCase(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        commune('FR', '58000', 'Nevers', '46.9894', '3.1581', 'Bourgogne-Franche-Comté')
        commune('FR', '10000', 'Troyes', '48.2973', '4.0744', 'Grand Est')
        commune('FR', '44000', 'Nantes', '47.2184', '-1.5536', 'Pays de la Loire')
        commune('BE', '1000', 'Bruxelles', '50.8466', '4.3517', 'Bruxelles-Capitale')

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='geo', ville='Nevers')
        self.cat = CategorieFactory(course=self.course)
        for ville, cp, pays, nombre in [
                ('Nevers', '58000', 'FR', 1), ('Troyes', '10000', 'FR', 2),
                ('Nantes', '44000', 'FR', 1), ('Bruxelles', '1000', 'BE', 1), ('?', '?', 'FR', 1)]:
            equipe = EquipeFactory(course=self.course, categorie=self.cat, gerant_ville=ville,
                                   gerant_code_postal=cp, gerant_pays=pays, nombre=nombre)
            EquipierFactory(equipe=equipe, numero=1)

    def test_course_geocodee_a_la_creation(self):
        self.assertEqual(self.course.ville2.nom, 'Nevers')
        stats = self.course.stats()
        self.assertEqual(stats['origine']['nom'], 'Nevers')
        self.assertAlmostEqual(stats['origine']['lat'], 46.9894, places=3)

    def test_course_sans_localisation(self):
        course = CourseFactory(uid='nowhere', ville='Zzzzz')
        self.assertIsNone(course.ville2)
        self.assertIsNone(course.stats()['origine'])

    def test_pays_et_regions(self):
        pays = self.course.stats()['pays']
        self.assertEqual(set(pays), {'Bourgogne-Franche-Comté', 'Grand-Est', 'Pays de la Loire', 'BE', PAYS_INCONNU})
        self.assertEqual(pays['BE']['pays'], 'BE')
        self.assertEqual(pays['Grand-Est']['pays'], 'FR')
        self.assertEqual(pays[PAYS_INCONNU]['equipes'], 1)

    def test_villes_ponderees_par_nombre_d_equipiers(self):
        villes = {v['nom']: v['count'] for v in self.course.stats()['villes']}
        self.assertEqual(villes, {'Nevers': 1, 'Troyes': 2, 'Nantes': 1, 'Bruxelles': 1})

    def test_regions_normalisees_sans_faute_de_casse(self):
        for region in set(REGION_NORMALISATION.values()):
            self.assertEqual(region, region.strip())
        self.assertNotEqual(REGION_NORMALISATION['Lorraine'], 'Grand-est')
        self.assertEqual(REGION_NORMALISATION['Pays-de-la-Loire'], 'Pays de la Loire')

    def test_page_utilise_l_origine_de_la_course(self):
        html = self.client.get(reverse('inscriptions_stats', kwargs={'course_uid': 'geo'})).content.decode()
        self.assertIn('id="canvas_distance"', html)
        self.assertIn('new L.LatLng(46.9894', html)
        self.assertNotIn('48.852775', html)
        self.assertIn('id="map"', html)

    def test_page_sans_origine_pas_de_graphique_distance(self):
        self.course.ville2 = None
        type(self.course).objects.filter(pk=self.course.pk).update(ville2=None)
        html = self.client.get(reverse('inscriptions_stats', kwargs={'course_uid': 'geo'})).content.decode()
        self.assertNotIn('id="canvas_distance"', html)
        self.assertIn('id="map"', html)
        self.assertIn('var origine = null', html)
