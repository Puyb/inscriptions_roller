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
