import csv
import io
import json
import unittest
import zipfile
from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from inscriptions import admin_views
from inscriptions.factories import (
    CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory, ExtraQuestionFactory,
)
from inscriptions.models import Accreditation, Equipier
from inscriptions.tests.base import BaseTestCase


def login_as_organizer(client, course, username='orga'):
    user = User.objects.create_user(username, username + '@example.com', 'pass1234')
    Accreditation.objects.create(user=user, course=course, role='admin')
    client.force_login(user)
    client.cookies['course_uid'] = course.uid
    client.cookies['course_id'] = str(course.id)
    return user


def parse_csv(response, encoding='utf-8'):
    return list(csv.reader(io.StringIO(response.content.decode(encoding))))


def pending_equipier(equipe, numero=1, **kwargs):
    """Equipier avec un justificatif en attente de relecture (verifier=True)."""
    return EquipierFactory(
        equipe=equipe, numero=numero, piece_jointe_valide=None,
        piece_jointe=SimpleUploadedFile('certif.pdf', b'%PDF-1.4 test'), **kwargs
    )


class ExportBaseTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.categorie = CategorieFactory(course=self.course, min_equipiers=1, max_equipiers=3)


class DossardsCSVTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        login_as_organizer(self.client, self.course)

    def test_headers_rows_and_order(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2, nom='Alpha',
                           gerant_nom='Martin', gerant_prenom='Luc', gerant_ville='Lyon',
                           gerant_code_postal='69000', gerant_pays='FR')
        q1 = EquipierFactory(equipe=e1, numero=1, nom='Durand', prenom='Anne', sexe='F',
                             date_de_naissance=date(1985, 3, 4), num_licence='L123')
        q2 = EquipierFactory(equipe=e1, numero=2, nom='Petit', prenom='Paul')

        response = self.client.get('/%s/dossards.csv' % self.course.uid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        rows = parse_csv(response)
        self.assertEqual(rows[0], [
            'equipe', 'nom', 'categorie', 'dossard', 'nom', 'prenom', 'sexe', 'date_de_naissance',
            'num_licence', 'gerant_nom', 'gerant_prenom', 'gerant_ville', 'gerant_code_postal',
            'gerant_code_pays',
        ])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1], [
            str(e1.numero), 'Alpha', str(self.categorie), str(q1.dossard()), 'Durand', 'Anne', 'F',
            '1985-03-04', 'L123', 'Martin', 'Luc', 'Lyon', '69000', 'FR',
        ])
        self.assertEqual(rows[2][3], str(q2.dossard()))
        self.assertEqual(rows[2][4:6], ['Petit', 'Paul'])

    def test_only_requested_course_is_exported(self):
        other = CourseFactory()
        other_cat = CategorieFactory(course=other)
        EquipierFactory(equipe=EquipeFactory(course=other, categorie=other_cat), numero=1, nom='Autre')
        EquipierFactory(equipe=EquipeFactory(course=self.course, categorie=self.categorie), numero=1, nom='Ici')

        rows = parse_csv(self.client.get('/%s/dossards.csv' % self.course.uid))
        self.assertEqual([r[4] for r in rows[1:]], ['Ici'])

    def test_header_only_when_no_equipier(self):
        rows = parse_csv(self.client.get('/%s/dossards.csv' % self.course.uid))
        self.assertEqual(len(rows), 1)

    def test_encoding_parameter_and_non_ascii(self):
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nom='Équipe Été')
        EquipierFactory(equipe=equipe, numero=1, nom='Müller', prenom='Zoë')

        response = self.client.get('/%s/dossards.csv?code=iso-8859-1' % self.course.uid)
        # NB: le charset n'est pas annoncé dans Content-Type (content_type explicite écrase charset=)
        rows = parse_csv(response, 'iso-8859-1')
        self.assertEqual(rows[1][1], 'Équipe Été')
        self.assertEqual(rows[1][4:6], ['Müller', 'Zoë'])
        with self.assertRaises(UnicodeDecodeError):
            response.content.decode('utf-8')

        rows = parse_csv(self.client.get('/%s/dossards.csv' % self.course.uid))
        self.assertEqual(rows[1][4:6], ['Müller', 'Zoë'])

    def test_equipiers_beyond_team_size_are_not_exported(self):
        # Les lignes d'équipier au-delà de equipe.nombre sont des restes ignorés partout ailleurs
        # (export organisateur, transpondeurs, dossards imprimés).
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=1)
        EquipierFactory(equipe=equipe, numero=1, nom='Actif')
        EquipierFactory(equipe=equipe, numero=2, nom='Reste')

        rows = parse_csv(self.client.get('/%s/dossards.csv' % self.course.uid))
        self.assertEqual([r[4] for r in rows[1:]], ['Actif'])



class DossardsEquipesCSVTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        login_as_organizer(self.client, self.course)

    def test_headers_and_rows(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie, nom='Alpha',
                           gerant_nom='Martin', gerant_prenom='Luc', gerant_ville='Lyon',
                           gerant_code_postal='69000', gerant_pays='FR')
        e2 = EquipeFactory(course=self.course, categorie=self.categorie, nom='Béta')
        other = CourseFactory()
        EquipeFactory(course=other, categorie=CategorieFactory(course=other), nom='Intruse')

        response = self.client.get('/%s/dossards_equipes.csv' % self.course.uid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        rows = parse_csv(response)
        self.assertEqual(rows[0], [
            'equipe', 'nom', 'categorie', 'gerant_nom', 'gerant_prenom', 'gerant_ville',
            'gerant_code_postal', 'gerant_code_pays',
        ])
        by_num = {int(r[0]): r for r in rows[1:]}
        self.assertEqual(set(by_num), {e1.numero, e2.numero})
        self.assertEqual(by_num[e1.numero], [
            str(e1.numero), 'Alpha', str(self.categorie), 'Martin', 'Luc', 'Lyon', '69000', 'FR',
        ])
        self.assertEqual(by_num[e2.numero][1], 'Béta')

    def test_encoding_parameter(self):
        EquipeFactory(course=self.course, categorie=self.categorie, nom='Été')
        rows = parse_csv(self.client.get('/%s/dossards_equipes.csv?code=cp1252' % self.course.uid), 'cp1252')
        self.assertEqual(rows[1][1], 'Été')


class DossardsEquipiersCSVTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        login_as_organizer(self.client, self.course)

    def test_headers_rows_and_order(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2)
        q1 = EquipierFactory(equipe=e1, numero=1, nom='Durand', prenom='Anne', sexe='F',
                             date_de_naissance=date(1985, 3, 4), num_licence='L123')
        q2 = EquipierFactory(equipe=e1, numero=2, nom='Petit', prenom='Paul')

        response = self.client.get('/%s/dossards_equipiers.csv' % self.course.uid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        rows = parse_csv(response)
        self.assertEqual(rows[0], [
            'equipe', 'dossard', 'nom', 'prenom', 'sexe', 'date_de_naissance', 'num_licence',
        ])
        self.assertEqual(rows[1], [
            str(e1.numero), str(q1.dossard()), 'Durand', 'Anne', 'F', '1985-03-04', 'L123',
        ])
        self.assertEqual(rows[2][1:4], [str(q2.dossard()), 'Petit', 'Paul'])

    def test_other_course_excluded_and_encoding(self):
        other = CourseFactory()
        EquipierFactory(equipe=EquipeFactory(course=other, categorie=CategorieFactory(course=other)),
                        numero=1, nom='Autre')
        EquipierFactory(equipe=EquipeFactory(course=self.course, categorie=self.categorie),
                        numero=1, nom='Gaëtan')
        response = self.client.get('/%s/dossards_equipiers.csv?code=iso-8859-1' % self.course.uid)
        rows = parse_csv(response, 'iso-8859-1')
        self.assertEqual([r[2] for r in rows[1:]], ['Gaëtan'])

    def test_equipiers_beyond_team_size_are_not_exported(self):
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=1)
        EquipierFactory(equipe=equipe, numero=1, nom='Actif')
        EquipierFactory(equipe=equipe, numero=2, nom='Reste')
        rows = parse_csv(self.client.get('/%s/dossards_equipiers.csv' % self.course.uid))
        self.assertEqual([r[2] for r in rows[1:]], ['Actif'])



class PersonalDataExportAccessTestCase(ExportBaseTestCase):
    """Les CSV, la page equipiers et le listing contiennent des donnees personnelles
    (noms, dates de naissance, adresses de gerants) : connexion ET role sur la course."""

    PATHS = ['dossards.csv', 'dossards_equipes.csv', 'dossards_equipiers.csv', 'equipiers/', 'listing/']

    def setUp(self):
        super().setUp()
        equipe = EquipeFactory(course=self.course, categorie=self.categorie)
        EquipierFactory(equipe=equipe, numero=1, nom='Secret')

    def url(self, path):
        return '/%s/%s' % (self.course.uid, path)

    def test_anonymous_is_redirected_to_login(self):
        for path in self.PATHS:
            response = self.client.get(self.url(path))
            self.assertEqual(response.status_code, 302, path)
            self.assertIn('login', response.url, path)

    def test_logged_user_without_accreditation_is_forbidden(self):
        self.client.force_login(User.objects.create_user('outsider', 'o@example.com', 'pass1234'))
        for path in self.PATHS:
            self.assertEqual(self.client.get(self.url(path)).status_code, 403, path)

    def test_accreditation_on_another_course_is_forbidden(self):
        login_as_organizer(self.client, CourseFactory())
        for path in self.PATHS:
            self.assertEqual(self.client.get(self.url(path)).status_code, 403, path)

    def test_accreditation_without_role_is_forbidden(self):
        user = User.objects.create_user('pending', 'p@example.com', 'pass1234')
        Accreditation.objects.create(user=user, course=self.course, role='')
        self.client.force_login(user)
        for path in self.PATHS:
            self.assertEqual(self.client.get(self.url(path)).status_code, 403, path)

    def test_organizer_has_access(self):
        login_as_organizer(self.client, self.course)
        for path in self.PATHS:
            self.assertEqual(self.client.get(self.url(path)).status_code, 200, path)

    def test_validateur_role_has_access(self):
        user = User.objects.create_user('valid', 'v@example.com', 'pass1234')
        Accreditation.objects.create(user=user, course=self.course, role='validateur')
        self.client.force_login(user)
        for path in self.PATHS:
            self.assertEqual(self.client.get(self.url(path)).status_code, 200, path)

    def test_superuser_has_access_without_accreditation(self):
        self.client.force_login(User.objects.create_superuser('root', 'r@example.com', 'pass1234'))
        for path in self.PATHS:
            self.assertEqual(self.client.get(self.url(path)).status_code, 200, path)


class EquipiersPageTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        login_as_organizer(self.client, self.course)

    def test_lists_names_of_the_course_only(self):
        EquipierFactory(equipe=EquipeFactory(course=self.course, categorie=self.categorie),
                        numero=1, nom='Dupuis', prenom='Marie')
        other = CourseFactory()
        EquipierFactory(equipe=EquipeFactory(course=other, categorie=CategorieFactory(course=other)),
                        numero=1, nom='Ailleurs')

        response = self.client.get('/%s/equipiers/' % self.course.uid)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dupuis')
        self.assertContains(response, 'Marie')
        self.assertNotContains(response, 'Ailleurs')

    def test_unknown_course_is_404(self):
        self.assertEqual(self.client.get('/nope/equipiers/').status_code, 404)


class ListingViewTestCase(ExportBaseTestCase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get('/%s/listing/' % self.course.uid)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_logged_user_gets_ordered_equipes(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie, nom='Zebra', numero=10)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie, nom='Abeille', numero=20)
        other = CourseFactory()
        EquipeFactory(course=other, categorie=CategorieFactory(course=other), nom='Intruse')
        login_as_organizer(self.client, self.course)

        response = self.client.get('/%s/listing/' % self.course.uid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['course'], self.course)
        self.assertEqual(list(response.context['equipes']), [e1, e2])
        self.assertEqual(response.context['order'], 'numero')

        response = self.client.get('/%s/listing/?order=-numero' % self.course.uid)
        self.assertEqual(list(response.context['equipes']), [e2, e1])

        response = self.client.get('/%s/listing/?order=nom' % self.course.uid)
        self.assertEqual(list(response.context['equipes']), [e2, e1])

    def test_unknown_course_is_404(self):
        login_as_organizer(self.client, self.course)
        self.assertEqual(self.client.get('/nope/listing/').status_code, 404)


class DossardsViewTestCase(ExportBaseTestCase):
    """`admin_views.dossards` n'est routée nulle part : appel direct de la vue."""

    def call(self, user=None, query=''):
        request = RequestFactory().get('/%s/dossards/%s' % (self.course.uid, query))
        from django.contrib.auth.models import AnonymousUser
        request.user = user or AnonymousUser()
        return admin_views.dossards(request, self.course.uid)

    def test_anonymous_redirected_to_login(self):
        response = self.call()
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_context_is_scoped_to_course_and_ordered(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2, numero=5)
        a = EquipierFactory(equipe=e1, numero=1)
        b = EquipierFactory(equipe=e1, numero=2)
        other = CourseFactory()
        EquipierFactory(equipe=EquipeFactory(course=other, categorie=CategorieFactory(course=other)), numero=1)
        user = User.objects.create_user('u', 'u@example.com', 'x')

        response = self.call(user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context_data['equipiers']), [a, b])

        response = self.call(user, '?order=-numero')
        self.assertEqual(list(response.context_data['equipiers']), [b, a])


class OrganizerAccessTestCase(ExportBaseTestCase):
    PATHS = [
        '/course/document/review/',
        '/course/listing/dossards/',
        '/course/dossards/',
        '/course/anomalies/',
        '/course/anniversaires/',
        '/course/stats/',
        '/course/inscriptions/categorie/test/',
        '/course/inscriptions/equipe/export/',
        '/course/inscriptions/equipe/download/',
    ]

    def test_anonymous_redirected_to_login(self):
        self.client.cookies['course_uid'] = self.course.uid
        for path in self.PATHS:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn('/course/login/', response.url, path)

    def test_user_without_accreditation_redirected_to_login(self):
        user = User.objects.create_user('outsider', 'o@example.com', 'pass1234')
        self.client.force_login(user)
        self.client.cookies['course_uid'] = self.course.uid
        for path in self.PATHS:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn('/course/login/', response.url, path)

    def test_accreditation_for_another_course_does_not_give_access(self):
        other = CourseFactory()
        login_as_organizer(self.client, other)
        self.client.cookies['course_uid'] = self.course.uid  # cookie pointe sur une autre course
        for path in self.PATHS:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn('/course/login/', response.url, path)

    def test_pending_accreditation_without_role_has_no_access(self):
        user = User.objects.create_user('pending', 'p@example.com', 'pass1234')
        Accreditation.objects.create(user=user, course=self.course, role='')
        self.client.force_login(user)
        self.client.cookies['course_uid'] = self.course.uid
        response = self.client.get('/course/anomalies/')
        self.assertEqual(response.status_code, 302)

    def test_post_actions_also_require_access(self):
        self.client.cookies['course_uid'] = self.course.uid
        response = self.client.post('/course/inscriptions/equipe/export/', {
            'ids': '[]', 'objet': 'equipes', 'colonnes': ['equipe.nom'],
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/course/login/', response.url)


class DocumentReviewTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        self.equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2, commentaires='')
        self.q1 = pending_equipier(self.equipe, 1, nom='Premier')
        self.q2 = pending_equipier(self.equipe, 2, nom='Second')
        login_as_organizer(self.client, self.course)

    def test_pending_flags_are_set(self):
        self.assertTrue(self.q1.verifier)
        self.assertIsNone(self.q1.piece_jointe_valide)

    def test_get_shows_first_pending_document(self):
        response = self.client.get('/course/document/review/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['count'], 2)
        self.assertEqual(response.context['index'], 1)
        self.assertEqual(response.context['equipier'], self.q1)
        self.assertEqual(response.context['skip'], '')

    def test_only_pending_documents_of_the_course(self):
        other = CourseFactory()
        other_eq = pending_equipier(
            EquipeFactory(course=other, categorie=CategorieFactory(course=other)), 1)
        EquipierFactory(equipe=self.equipe, numero=3, piece_jointe_valide=True)
        response = self.client.get('/course/document/review/')
        self.assertEqual(response.context['count'], 2)
        self.assertNotEqual(response.context['equipier'], other_eq)

    def test_no_pending_document_redirects_to_dashboard(self):
        Equipier.objects.filter(equipe=self.equipe).delete()
        response = self.client.get('/course/document/review/')
        self.assertRedirects(response, '/course/', fetch_redirect_response=False)

    def test_accept_document_updates_equipier_and_comment(self):
        response = self.client.post('/course/document/review/', {
            'id': self.q1.id, 'value': 'yes', 'skip': '', 'commentaires': 'RAS',
        })
        self.q1.refresh_from_db()
        self.equipe.refresh_from_db()
        self.assertTrue(self.q1.piece_jointe_valide)
        self.assertFalse(self.q1.verifier)
        self.assertTrue(self.q1.valide)
        self.assertFalse(self.q1.certificat_manquant)
        self.assertEqual(self.equipe.commentaires, 'RAS')
        # passe au suivant
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['equipier'], self.q2)
        self.assertEqual(response.context['count'], 1)

    def test_refuse_document_marks_it_invalid(self):
        self.client.post('/course/document/review/', {
            'id': self.q1.id, 'value': 'no', 'skip': '', 'commentaires': 'Illisible',
        })
        self.q1.refresh_from_db()
        self.equipe.refresh_from_db()
        self.assertIs(self.q1.piece_jointe_valide, False)
        self.assertFalse(self.q1.verifier)
        self.assertTrue(self.q1.erreur)
        self.assertTrue(self.q1.certificat_manquant)
        self.assertEqual(self.equipe.commentaires, 'Illisible')

    def test_skip_leaves_equipier_untouched_and_moves_on(self):
        response = self.client.post('/course/document/review/', {
            'id': self.q1.id, 'value': 'skip', 'skip': '', 'commentaires': 'à voir',
        })
        self.q1.refresh_from_db()
        self.assertIsNone(self.q1.piece_jointe_valide)
        self.assertTrue(self.q1.verifier)
        self.assertEqual(response.context['skip'], str(self.q1.id))
        self.assertEqual(response.context['equipier'], self.q2)
        self.assertEqual(response.context['index'], 2)

    def test_skip_list_is_carried_over(self):
        response = self.client.post('/course/document/review/', {
            'id': self.q2.id, 'value': 'skip', 'skip': str(self.q1.id), 'commentaires': '',
        })
        # tout est ignoré : plus rien à relire dans cette session
        self.assertRedirects(response, '/course/', fetch_redirect_response=False)

    def test_last_review_redirects_to_dashboard(self):
        self.client.post('/course/document/review/', {
            'id': self.q1.id, 'value': 'yes', 'skip': '', 'commentaires': '',
        })
        response = self.client.post('/course/document/review/', {
            'id': self.q2.id, 'value': 'yes', 'skip': '', 'commentaires': '',
        })
        self.assertRedirects(response, '/course/', fetch_redirect_response=False)

    def test_cannot_review_equipier_of_another_course(self):
        other = CourseFactory()
        other_eq = pending_equipier(
            EquipeFactory(course=other, categorie=CategorieFactory(course=other)), 1)
        self.client.post('/course/document/review/', {
            'id': other_eq.id, 'value': 'yes', 'skip': '', 'commentaires': 'piraté',
        })
        other_eq.refresh_from_db()
        self.assertIsNone(other_eq.piece_jointe_valide)
        self.assertNotEqual(other_eq.equipe.commentaires, 'piraté')


class ListingDossardsTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        self.e = [EquipeFactory(course=self.course, categorie=self.categorie, numero=n) for n in (1, 5, 12)]
        login_as_organizer(self.client, self.course)

    def test_get_shows_form(self):
        response = self.client.get('/course/listing/dossards/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['course'], self.course)

    def test_post_splits_equipes_in_ranges(self):
        response = self.client.post('/course/listing/dossards/', {'split': '5'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['keys'], ['1 à 4', '5 à 12'])
        self.assertEqual(list(response.context['equipes']['1 à 4']), [self.e[0]])
        self.assertEqual(list(response.context['equipes']['5 à 12']), [self.e[1], self.e[2]][:1] + [self.e[2]])

    def test_post_multiple_splits(self):
        response = self.client.post('/course/listing/dossards/', {'split': '5,12'})
        self.assertEqual(response.context['keys'], ['1 à 4', '5 à 11', '12 à 12'])
        self.assertEqual(list(response.context['equipes']['12 à 12']), [self.e[2]])

    def test_equipes_of_other_course_excluded(self):
        other = CourseFactory()
        EquipeFactory(course=other, categorie=CategorieFactory(course=other), numero=2)
        response = self.client.post('/course/listing/dossards/', {'split': '5'})
        self.assertEqual(list(response.context['equipes']['1 à 4']), [self.e[0]])

    def test_post_without_split_gives_a_single_range(self):
        response = self.client.post('/course/listing/dossards/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['keys'], ['1 à 12'])


class AnomaliesTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        login_as_organizer(self.client, self.course)

    def doublons(self):
        response = self.client.get('/course/anomalies/')
        self.assertEqual(response.status_code, 200)
        return response.context['doublons']

    def test_detects_duplicates_across_teams_ignoring_case_and_accents(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie)
        a = EquipierFactory(equipe=e1, numero=1, nom='Éric-Durand', prenom='Jean')
        b = EquipierFactory(equipe=e2, numero=1, nom='eric durand', prenom='JEAN')
        EquipierFactory(equipe=e2, numero=2, nom='Zzzzzz', prenom='Yyyyyy')

        doublons = self.doublons()
        self.assertEqual(len(doublons), 1)
        self.assertEqual({doublons[0][0].id, doublons[0][1].id}, {a.id, b.id})

    def test_distinct_people_are_not_reported(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie)
        EquipierFactory(equipe=e1, numero=1, nom='Durand', prenom='Jean')
        EquipierFactory(equipe=e2, numero=1, nom='Martinez', prenom='Pierre')
        self.assertEqual(self.doublons(), [])

    def test_inactive_equipiers_beyond_team_size_ignored(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie, nombre=1)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie, nombre=1)
        EquipierFactory(equipe=e1, numero=1, nom='Durand', prenom='Jean')
        EquipierFactory(equipe=e2, numero=2, nom='Durand', prenom='Jean')
        self.assertEqual(self.doublons(), [])

    def test_other_course_duplicates_ignored(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie)
        other = CourseFactory()
        e2 = EquipeFactory(course=other, categorie=CategorieFactory(course=other))
        EquipierFactory(equipe=e1, numero=1, nom='Durand', prenom='Jean')
        EquipierFactory(equipe=e2, numero=1, nom='Durand', prenom='Jean')
        self.assertEqual(self.doublons(), [])


class AnniversairesTestCase(ExportBaseTestCase):
    def test_lists_birthdays_on_race_day_only(self):
        login_as_organizer(self.client, self.course)
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=3)
        happy = EquipierFactory(equipe=equipe, numero=1, nom='Fete',
                                date_de_naissance=self.course.date.replace(year=1992))
        EquipierFactory(equipe=equipe, numero=2, nom='Autrejour', date_de_naissance=date(1992, 1, 2)
                        if (self.course.date.month, self.course.date.day) != (1, 2) else date(1992, 1, 3))
        other = CourseFactory(date=self.course.date)
        EquipierFactory(equipe=EquipeFactory(course=other, categorie=CategorieFactory(course=other)),
                        numero=1, nom='Ailleurs', date_de_naissance=other.date.replace(year=1990))

        response = self.client.get('/course/anniversaires/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['anniversaires']), [happy])
        self.assertContains(response, 'Fete')
        self.assertNotContains(response, 'Autrejour')
        self.assertNotContains(response, 'Ailleurs')


class StatsTestCase(ExportBaseTestCase):
    def setUp(self):
        super().setUp()
        login_as_organizer(self.client, self.course)
        self.equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2)
        EquipierFactory(equipe=self.equipe, numero=1, sexe='H')
        EquipierFactory(equipe=self.equipe, numero=2, sexe='F')

    def test_stats_page(self):
        response = self.client.get('/course/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['course'], self.course)
        self.assertIn(self.course, response.context['courses'])

    def test_stats_page_lists_other_courses_only_for_superuser(self):
        other = CourseFactory()
        response = self.client.get('/course/stats/')
        self.assertEqual(list(response.context['courses_other']), [])
        self.assertNotIn(other, response.context['courses'])

        admin = User.objects.create_superuser('root', 'root@example.com', 'pass1234')
        self.client.force_login(admin)
        response = self.client.get('/course/stats/')
        self.assertIn(other, response.context['courses_other'])

    def test_stats_api_returns_json(self):
        response = self.client.get('/course/stats/%s/' % self.course.uid)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['uid'], self.course.uid)
        self.assertEqual(data['course'], self.course.nom)
        self.assertEqual(set(data['date']), {'ouverture', 'fermeture', 'course'})
        self.assertEqual(len(data['augmentations']), len(self.course.augmentations))
        self.assertEqual(data['delta']['ouverture'], 0)
        self.assertEqual(data['delta']['course'], (self.course.date - self.course.date_ouverture).days)
        totals = {'equipes': 0, 'equipiers': 0}
        for jour in data['stats'].values():
            totals['equipes'] += jour['equipes']
            totals['equipiers'] += jour['equipiers']
        self.assertEqual(totals, {'equipes': 1, 'equipiers': 2})

    def test_stats_api_unknown_course_is_404(self):
        self.assertEqual(self.client.get('/course/stats/nope/').status_code, 404)

    def test_stats_api_requires_login(self):
        self.client.logout()
        self.client.cookies['course_uid'] = self.course.uid
        response = self.client.get('/course/stats/%s/' % self.course.uid)
        self.assertEqual(response.status_code, 302)


class TestCategoriesTestCase(ExportBaseTestCase):
    def test_page_renders_for_organizer(self):
        login_as_organizer(self.client, self.course)
        response = self.client.get('/course/inscriptions/categorie/test/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['course'], self.course)


class EquipeExportTestCase(ExportBaseTestCase):
    URL = '/course/inscriptions/equipe/export/'

    def setUp(self):
        super().setUp()
        login_as_organizer(self.client, self.course)
        self.e1 = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2, nom='Alpha')
        self.q11 = EquipierFactory(equipe=self.e1, numero=1, nom='Durand', prenom='Anne')
        self.q12 = EquipierFactory(equipe=self.e1, numero=2, nom='Petit', prenom='Paul')
        EquipierFactory(equipe=self.e1, numero=3, nom='Reste')
        self.e2 = EquipeFactory(course=self.course, categorie=self.categorie, nombre=1, nom='Béta')
        self.q21 = EquipierFactory(equipe=self.e2, numero=1, nom='Moreau', prenom='Zoé')

    def post(self, **overrides):
        data = {
            'ids': '[]', 'objet': 'equipes', 'colonnes': ['equipe.nom', 'categorie.code'],
        }
        data.update(overrides)
        return self.client.post(self.URL, data)

    def test_get_shows_export_form(self):
        ExtraQuestionFactory(course=self.course, page='Equipe', label='Taille T-shirt')
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['equipes'], 2)
        self.assertEqual(response.context['equipiers'], 3)
        self.assertIn('equipe.nom', response.context['fields'])
        self.assertIn('categorie.code', response.context['fields'])
        self.assertIn('equipier.nom', response.context['fields'])
        self.assertIn('Equipe - Taille T-shirt', response.context['fields'].values())

    def test_equipes_export_all_with_header(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename=equipes.csv')
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8')), delimiter=';'))
        self.assertEqual(rows[0], ["Equipe - Nom d'équipe", 'Catégorie - Code'])
        self.assertCountEqual(rows[1:], [
            ['Alpha', self.categorie.code], ['Béta', self.categorie.code],
        ])

    def test_equipes_export_filtered_by_ids(self):
        response = self.post(ids=json.dumps([self.e2.id]))
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8')), delimiter=';'))
        self.assertEqual(rows[1:], [['Béta', self.categorie.code]])

    def test_ids_of_another_course_are_ignored(self):
        other = CourseFactory()
        foreign = EquipeFactory(course=other, categorie=CategorieFactory(course=other), nom='Etrangere')
        response = self.post(ids=json.dumps([foreign.id]))
        self.assertNotIn('Etrangere', response.content.decode('utf-8'))
        response = self.post()
        self.assertNotIn('Etrangere', response.content.decode('utf-8'))

    def test_equipiers_export_skips_inactive_and_resolves_related_columns(self):
        response = self.post(
            objet='equipiers', delimiter=',', name='joueurs',
            colonnes=['equipe.nom', 'equipier.nom', 'equipier.prenom', 'equipier.numero',
                      'categorie.code'],
        )
        self.assertEqual(response['Content-Disposition'], 'attachment; filename=joueurs.csv')
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        self.assertEqual(rows[0][0], "Equipe - Nom d'équipe")
        self.assertCountEqual(rows[1:], [
            ['Alpha', 'Durand', 'Anne', '1', self.categorie.code],
            ['Alpha', 'Petit', 'Paul', '2', self.categorie.code],
            ['Béta', 'Moreau', 'Zoé', '1', self.categorie.code],
        ])

    def test_equipiers_export_filtered_by_equipe_ids(self):
        response = self.post(objet='equipiers', ids=json.dumps([self.e2.id]),
                             colonnes=['equipier.nom'])
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8')), delimiter=';'))
        self.assertEqual(rows[1:], [['Moreau']])

    def test_equipes_export_drops_equipier_columns(self):
        response = self.post(colonnes=['equipe.nom', 'equipier.nom'])
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8')), delimiter=';'))
        self.assertEqual(rows[0], ["Equipe - Nom d'équipe"])

    def test_extra_question_columns(self):
        q = ExtraQuestionFactory(course=self.course, page='Equipe', label='Taille')
        self.e1.extra = {'extra%d' % q.id: 'XL'}
        self.e1.save()
        key = 'equipe.extra%d' % q.id
        response = self.post(colonnes=['equipe.nom', key])
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8')), delimiter=';'))
        self.assertEqual(rows[0], ["Equipe - Nom d'équipe", 'Equipe - Taille'])
        self.assertCountEqual(rows[1:], [['Alpha', 'XL'], ['Béta', '']])

    def test_encoding_and_delimiter(self):
        response = self.post(encoding='iso-8859-1', delimiter='|', colonnes=['equipe.nom', 'categorie.code'])
        text = response.content.decode('iso-8859-1')
        self.assertIn('Béta|', text)

    def test_unencodable_data_characters_are_replaced(self):
        self.e2.nom = 'Ω'
        self.e2.save()
        response = self.post(encoding='iso-8859-1', colonnes=['categorie.code', 'equipe.nom'])
        self.assertEqual(response.status_code, 200)
        self.assertIn(';?', response.content.decode('iso-8859-1'))

    def test_unencodable_header_characters_are_replaced(self):
        # l'en-tête n'est pas passé par encode(..., 'replace') comme les données : 500
        response = self.post(encoding='ascii', colonnes=['equipe.nom'])
        self.assertEqual(response.status_code, 200)

    def test_header_can_be_disabled(self):
        response = self.post(header='no', colonnes=['equipe.nom'])
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8')), delimiter=';'))
        self.assertNotIn(["Equipe - Nom d'équipe"], rows)

    def test_action_on_changelist_redirects_to_export_form(self):
        # l'action « Exporter » du changelist passe la sélection au formulaire
        response = self.client.post('/course/inscriptions/equipe/', {
            'action': 'export', '_selected_action': [self.e1.id],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['equipes'], 1)
        self.assertEqual(response.context['equipiers'], 2)


class EquipeDownloadTestCase(ExportBaseTestCase):
    URL = '/course/inscriptions/equipe/download/'

    def zip_from(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        return zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content)))

    def test_zip_contains_justificatifs_and_parental_authorizations(self):
        login_as_organizer(self.client, self.course)
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2, nom='A/B')
        EquipierFactory(
            equipe=equipe, numero=1, nom='Durand', prenom='Anne', justificatif='licence',
            piece_jointe=SimpleUploadedFile('lic.pdf', b'licence-content'),
        )
        EquipierFactory(
            equipe=equipe, numero=2, nom='Petit', prenom='Paul', date_de_naissance=date(2015, 1, 1),
            autorisation=SimpleUploadedFile('aut.png', b'autorisation-content'),
        )
        EquipierFactory(equipe=equipe, numero=3, nom='Sans', prenom='Piece')

        response = self.client.get(self.URL)

        self.assertIn('Justificatifs de 1 equipes.zip', response['Content-Disposition'])
        self.assertIn(self.course.nom, response['Content-Disposition'])
        z = self.zip_from(response)
        n = equipe.numero
        self.assertCountEqual(z.namelist(), [
            '%d - A_B/%d1 - Anne Durand - licence.pdf' % (n, n),
            '%d - A_B/%d2 - Paul Petit - autorisation parentale.png' % (n, n),
        ])
        self.assertEqual(z.read('%d - A_B/%d1 - Anne Durand - licence.pdf' % (n, n)), b'licence-content')
        self.assertEqual(
            z.read('%d - A_B/%d2 - Paul Petit - autorisation parentale.png' % (n, n)), b'autorisation-content')

    def test_zip_only_contains_files_of_the_current_course(self):
        login_as_organizer(self.client, self.course)
        other = CourseFactory()
        other_equipe = EquipeFactory(course=other, categorie=CategorieFactory(course=other), nom='Etrangere')
        EquipierFactory(equipe=other_equipe, numero=1,
                        piece_jointe=SimpleUploadedFile('x.pdf', b'secret'))
        z = self.zip_from(self.client.get(self.URL))
        self.assertEqual(z.namelist(), [])

    def test_missing_file_on_disk_is_skipped(self):
        login_as_organizer(self.client, self.course)
        equipe = EquipeFactory(course=self.course, categorie=self.categorie)
        EquipierFactory(equipe=equipe, numero=1, piece_jointe='inexistant/fichier.pdf')
        z = self.zip_from(self.client.get(self.URL))
        self.assertEqual(z.namelist(), [])

    def test_changelist_action_restricts_to_selected_equipes(self):
        login_as_organizer(self.client, self.course)
        e1 = EquipeFactory(course=self.course, categorie=self.categorie, nom='Une')
        e2 = EquipeFactory(course=self.course, categorie=self.categorie, nom='Deux')
        EquipierFactory(equipe=e1, numero=1, prenom='A', nom='B',
                        piece_jointe=SimpleUploadedFile('a.pdf', b'1'))
        EquipierFactory(equipe=e2, numero=1, prenom='C', nom='D',
                        piece_jointe=SimpleUploadedFile('c.pdf', b'2'))
        response = self.client.post('/course/inscriptions/equipe/', {
            'action': 'download', '_selected_action': [e2.id],
        })
        z = self.zip_from(response)
        self.assertEqual(len(z.namelist()), 1)
        self.assertIn('Deux', z.namelist()[0])
        self.assertIn('Justificatifs de 1 equipes', response['Content-Disposition'])
