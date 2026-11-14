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
        self.assertIn('GeoNames', html)

    def test_page_sans_origine_pas_de_graphique_distance(self):
        self.course.ville2 = None
        type(self.course).objects.filter(pk=self.course.pk).update(ville2=None)
        html = self.client.get(reverse('inscriptions_stats', kwargs={'course_uid': 'geo'})).content.decode()
        self.assertNotIn('id="canvas_distance"', html)
        self.assertIn('id="map"', html)
        self.assertIn('var origine = null', html)


import json  # noqa: E402

from django.contrib.auth.models import User  # noqa: E402


class AugmentationsMultiplesTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        today = date.today()
        self.today = today
        self.c1 = CourseFactory(
            uid='aug3', date=today + timedelta(days=100), date_ouverture=today - timedelta(days=20),
            date_fermeture=today + timedelta(days=90),
            dates_augmentation=[today + timedelta(days=30), today + timedelta(days=10), today + timedelta(days=60)])
        self.c0 = CourseFactory(
            uid='aug0', date=today + timedelta(days=100), date_ouverture=today - timedelta(days=20),
            date_fermeture=today + timedelta(days=90), dates_augmentation=[])
        self.c1b = CourseFactory(
            uid='aug1', date=today + timedelta(days=100), date_ouverture=today - timedelta(days=20),
            date_fermeture=today + timedelta(days=90), dates_augmentation=[today + timedelta(days=5)])
        for c in (self.c1, self.c0, self.c1b):
            CategorieFactory(course=c)
        su = User.objects.create_superuser('su', 'su@example.com', 'x')
        self.client.force_login(su)
        self.client.cookies['course_uid'] = self.c1.uid
        self.client.cookies['course_id'] = str(self.c1.id)

    def api(self, uid):
        response = self.client.get('/course/stats/%s/' % uid)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_api_liste_toutes_les_augmentations_dans_l_ordre(self):
        data = self.api('aug3')
        self.assertEqual([a['delta'] for a in data['augmentations']], [29, 49, 79])  # jours depuis l'ouverture - 1
        self.assertNotIn('augmentation', data['delta'])
        self.assertNotIn('augmentation', data['date'])
        self.assertEqual(data['delta']['course'], 120)

    def test_api_sans_augmentation(self):
        self.assertEqual(self.api('aug0')['augmentations'], [])

    def test_compare_alignement_sur_la_nieme_augmentation(self):
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'aug3', 'course_uid2': 'aug1,aug0'})
        # n = 1 : aug3 -> 30 j, aug1 -> 25 j ; la course sans augmentation reste alignee sur sa date (120 j)
        data = self.client.get(url, {'align': 'augment'}).context['data']
        self.assertEqual([d['delta'] for d in data], [0, 30 - 25, 30 - 120])
        # n = 2 : aug3 -> 50 j ; aug1 n'a qu'une augmentation : sa derniere (25 j) est utilisee
        data = self.client.get(url, {'align': 'augment:2'}).context['data']
        self.assertEqual([d['delta'] for d in data], [0, 50 - 25, 50 - 120])
        # n = 3 -> 80
        data = self.client.get(url, {'align': 'augment:3'}).context['data']
        self.assertEqual(data[0]['delta'], 0)
        self.assertEqual(data[1]['delta'], 80 - 25)

    def test_compare_align_invalide_ou_hors_borne(self):
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'aug3', 'course_uid2': 'aug1'})
        for align in ('augment:abc', 'augment:0', 'augment:99', 'augment:-3'):
            self.assertEqual(self.client.get(url, {'align': align}).status_code, 200)

    def test_compare_menu_une_entree_par_augmentation(self):
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'aug3', 'course_uid2': 'aug1'})
        response = self.client.get(url, {'align': 'augment:2'})
        self.assertEqual([o['value'] for o in response.context['augment_options']],
                         ['augment', 'augment:2', 'augment:3'])
        self.assertEqual([o['selected'] for o in response.context['augment_options']], [False, True, False])
        html = response.content.decode()
        self.assertIn('data-value="augment:3"', html)
        # une seule augmentation : libelle historique
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'aug1', 'course_uid2': 'aug0'})
        html = self.client.get(url).content.decode()
        self.assertIn("Date d'augmentation", html)
        self.assertNotIn('data-value="augment:2"', html)
