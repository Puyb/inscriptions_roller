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


class UidEditionParDefautTestCase(BaseTestCase):
    def test_uid_par_defaut_est_l_annee_puis_suffixe(self):
        course = CourseEntiteFactory(uid='3h6h')
        uids = []
        for _ in range(3):
            e = CourseFactory(course=course, uid='', date=date(2026, 5, 1))
            uids.append(e.uid)
        self.assertEqual(uids, ['2026', '2026-2', '2026-3'])


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

    def test_get_edition_accepte_un_ancien_uid(self):
        from inscriptions.models import get_edition
        self.assertEqual(get_edition('6hdp13'), self.edition)
        self.assertEqual(get_edition('6hparis/2013'), self.edition)

    def test_stats_compare_avec_anciens_uids(self):
        autre = CourseFactory(course=self.edition.course, uid='2014', legacy_uid='6hdp14')
        reponse = self.client.get('/6hparis/2013/stats/6hdp14')
        self.assertNotEqual(reponse.status_code, 404, autre)


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


# --- creation d'une course / d'une edition depuis l'admin organisateur ----------------

import json  # noqa: E402
from datetime import timedelta  # noqa: E402

from django.contrib.auth.models import User  # noqa: E402

from inscriptions.factories import CategorieFactory  # noqa: E402
from inscriptions.models import Accreditation, Categorie, Course, Edition, TemplateMail  # noqa: E402

ADD = '/course/inscriptions/edition/add/'


def donnees_edition(**surcharges):
    futur = date.today() + timedelta(days=200)
    data = dict(
        nom='Edition test', uid='2099', url_reglement='http://example.com/r', email_contact='o@example.com',
        date=futur.isoformat(), date_ouverture=(futur - timedelta(days=100)).isoformat(),
        date_fermeture=(futur - timedelta(days=2)).isoformat(), dates_augmentation='',
        limite_participants='300', delai_paiement='31',
        course_model='paris', course_prix='{}',
    )
    data.update(surcharges)
    return data


class CreationEditionTestCase(BaseTestCase):
    def setUp(self):
        self.user = User.objects.create_user('orga', 'orga@example.com', 'x')
        self.client.force_login(self.user)
        self.course = CourseEntiteFactory(uid='creation', nom='Creation')
        self.precedente = CourseFactory(course=self.course, uid='2025', nom='Edition 2025',
                                        date=date.today() - timedelta(days=165),
                                        date_ouverture=date.today() - timedelta(days=265),
                                        date_fermeture=date.today() - timedelta(days=167),
                                        limite_participants=555, email_contact='ancienne@example.com')
        self.cat = CategorieFactory(course=self.precedente, code='DUO', nom='Duo', prices_base=[10], prices_equipier=[5])
        TemplateMail.objects.create(course=self.precedente, nom='inscription', sujet='S', message='M')
        Accreditation.objects.create(user=self.user, course=self.course, role='admin')

    def test_formulaire_prerempli_avec_la_derniere_edition(self):
        reponse = self.client.get(ADD, {'course': 'creation'})
        self.assertEqual(reponse.status_code, 200)
        initial = reponse.context['adminform'].form.initial
        self.assertEqual(initial['email_contact'], 'ancienne@example.com')
        self.assertEqual(initial['limite_participants'], 555)
        self.assertEqual(initial['uid'], str(self.precedente.date.year + 1))
        self.assertEqual(initial['date'].year, self.precedente.date.year + 1)

    def test_creation_reprend_l_edition_precedente(self):
        reponse = self.client.post(ADD + '?course=creation', donnees_edition(
            course_model=str(self.precedente.id),
            course_prix=json.dumps({'DUO': {'prices_base': [12], 'prices_equipier': [6]}})))
        self.assertEqual(reponse.status_code, 302, getattr(reponse, 'context', None) and reponse.context['adminform'].form.errors)
        edition = Edition.objects.get(course=self.course, uid='2099')
        self.assertFalse(edition.active)  # non publiee par defaut
        self.assertEqual(reponse.cookies['course_uid'].value, 'creation/2099')
        categorie = Categorie.objects.get(course=edition, code='DUO')
        self.assertEqual(categorie.prices_base, [12])
        self.assertEqual(categorie.prices_equipier, [6])
        self.assertEqual(TemplateMail.objects.filter(course=edition, nom='inscription').count(), 1)
        self.assertEqual(Course.objects.count(), 1)

    def test_creation_depuis_un_modele_json_sans_edition_precedente(self):
        autre = CourseEntiteFactory(uid='sansedition')
        Accreditation.objects.create(user=self.user, course=autre, role='admin')
        reponse = self.client.post(ADD + '?course=sansedition', donnees_edition(course_model='paris'))
        self.assertEqual(reponse.status_code, 302)
        edition = Edition.objects.get(course=autre, uid='2099')
        self.assertTrue(Categorie.objects.filter(course=edition, code='IDH').exists())

    def test_uid_deja_pris_dans_la_course_refuse(self):
        reponse = self.client.post(ADD + '?course=creation', donnees_edition(
            uid='2025', course_model=str(self.precedente.id)))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('uid', reponse.context['adminform'].form.errors)

    def test_legacy_uid_non_modifiable_depuis_le_formulaire(self):
        reponse = self.client.post(ADD + '?course=creation', donnees_edition(
            course_model=str(self.precedente.id), legacy_uid='vieux'))
        self.assertEqual(reponse.status_code, 302)
        self.assertIsNone(Edition.objects.get(course=self.course, uid='2099').legacy_uid)

    def test_non_accredite_refuse(self):
        etranger = User.objects.create_user('etranger', 'e@example.com', 'x')
        self.client.force_login(etranger)
        self.assertEqual(self.client.get(ADD, {'course': 'creation'}).status_code, 403)

    def test_accreditation_en_attente_refusee(self):
        Accreditation.objects.filter(user=self.user).update(role='')
        self.assertEqual(self.client.get(ADD, {'course': 'creation'}).status_code, 403)

    def test_copie_d_une_edition_d_une_autre_course_refusee(self):
        autre = CourseFactory(uid='autrecourse')
        reponse = self.client.post(ADD + '?course=creation', donnees_edition(course_model=str(autre.id)))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('course_model', reponse.context['adminform'].form.errors)
        self.assertFalse(Edition.objects.filter(course=self.course, uid='2099').exists())

    def test_models_liste_les_editions_precedentes_d_abord(self):
        plus_ancienne = CourseFactory(course=self.course, uid='2020', date=date.today() - timedelta(days=2000))
        reponse = self.client.get('/course/inscriptions/edition/models/', {'course': 'creation'})
        data = json.loads(reponse.content)
        self.assertEqual(data['_order'], [str(self.precedente.id), str(plus_ancienne.id)])
        self.assertNotIn('paris', data)  # les modeles JSON ne servent que sans edition

    def test_models_sans_edition_propose_les_modeles_json(self):
        autre = CourseEntiteFactory(uid='vide')
        Accreditation.objects.create(user=self.user, course=autre, role='admin')
        data = json.loads(self.client.get('/course/inscriptions/edition/models/', {'course': 'vide'}).content)
        self.assertIn('paris', data['_order'])


class CreationCourseTestCase(BaseTestCase):
    def setUp(self):
        self.user = User.objects.create_user('nouveau', 'n@example.com', 'x')
        self.client.force_login(self.user)

    def donnees(self, **surcharges):
        data = donnees_edition(
            course_nom='Nouvelle Course', course_uid='nouvellecourse', organisateur='Club', ville='Paris',
            url='http://example.com', ordre='Club', frais_paypal_inclus='', frais_stripe_inclus='', helloasso_sandbox='on')
        data.update(surcharges)
        return data

    def test_creation_course_et_premiere_edition(self):
        reponse = self.client.post(ADD, self.donnees())
        self.assertEqual(reponse.status_code, 302, getattr(reponse, 'context', None) and reponse.context['adminform'].form.errors)
        course = Course.objects.get(uid='nouvellecourse')
        self.assertFalse(course.active)  # validation par un superutilisateur
        self.assertEqual(course.nom, 'Nouvelle Course')
        edition = course.editions.get()
        self.assertEqual(edition.key, 'nouvellecourse/2099')
        self.assertEqual(course.accreditations.get().user, self.user)
        self.assertEqual(course.accreditations.get().role, 'admin')

    def test_uid_de_course_reserve_ou_pris_refuse(self):
        for uid in ('admin', 'static'):
            reponse = self.client.post(ADD, self.donnees(course_uid=uid))
            self.assertEqual(reponse.status_code, 200)
            self.assertIn('course_uid', reponse.context['adminform'].form.errors)
        CourseEntiteFactory(uid='dejala')
        reponse = self.client.post(ADD, self.donnees(course_uid='dejala'))
        self.assertIn('course_uid', reponse.context['adminform'].form.errors)

    def test_uid_de_course_ancien_uid_d_edition_refuse(self):
        CourseFactory(legacy_uid='6hdp13')
        reponse = self.client.post(ADD, self.donnees(course_uid='6hdp13'))
        self.assertIn('course_uid', reponse.context['adminform'].form.errors)

    def test_copie_d_une_edition_inaccessible_refusee(self):
        autre = CourseFactory(uid='privee')
        reponse = self.client.post(ADD, self.donnees(course_model=str(autre.id)))
        self.assertIn('course_model', reponse.context['adminform'].form.errors)
