"""Separation Course (evenement annuel) / Edition (occurrence datee) : cle d'URL
« course/edition », redirection des anciennes URLs, validation des uid, mapping de migration."""
import importlib
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from inscriptions.factories import CourseEntiteFactory, CourseFactory
from inscriptions.middleware import legacy_uid_middleware
from inscriptions.models import valide_uid_course

from .base import BaseTestCase


class EditionKeyTestCase(BaseTestCase):
    def test_key_est_course_slash_edition(self):
        course = CourseEntiteFactory(uid='parisrace')
        edition = CourseFactory(course=course, uid='2026')
        self.assertEqual(edition.key, 'parisrace/2026')

    def test_meme_uid_d_edition_dans_deux_courses(self):
        CourseFactory(course=CourseEntiteFactory(uid='aaa'), uid='2026')
        CourseFactory(course=CourseEntiteFactory(uid='bbb'), uid='2026')

    def test_uid_d_edition_unique_dans_une_course(self):
        course = CourseEntiteFactory(uid='ccc')
        CourseFactory(course=course, uid='2026')
        with self.assertRaises(IntegrityError), transaction.atomic():
            CourseFactory(course=course, uid='2026')

    def test_uid_par_defaut_est_l_annee(self):
        edition = CourseFactory(uid='', date=date(2031, 5, 1))
        self.assertEqual(edition.uid, '2031')

    def test_page_de_l_edition_resolue_par_course_et_edition(self):
        course = CourseEntiteFactory(uid='resol')
        CourseFactory(course=course, uid='2025', nom='Edition 2025')
        CourseFactory(course=course, uid='2026', nom='Edition 2026')
        reponse = self.client.get('/resol/2025/')
        self.assertContains(reponse, 'Edition 2025')
        self.assertEqual(self.client.get('/resol/2099/').status_code, 404)
        self.assertEqual(self.client.get('/inconnu/2025/').status_code, 404)


class UidCourseTestCase(BaseTestCase):
    def test_mot_reserve_refuse(self):
        for uid in ('admin', 'course', 'challenges', 'static'):
            with self.assertRaises(ValidationError):
                valide_uid_course(uid)

    def test_ancien_uid_d_edition_refuse(self):
        CourseFactory(legacy_uid='6hdp13')
        with self.assertRaises(ValidationError):
            valide_uid_course('6hdp13')

    def test_uid_libre_accepte(self):
        valide_uid_course('nouvellecourse')


class LegacyRedirectTestCase(BaseTestCase):
    def setUp(self):
        self.edition = CourseFactory(
            course=CourseEntiteFactory(uid='6hparis'), uid='2013', legacy_uid='6hdp13')

    def test_get_redirige_en_permanence_avec_la_query_string(self):
        reponse = self.client.get('/6hdp13/list/?order=nom')
        self.assertEqual(reponse.status_code, 301)
        self.assertEqual(reponse['Location'], '/6hparis/2013/list/?order=nom')

    def test_la_racine_de_l_edition_est_redirigee(self):
        reponse = self.client.get('/6hdp13/')
        self.assertEqual(reponse.status_code, 301)
        self.assertEqual(reponse['Location'], '/6hparis/2013/')

    def test_numero_et_code_conserves(self):
        reponse = self.client.get('/6hdp13/12/abcdef/')
        self.assertEqual(reponse['Location'], '/6hparis/2013/12/abcdef/')

    def test_post_redirige_en_308(self):
        reponse = self.client.post('/6hdp13/contact/', {})
        self.assertEqual(reponse.status_code, 308)
        self.assertEqual(reponse['Location'], '/6hparis/2013/contact/')

    def test_webhooks_reecrits_en_interne_sans_redirection(self):
        # Stripe/HelloAsso/PayPal ne suivent pas les redirections
        middleware = legacy_uid_middleware(lambda request: HttpResponse(request.path_info))
        for chemin in ('stripe/webhook/', 'helloasso/webhook/', 'ipn/'):
            reponse = middleware(RequestFactory().post('/6hdp13/' + chemin))
            self.assertEqual(reponse.status_code, 200, chemin)
            self.assertEqual(reponse.content.decode(), '/6hparis/2013/' + chemin)

    def test_uid_inconnu_reste_404(self):
        self.assertEqual(self.client.get('/jamais/list/').status_code, 404)


class MappingMigrationTestCase(SimpleTestCase):
    """Le mapping des editions historiques doit rester coherent."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mapping = importlib.import_module('inscriptions.migrations._course_mapping')

    def test_aucun_uid_de_course_ne_collisionne_avec_un_ancien_uid(self):
        self.assertFalse(set(self.mapping.COURSES) & set(self.mapping.PAR_ANCIEN_UID))

    def test_uid_de_course_valides(self):
        import re
        for uid in self.mapping.COURSES:
            self.assertRegex(uid, r'^[a-z0-9]{3,}$')

    def test_uid_d_edition_uniques_par_course(self):
        for uid, data in self.mapping.COURSES.items():
            valeurs = list(data['editions'].values())
            self.assertEqual(len(valeurs), len(set(valeurs)), uid)

    def test_uid_d_edition_valides(self):
        for data in self.mapping.COURSES.values():
            for uid in data['editions'].values():
                self.assertRegex(uid, r'^[a-z0-9][a-z0-9-]*$')

    def test_76_editions_19_courses(self):
        self.assertEqual(len(self.mapping.PAR_ANCIEN_UID), 76)
        self.assertEqual(len(self.mapping.COURSES), 19)
