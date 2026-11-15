"""Tests of the public, read-only(ish) pages of `inscriptions/views.py`.

Challenge views rely on Postgres-only SQL functions (`CompareNames`), hence
this module runs through docker-compose like the others.
"""
import json
import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from inscriptions.factories import CategorieFactory, CourseEntiteFactory, CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.models import (
    Accreditation, Challenge, Course, ChallengeCategorie, ParticipationChallenge,
)
from inscriptions.tests.base import BaseTestCase, equipier_formset_data


def template_names(response):
    return [t.name for t in response.templates if t.name]


class IndexTestCase(BaseTestCase):
    def test_lists_active_courses_split_between_current_and_archived(self):
        futur = CourseFactory(nom='Course Futur', date=date.today() + timedelta(days=30))
        passee = CourseFactory(nom='Course Passee', date=date.today() - timedelta(days=30))
        Course.objects.filter(pk=passee.course_id).update(archive=True)
        inactive = CourseFactory(nom='Course Inactive', active=False)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('index.html', template_names(response))
        self.assertEqual(list(response.context['courses']), [futur.course])
        self.assertEqual(list(response.context['anciennes_courses']), [passee.course])
        self.assertContains(response, 'Course Futur')
        self.assertContains(response, 'Course Passee')
        self.assertNotContains(response, inactive.nom)

    def test_orders_by_last_edition_date_desc(self):
        c2 = CourseFactory(date=date.today() + timedelta(days=90))
        c1 = CourseFactory(date=date.today() + timedelta(days=10))
        response = self.client.get(reverse('home'))
        self.assertEqual(list(response.context['courses']), [c2.course, c1.course])

    def test_empty(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['courses']), [])

    def test_une_seule_edition_ouverte_lien_direct(self):
        edition = CourseFactory(nom='Seule', uid='2026')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'href="/%s/"' % edition.key)
        self.assertNotContains(response, 'data-toggle="modal"')

    def test_plusieurs_editions_ouvertes_un_bouton_et_une_popup(self):
        course = CourseEntiteFactory(nom='GrandeCourse', uid='grande')
        e6 = CourseFactory(course=course, uid='2026', nom='Edition 6h')
        e3 = CourseFactory(course=course, uid='2026-3h', nom='Edition 3h')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.content.decode().count('data-toggle="modal"'), 1)
        self.assertContains(response, 'Edition 6h')
        self.assertContains(response, 'Edition 3h')
        self.assertContains(response, 'href="/%s/"' % e6.key)
        self.assertContains(response, 'href="/%s/"' % e3.key)
        self.assertEqual(list(response.context['courses']), [course])

    def test_edition_non_publiee_absente(self):
        course = CourseEntiteFactory(uid='brouillon')
        CourseFactory(course=course, uid='2026', nom='Brouillon 2026', active=False)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'Brouillon 2026')
        self.assertEqual(list(response.context['courses']), [])
        self.assertEqual(list(response.context['anciennes_courses']), [])

    def test_inscriptions_pas_encore_ouvertes_affiche_la_date_d_ouverture(self):
        CourseFactory(date_ouverture=date.today() + timedelta(days=10),
                      date_fermeture=date.today() + timedelta(days=40))
        response = self.client.get(reverse('home'))
        self.assertContains(response, "Ouverture des inscriptions le")
        self.assertNotContains(response, 'data-toggle="modal"')


class CoursePageTestCase(BaseTestCase):
    def test_liste_les_editions_publiees(self):
        course = CourseEntiteFactory(uid='lacourse', nom='La Course')
        CourseFactory(course=course, uid='2024', nom='Edition 2024', date=date.today() - timedelta(days=700))
        CourseFactory(course=course, uid='2026', nom='Edition 2026')
        CourseFactory(course=course, uid='2027', nom='Edition 2027 brouillon', active=False)
        response = self.client.get('/lacourse/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edition 2024')
        self.assertContains(response, 'Edition 2026')
        self.assertNotContains(response, 'brouillon')
        self.assertContains(response, 'href="/lacourse/2026/list/"')

    def test_course_inactive_ou_inconnue_404(self):
        CourseFactory(uid='masquee', active=False)  # edition active, course.active=True par defaut
        inactive = CourseEntiteFactory(uid='inactivecourse', active=False)
        CourseFactory(course=inactive, uid='2026')
        self.assertEqual(self.client.get('/inactivecourse/').status_code, 404)
        self.assertEqual(self.client.get('/inconnue/').status_code, 404)

    def test_course_sans_edition_publiee_404(self):
        CourseFactory(course=CourseEntiteFactory(uid='videe'), uid='2026', active=False)
        self.assertEqual(self.client.get('/videe/').status_code, 404)


class EquipeListTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='list')
        self.cat_a = CategorieFactory(course=self.course, code='AAA', nom='Cat A', numero_debut=0, numero_fin=99)
        self.cat_b = CategorieFactory(course=self.course, code='BBB', nom='Cat B', numero_debut=100, numero_fin=199)
        self.e1 = EquipeFactory(course=self.course, categorie=self.cat_a, nom='Zebres', club='Club Z')
        self.e2 = EquipeFactory(course=self.course, categorie=self.cat_b, nom='Alpagas', club='Club A')
        self.e3 = EquipeFactory(course=self.course, categorie=self.cat_a, nom='Mouettes', club='Club M')
        self.url = reverse('inscriptions_list', kwargs={'course_uid': 'list/list'})

    def names(self, response):
        return [e.nom for e in response.context['equipes']]

    def test_default_sort_is_by_date(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('list.html', template_names(response))
        self.assertEqual(self.names(response), ['Zebres', 'Alpagas', 'Mouettes'])
        self.assertContains(response, 'Zebres')
        self.assertFalse(response.context['user_is_staff'])
        self.assertFalse(response.context['split_categories'])

    def test_sort_by_nom_and_reverse(self):
        response = self.client.get(self.url, {'sort': 'nom'})
        self.assertEqual(self.names(response), ['Alpagas', 'Mouettes', 'Zebres'])
        response = self.client.get(self.url, {'sort': '-nom'})
        self.assertEqual(self.names(response), ['Zebres', 'Mouettes', 'Alpagas'])

    def test_sort_by_numero(self):
        response = self.client.get(self.url, {'sort': '-numero'})
        self.assertEqual(self.names(response)[0], 'Alpagas')  # numero 100+ in cat B

    def test_invalid_sort_falls_back_to_default(self):
        response = self.client.get(self.url, {'sort': 'password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.names(response), ['Zebres', 'Alpagas', 'Mouettes'])

    def test_by_categories_groups_by_category_code(self):
        response = self.client.get(self.url, {'by_categories': '1', 'sort': 'nom'})
        self.assertTrue(response.context['split_categories'])
        self.assertEqual(self.names(response), ['Mouettes', 'Zebres', 'Alpagas'])
        self.assertContains(response, 'AAA - Cat A')
        self.assertContains(response, 'BBB - Cat B')

    def test_filter_by_categorie(self):
        response = self.client.get(self.url, {'categorie': 'BBB'})
        self.assertEqual(self.names(response), ['Alpagas'])

    def test_search_on_nom_and_club(self):
        response = self.client.get(self.url, {'search': 'alpa'})
        self.assertEqual(self.names(response), ['Alpagas'])
        response = self.client.get(self.url, {'search': 'club m'})
        self.assertEqual(self.names(response), ['Mouettes'])

    def test_top_filters_on_position_and_ignores_garbage(self):
        EquipeFactory._meta.model.objects.filter(pk=self.e1.pk).update(position_generale=1, position_categorie=1)
        EquipeFactory._meta.model.objects.filter(pk=self.e2.pk).update(position_generale=2, position_categorie=1)
        EquipeFactory._meta.model.objects.filter(pk=self.e3.pk).update(position_generale=3, position_categorie=2)
        response = self.client.get(self.url, {'top': '2', 'sort': 'nom'})
        self.assertEqual(self.names(response), ['Alpagas', 'Zebres'])
        response = self.client.get(self.url, {'top': '1', 'by_categories': '1', 'sort': 'nom'})
        self.assertEqual(self.names(response), ['Zebres', 'Alpagas'])
        response = self.client.get(self.url, {'top': 'abc'})
        self.assertEqual(len(self.names(response)), 3)

    def test_stats_for_anonymous(self):
        response = self.client.get(self.url)
        stats = response.context['stats']
        self.assertEqual(stats['count'], 3)
        self.assertEqual(stats['club'], 3)
        self.assertNotIn('prix', stats)

    def test_only_this_courses_teams_are_listed(self):
        other = EquipeFactory(nom='Autre Course Equipe')
        response = self.client.get(self.url)
        self.assertNotIn(other.nom, self.names(response))
        self.assertNotContains(response, 'Autre Course Equipe')

    def test_unknown_course_is_404(self):
        # BUG: no `get_object_or_404` on the course: the template is rendered
        # without `COURSE` and crashes (HTTP 500) instead of returning 404.
        response = self.client.get(reverse('inscriptions_list', kwargs={'course_uid': 'nope/nope'}))
        self.assertEqual(response.status_code, 404)

    def test_staff_with_accreditation_sees_payment_stats(self):
        user = User.objects.create_user('orga', 'orga@example.com', 'pw', is_staff=True)
        Accreditation.objects.create(user=user, course=self.course.course, role='organisateur')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user_is_staff'])
        stats = response.context['stats']
        self.assertEqual(stats['prix'], Decimal('120.00'))
        self.assertEqual(stats['equipiers'], 3)

    def test_staff_without_accreditation_on_course_is_not_staff_here(self):
        user = User.objects.create_user('orga2', 'orga2@example.com', 'pw', is_staff=True)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user_is_staff'])
        self.assertNotIn('prix', response.context['stats'])


class StatsTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='stats1', dates_augmentation=[date.today() + timedelta(days=10)])
        self.cat = CategorieFactory(course=self.course)
        equipe = EquipeFactory(course=self.course, categorie=self.cat, club='Club S')
        EquipierFactory(equipe=equipe, numero=1)

    def test_stats_page(self):
        response = self.client.get(reverse('inscriptions_stats', kwargs={'course_uid': 'stats1/stats1'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('stats.html', template_names(response))
        self.assertEqual(response.context['course'], self.course)
        stats = response.context['stats']
        self.assertEqual(stats['course']['equipes'], 1)
        self.assertEqual(json.loads(response.context['json'])['course']['equipes'], 1)

    def test_stats_unknown_course_is_404(self):
        response = self.client.get(reverse('inscriptions_stats', kwargs={'course_uid': 'nope/nope'}))
        self.assertEqual(response.status_code, 404)

    def _other_course(self, uid='stats2', **kw):
        course = CourseFactory(
            uid=uid,
            date=self.course.date - timedelta(days=365),
            date_ouverture=self.course.date_ouverture - timedelta(days=365),
            date_fermeture=self.course.date_fermeture - timedelta(days=365),
            dates_augmentation=[self.course.date - timedelta(days=365 + 10)],
            **kw)
        CategorieFactory(course=course)
        return course

    def test_stats_compare(self):
        self._other_course()
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'stats1/stats1', 'course_uid2': 'stats2/stats2'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('stats_compare.html', template_names(response))
        data = response.context['data']
        self.assertEqual([d['index'] for d in data], [0, 1])
        self.assertEqual([d['course'].uid for d in data], ['stats1', 'stats2'])
        self.assertEqual(data[0]['delta'], 0)
        self.assertEqual(response.context['align'], '')

    def test_stats_compare_align_start_and_augment(self):
        self._other_course()
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'stats1/stats1', 'course_uid2': 'stats2/stats2'})
        response = self.client.get(url, {'align': 'start'})
        self.assertEqual([d['delta'] for d in response.context['data']], [0, 0])
        response = self.client.get(url, {'align': 'augment'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['align'], 'augment')
        self.assertEqual(response.context['data'][0]['delta'], 0)

    def test_stats_compare_unknown_course_is_404(self):
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'stats1/stats1', 'course_uid2': 'nope/nope'})
        self.assertEqual(self.client.get(url).status_code, 404)
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'nope/nope', 'course_uid2': 'stats1/stats1'})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_stats_compare_course_without_augmentation_date(self):
        # BUG: `course.dates_augmentation[0]` is indexed unconditionally, but
        # the field defaults to `[]` -> IndexError (HTTP 500) for any course
        # without a price increase date.
        CourseFactory(uid='noaug')
        url = reverse('inscriptions_stats_compare', kwargs={'course_uid': 'stats1/stats1', 'course_uid2': 'noaug/noaug'})
        self.assertEqual(self.client.get(url).status_code, 200)


class CategoriesTestCase(BaseTestCase):
    def test_categories_page(self):
        course = CourseFactory(uid='cats')
        CategorieFactory(course=course, code='GRD', nom='Grand', min_equipiers=4, max_equipiers=6)
        CategorieFactory(course=course, code='SOL', nom='Solo', min_equipiers=1, max_equipiers=1)
        CategorieFactory(nom='Categorie Autre Course')
        response = self.client.get(reverse('categories', kwargs={'course_uid': 'cats/cats'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('categories.html', template_names(response))
        self.assertEqual(response.context['course'], course)
        self.assertEqual([c.code for c in response.context['categories']], ['SOL', 'GRD'])
        self.assertContains(response, 'Solo')
        self.assertNotContains(response, 'Categorie Autre Course')
        self.assertIn('mixite_choices', response.context)

    def test_unknown_course_is_404(self):
        self.assertEqual(self.client.get(reverse('categories', kwargs={'course_uid': 'nope/nope'})).status_code, 404)


class CheckNameTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='chk')
        self.equipe = EquipeFactory(course=self.course, nom='Les Rapides',
                                    categorie=CategorieFactory(course=self.course))
        self.url = reverse('inscriptions_check_name', kwargs={'course_uid': 'chk/chk'})

    def test_counts_same_name_case_insensitive(self):
        response = self.client.post(self.url, {'nom': 'les rapides', 'id': '0'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'1')
        self.assertEqual(response['Content-Type'], 'text/plain')

    def test_free_name(self):
        response = self.client.post(self.url, {'nom': 'Autre', 'id': '0'})
        self.assertEqual(response.content, b'0')

    def test_own_id_is_excluded(self):
        response = self.client.post(self.url, {'nom': 'Les Rapides', 'id': str(self.equipe.id)})
        self.assertEqual(response.content, b'0')

    def test_same_name_in_other_course_does_not_count(self):
        EquipeFactory(nom='Les Rapides')
        response = self.client.post(self.url, {'nom': 'Les Rapides', 'id': '0'})
        self.assertEqual(response.content, b'1')

    def test_missing_parameters_is_422(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 422)

    def test_missing_id_only_is_422(self):
        # BUG: the guard uses `and` so a request with `nom` but no `id` passes
        # it, then `request.POST['id']` raises MultiValueDictKeyError (500).
        self.assertEqual(self.client.post(self.url, {'nom': 'x'}).status_code, 422)


class ChangeTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='chg')
        # numero_debut=1: a team numbered 0 is falsy in `change()` and would hit the list page
        self.cat = CategorieFactory(course=self.course, numero_debut=1)
        self.e1 = EquipeFactory(course=self.course, categorie=self.cat, nom='Premiers')
        self.e2 = EquipeFactory(course=self.course, categorie=self.cat, nom='Seconds')
        self.url = reverse('inscriptions_change', kwargs={'course_uid': 'chg/chg'})

    def test_list_of_teams(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('change.html', template_names(response))
        self.assertIsNone(response.context['sent'])
        self.assertEqual([e.nom for e in response.context['equipes']], ['Premiers', 'Seconds'])
        self.assertContains(response, 'Premiers')
        self.assertNotContains(response, 'Un email vient de vous être envoyé')

    def test_sent_variant_shows_notice(self):
        response = self.client.get('/chg/chg/change/sent/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['sent'])
        self.assertContains(response, 'Un email vient de vous être envoyé')

    def test_question_page(self):
        response = self.client.get(reverse('inscriptions_change', kwargs={'course_uid': 'chg/chg', 'numero': self.e1.numero}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('change_numero.html', template_names(response))
        self.assertEqual(response.context['equipe'], self.e1)

    def test_unknown_numero_is_404(self):
        response = self.client.get(reverse('inscriptions_change', kwargs={'course_uid': 'chg/chg', 'numero': 9999}))
        self.assertEqual(response.status_code, 404)

    def test_numero_of_other_course_is_404(self):
        other_cat = CategorieFactory(numero_debut=500, numero_fin=599)
        other = EquipeFactory(course=other_cat.course, categorie=other_cat)
        self.assertEqual(other.numero, 500)
        response = self.client.get(reverse('inscriptions_change', kwargs={'course_uid': 'chg/chg', 'numero': 500}))
        self.assertEqual(response.status_code, 404)

    def test_wrong_answer_sends_nothing(self):
        with mock.patch('inscriptions.models.Equipe.send_mail') as send_mail:
            response = self.client.post(
                reverse('inscriptions_change', kwargs={'course_uid': 'chg/chg', 'numero': self.e1.numero}),
                {'question': '8'})
        self.assertEqual(response.status_code, 200)
        send_mail.assert_not_called()

    def test_right_answer_sends_change_request_mail(self):
        url = reverse('inscriptions_change', kwargs={'course_uid': 'chg/chg', 'numero': self.e1.numero})
        # the redirect afterwards is broken (see next test): don't let it
        # hide the part under test here
        with mock.patch('inscriptions.models.Equipe.send_mail') as send_mail:
            try:
                self.client.post(url, {'question': '7'})
            except Exception:  # broken redirect, see next test
                pass
        send_mail.assert_called_once_with('change_request')

    def test_right_answer_redirects_to_sent_page(self):
        # BUG: the view redirects to the URL name 'inscriptions_change_sent'
        # but urls.py registers it as 'inscriptions.change_sent' (dot) ->
        # NoReverseMatch (500) after the mail was sent.
        url = reverse('inscriptions_change', kwargs={'course_uid': 'chg/chg', 'numero': self.e1.numero})
        with mock.patch('inscriptions.models.Equipe.send_mail'):
            response = self.client.post(url, {'question': '7'})
        self.assertRedirects(response, '/chg/chg/change/sent/', fetch_redirect_response=False)


class StaticishPagesTestCase(BaseTestCase):
    def test_model_certificat_redirects_to_pdf(self):
        course = CourseFactory(uid='cert')
        response = self.client.get(reverse('inscriptions_model_certificat', kwargs={'course_uid': course.key}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith('certificat_medical.pdf'))

    def test_model_autorisation(self):
        CourseFactory(uid='auto')
        response = self.client.get(reverse('inscriptions_model_autorisation', kwargs={'course_uid': 'auto/auto'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('autorisation.html', template_names(response))

    def test_countries(self):
        response = self.client.get(reverse('countries'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = dict(json.loads(response.content))
        self.assertIn('FR', data)
        self.assertEqual(data['FR'], 'France')
        self.assertGreater(len(data), 200)

    def test_blank_gif(self):
        root = tempfile.mkdtemp(prefix='enduroller-tests-static-')
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        gif = b'GIF89a\x01\x00\x01\x00\x00\x00\x00;'
        with open(os.path.join(root, 'blank.gif'), 'wb') as f:
            f.write(gif)
        with override_settings(STATIC_ROOT=root):
            response = self.client.get(reverse('inscriptions_blank'))
            body = b''.join(response.streaming_content) if response.streaming else response.content
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/gif')
        self.assertEqual(body, gif)

    def test_signup_page(self):
        response = self.client.get(reverse('account_signup'))
        self.assertEqual(response.status_code, 200)
        from inscriptions.forms import SignupForm
        self.assertIsInstance(response.context['form'], SignupForm)
        self.assertIn('turnstile', response.context['form'].fields)

    def test_signup_post_without_captcha_is_rejected(self):
        response = self.client.post(reverse('account_signup'), {
            'username': 'nouveau', 'email': 'n@example.com',
            'password': 'Sup3rSecret!', 'password_confirm': 'Sup3rSecret!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='nouveau').exists())


class FindChallengesCategoriesTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='fcc')
        self.cat = CategorieFactory(course=self.course, code='SOLOH', sexe='H', min_age=18)
        self.challenge = Challenge.objects.create(nom='Challenge FCC', uid='chalfcc', mode='nord2018', active=True)
        self.challenge.courses.add(self.course)
        self.cc = ChallengeCategorie.objects.create(
            challenge=self.challenge, nom='Solo Homme', code='CSOLOH',
            min_equipiers=1, max_equipiers=1, min_age=18, sexe='H', validation='')
        self.cc.categories.add(self.cat)
        self.url = reverse('inscriptions_find_challenges_categories', kwargs={'course_uid': 'fcc/fcc'})

    def _post_data(self, **kw):
        data = equipier_formset_data([{
            'nom': 'Dupont', 'prenom': 'Jean', 'sexe': 'H', 'date_de_naissance': date(1990, 1, 1),
        }])
        data.update({'nombre': '1', 'nom': 'Equipe FCC', 'categories': ['SOLOH']})
        data.update(kw)
        return data

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_unknown_course_is_404(self):
        url = reverse('inscriptions_find_challenges_categories', kwargs={'course_uid': 'nope/nope'})
        self.assertEqual(self.client.post(url, self._post_data()).status_code, 404)

    def test_closed_course_shows_closed_page_to_anonymous(self):
        CourseFactory(uid='fccclosed', date_fermeture=date.today() - timedelta(days=1))
        url = reverse('inscriptions_find_challenges_categories', kwargs={'course_uid': 'fccclosed/fccclosed'})
        response = self.client.post(url, self._post_data())
        self.assertEqual(response.status_code, 200)
        self.assertIn('closed.html', template_names(response))

    def test_not_yet_open_course(self):
        CourseFactory(uid='fccfuture', date_ouverture=date.today() + timedelta(days=5))
        url = reverse('inscriptions_find_challenges_categories', kwargs={'course_uid': 'fccfuture/fccfuture'})
        response = self.client.post(url, self._post_data())
        self.assertIn('not_opened_yet.html', template_names(response))

    def test_invalid_formset_is_400_with_errors(self):
        data = self._post_data()
        data['form-0-nom'] = ''
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertTrue(json.loads(response.content)[0])

    def test_returns_rendered_participation_per_category_code(self):
        response = self.client.post(self.url, self._post_data())
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(list(result.keys()), ['SOLOH'])
        self.assertEqual(len(result['SOLOH']), 1)
        self.assertIn('Challenge FCC', result['SOLOH'][0])

    def test_no_matching_challenge_category(self):
        data = self._post_data()
        data['form-0-sexe'] = 'F'
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {})


class ChallengeViewsTestCase(BaseTestCase):
    """Public challenge pages. Needs Postgres (CompareNames)."""

    def setUp(self):
        super().setUp()
        past = date.today() - timedelta(days=100)
        self.course_a = CourseFactory(uid='cha', date=past - timedelta(days=30), distance=Decimal('10.0'))
        self.course_b = CourseFactory(uid='chb', date=past, distance=Decimal('10.0'))
        self.cat_a = CategorieFactory(course=self.course_a, code='SA', sexe='H', min_age=18)
        self.cat_b = CategorieFactory(course=self.course_b, code='SB', sexe='H', min_age=18)

        self.challenge = Challenge.objects.create(nom='Grand Challenge', uid='grandchal', mode='nord2018', active=True)
        self.challenge.courses.add(self.course_a, self.course_b)
        self.cc = ChallengeCategorie.objects.create(
            challenge=self.challenge, nom='Solo Homme', code='CSOLOH',
            min_equipiers=1, max_equipiers=1, min_age=18, sexe='H', validation='')
        self.cc.categories.add(self.cat_a, self.cat_b)

        self.equipe_a = self._solo(self.course_a, self.cat_a, 'Dupont', 'Equipe Dupont', position=1)
        self.equipe_b = self._solo(self.course_b, self.cat_b, 'Dupont', 'Equipe Dupont', position=1)
        self.equipe_c = self._solo(self.course_a, self.cat_a, 'Martin', 'Equipe Martin', position=2)
        self.p_dupont = self.challenge.inscription_equipe(self.equipe_a)
        self.challenge.inscription_equipe(self.equipe_b)
        self.p_martin = self.challenge.inscription_equipe(self.equipe_c)
        self.challenge.compute_course(self.course_a)
        self.challenge.compute_course(self.course_b)
        self.challenge.compute_challenge()

    def _solo(self, course, cat, nom, equipe_nom, position):
        equipe = EquipeFactory(course=course, categorie=cat, nombre=1, nom=equipe_nom)
        EquipierFactory(equipe=equipe, numero=1, nom=nom, prenom='Jean', sexe='H',
                        date_de_naissance=date(1990, 1, 1))
        type(equipe).objects.filter(pk=equipe.pk).update(position_generale=position, position_categorie=position, tours=10)
        equipe.refresh_from_db()
        return equipe

    # --- challenges list
    def test_challenges_list_splits_upcoming_and_past(self):
        futur_course = CourseFactory(uid='chfut', date=date.today() + timedelta(days=30))
        upcoming = Challenge.objects.create(nom='Challenge A Venir', uid='avenir', mode='nord2018', active=True)
        upcoming.courses.add(futur_course)
        Challenge.objects.create(nom='Challenge Inactif', uid='inactif', mode='nord2018', active=False)

        response = self.client.get(reverse('inscriptions_challenges'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('challenges.html', template_names(response))
        self.assertEqual(response.context['prochains_challenges'], [upcoming])
        self.assertEqual(response.context['anciens_challenges'], [self.challenge])
        self.assertNotContains(response, 'Challenge Inactif')
        self.assertContains(response, 'Grand Challenge')

    # --- challenge ranking
    def _url(self):
        return reverse('inscriptions_challenge', kwargs={'challenge_uid': 'grandchal'})

    def _noms(self, response):
        return [p.nom for p in response.context['participations']]

    def test_challenge_ranking(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('resultats_challenge.html', template_names(response))
        self.assertEqual(response.context['challenge'], self.challenge)
        # Dupont: 2 races (15 + 15 pts) ahead of Martin (12 pts)
        self.assertEqual(self._noms(response), ['Equipe Dupont', 'Equipe Martin'])
        first = response.context['participations'][0]
        self.assertEqual(first.count, 2)
        self.assertEqual(first.points, 30)
        self.assertEqual(first.distance, Decimal('200.0'))
        self.assertContains(response, 'Equipe Dupont')

    def test_challenge_unknown_is_404(self):
        response = self.client.get(reverse('inscriptions_challenge', kwargs={'challenge_uid': 'nope'}))
        self.assertEqual(response.status_code, 404)

    def test_challenge_sort_and_reverse(self):
        response = self.client.get(self._url(), {'sort': '-nom'})
        self.assertEqual(self._noms(response), ['Equipe Martin', 'Equipe Dupont'])
        response = self.client.get(self._url(), {'sort': 'nom'})
        self.assertEqual(self._noms(response), ['Equipe Dupont', 'Equipe Martin'])

    def test_challenge_sort_by_distance(self):
        response = self.client.get(self._url(), {'sort': '-distance'})
        self.assertEqual(self._noms(response), ['Equipe Dupont', 'Equipe Martin'])
        response = self.client.get(self._url(), {'sort': 'distance'})
        self.assertEqual(self._noms(response), ['Equipe Martin', 'Equipe Dupont'])

    def test_challenge_invalid_sort_falls_back(self):
        response = self.client.get(self._url(), {'sort': 'bogus'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._noms(response), ['Equipe Dupont', 'Equipe Martin'])

    def test_challenge_search_filter_category_top(self):
        response = self.client.get(self._url(), {'search': 'martin'})
        self.assertEqual(self._noms(response), ['Equipe Martin'])
        response = self.client.get(self._url(), {'categorie': 'CSOLOH'})
        self.assertEqual(len(self._noms(response)), 2)
        response = self.client.get(self._url(), {'categorie': 'AUTRE'})
        self.assertEqual(self._noms(response), [])
        response = self.client.get(self._url(), {'top': '1'})
        self.assertEqual(self._noms(response), ['Equipe Dupont'])
        response = self.client.get(self._url(), {'top': 'x'})
        self.assertEqual(len(self._noms(response)), 2)
        response = self.client.get(self._url(), {'by_categories': '1'})
        self.assertTrue(response.context['split_categories'])

    def test_challenge_hides_empty_participations(self):
        ParticipationChallenge.objects.create(challenge=self.challenge, nom='Fantome', categorie=self.cc)
        response = self.client.get(self._url())
        self.assertNotIn('Fantome', self._noms(response))

    # --- participation detail
    def test_challenge_participation_detail(self):
        url = reverse('inscriptions_challenge_participation',
                      kwargs={'challenge_uid': 'grandchal', 'participation_id': self.p_dupont.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('participation_challenge.html', template_names(response))
        self.assertEqual(response.context['participation'].id, self.p_dupont.id)
        self.assertEqual(response.context['participation'].count, 2)
        self.assertContains(response, 'Equipe Dupont')
        self.assertContains(response, 'Grand Challenge')

    def test_challenge_participation_unknown_is_404(self):
        url = reverse('inscriptions_challenge_participation',
                      kwargs={'challenge_uid': 'grandchal', 'participation_id': 999999})
        self.assertEqual(self.client.get(url).status_code, 404)
        url = reverse('inscriptions_challenge_participation',
                      kwargs={'challenge_uid': 'nope', 'participation_id': self.p_dupont.id})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_challenge_participation_post_ignored_for_non_superuser(self):
        url = reverse('inscriptions_challenge_participation',
                      kwargs={'challenge_uid': 'grandchal', 'participation_id': self.p_dupont.id})
        response = self.client.post(url, {'course_uid': 'cha/cha', 'participation': ''})
        self.assertEqual(response.status_code, 200)  # falls through to the read-only page
        self.assertEqual(self.p_dupont.equipes.count(), 2)

    # --- candidate participations to move a team to
    def test_get_participations_to_move(self):
        # Moving Dupont's race "cha" entry: candidates are the other
        # participations of the same category that have no team in "cha".
        lonely = ParticipationChallenge.objects.create(challenge=self.challenge, nom='Equipe Dupond', categorie=self.cc)
        lonely.add_equipe(self._solo(self.course_b, self.cat_b, 'Dupond', 'Equipe Dupond', position=3))
        url = reverse('inscriptions_get_participations_to_move', kwargs={
            'challenge_uid': 'grandchal', 'participation_id': self.p_dupont.id, 'course_uid': 'cha/cha'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('selection_participation.html', template_names(response))
        self.assertEqual(response.context['course'], self.course_a)
        self.assertEqual(response.context['participation'], self.p_dupont)
        ids = [p.id for p in response.context['participations']]
        self.assertEqual(ids, [lonely.id])  # not itself, not Martin (already in "cha")

    def test_get_participations_to_move_unknown_objects_are_404(self):
        base = {'challenge_uid': 'grandchal', 'participation_id': self.p_dupont.id, 'course_uid': 'cha/cha'}
        for key, value in (('challenge_uid', 'nope'), ('participation_id', 999999), ('course_uid', 'nope/nope')):
            url = reverse('inscriptions_get_participations_to_move', kwargs=dict(base, **{key: value}))
            self.assertEqual(self.client.get(url).status_code, 404, key)


class LienResultatsCoursePageTest(BaseTestCase):
    def test_lien_resultats_seulement_si_resultats(self):
        edition = CourseFactory(date=date.today() - timedelta(days=30),
                                date_fermeture=date.today() - timedelta(days=40))
        edition.course.active = True
        edition.course.save()
        url = '/%s/' % edition.course.uid
        self.assertNotContains(self.client.get(url), '/resultats/')
        EquipeFactory(course=edition, position_generale=1)
        self.assertContains(self.client.get(url), '/resultats/')
