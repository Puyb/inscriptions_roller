import unittest
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.models import (
    Accreditation, Equipe, Tour,
)
from inscriptions.templatetags.duree import choose, duree, mod3
from inscriptions.tests.base import BaseTestCase


def login_as_organizer(client, course):
    user = User.objects.create_user(
        'orga%d' % course.id, 'orga%d@example.com' % course.id, 'pass1234',
        is_staff=True,
    )
    Accreditation.objects.create(user=user, course=course, role='admin')
    client.force_login(user)
    client.cookies['course_uid'] = course.uid
    client.cookies['course_id'] = str(course.id)
    return user


def csv_file(content, name='f.csv'):
    return SimpleUploadedFile(name, content.encode('utf-8'))


def import_data(csv_content, tours_content='', **overrides):
    """POST data for the results import form (default: ',' delimiter, floats)."""
    data = {
        'delimiter': ',',
        'csv': csv_file(csv_content),
        'tours_csv': csv_file(tours_content, 'tours.csv'),
        'dossard_column': '1',
        'time_format': 'float',
        'tours_duree_format': 'float',
        'tours_timestamp_format': 'float',
    }
    data.update(overrides)
    return data


class ResultsTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(distance=Decimal('2.000'))
        self.cat = CategorieFactory(course=self.course, code='SCR', numero_debut=1, numero_fin=99)


class DureeFilterTestCase(BaseTestCase):
    def test_duree_empty(self):
        self.assertEqual(duree(None), '')
        self.assertEqual(duree(0), '')

    def test_duree_minutes(self):
        self.assertEqual(duree(Decimal('65.5')), '1:05.500')

    def test_duree_hours(self):
        self.assertEqual(duree(Decimal('3725.25')), '1:02:05.250')

    def test_choose_six_equipiers_have_a_color_each(self):
        colors = 'danger,success,warning,info,primary,purple'
        self.assertEqual([choose(i, colors) for i in range(1, 7)],
                         ['danger', 'success', 'warning', 'info', 'primary', 'purple'])

    def test_choose_out_of_range_falls_back(self):
        self.assertEqual(choose(7, 'a,b'), 'color7')
        self.assertEqual(choose(0, 'a,b'), 'color0')

    def test_mod3(self):
        # 8 tours -> break every ceil(8/4)=2 rows
        self.assertEqual([i for i in range(8) if mod3(i, 8)], [1, 3, 5, 7])


class EquipeResultsMethodsTestCase(ResultsTestCase):
    def test_tours_total_includes_penalty(self):
        e = EquipeFactory(course=self.course, categorie=self.cat, tours=10, penalite=-2)
        self.assertEqual(e.tours_total(), 8)
        self.assertEqual(e.distance(), Decimal('16.000'))

    def test_tours_total_none_without_tours(self):
        e = EquipeFactory(course=self.course, categorie=self.cat)
        self.assertIsNone(e.tours_total())
        self.assertIsNone(e.distance())
        self.assertEqual(e.vitesse(), 0)

    def test_vitesse(self):
        e = EquipeFactory(course=self.course, categorie=self.cat, tours=10, temps=Decimal('3600'))
        self.assertEqual(e.vitesse(), Decimal('20'))

    def test_temps_humain(self):
        e = EquipeFactory(course=self.course, categorie=self.cat, tours=1, temps=Decimal('3725'))
        self.assertEqual(e.temps_humain(), '1:02:05.000')
        e.temps = None
        self.assertEqual(e.temps_humain(), '')

    def test_equipier_dossard(self):
        e = EquipeFactory(course=self.course, categorie=self.cat)
        eq = EquipierFactory(equipe=e, numero=3)
        self.assertEqual(eq.dossard(), e.numero * 10 + 3)


class PublicResultatsTestCase(ResultsTestCase):
    def url(self, **kw):
        return reverse('inscriptions_resultats', kwargs={'course_uid': self.course.uid})

    def test_only_teams_with_position_listed_ordered_by_position(self):
        e2 = EquipeFactory(course=self.course, categorie=self.cat, nom='Second',
                           position_generale=2, position_categorie=2, tours=9)
        e1 = EquipeFactory(course=self.course, categorie=self.cat, nom='Premier',
                           position_generale=1, position_categorie=1, tours=10)
        EquipeFactory(course=self.course, categorie=self.cat, nom='SansPosition')
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['equipes']), [e1, e2])
        self.assertNotContains(response, 'SansPosition')

    def test_other_course_not_listed(self):
        other = CourseFactory()
        EquipeFactory(course=other, nom='AutreCourse', position_generale=1)
        EquipeFactory(course=self.course, categorie=self.cat, position_generale=1)
        response = self.client.get(self.url())
        self.assertNotContains(response, 'AutreCourse')

    def test_sort_descending_and_search_and_top(self):
        for i in range(1, 4):
            EquipeFactory(course=self.course, categorie=self.cat, nom='Team%d' % i,
                          position_generale=i, position_categorie=i, tours=5)
        names = lambda r: [e.nom for e in r.context['equipes']]
        self.assertEqual(names(self.client.get(self.url(), {'sort': '-position_generale'})),
                         ['Team3', 'Team2', 'Team1'])
        self.assertEqual(names(self.client.get(self.url(), {'search': 'team2'})), ['Team2'])
        self.assertEqual(names(self.client.get(self.url(), {'top': '2'})), ['Team1', 'Team2'])
        self.assertEqual(names(self.client.get(self.url(), {'top': 'abc'})), ['Team1', 'Team2', 'Team3'])

    def test_by_categories_groups_and_filters(self):
        cat2 = CategorieFactory(course=self.course, code='DUO', numero_debut=100, numero_fin=199)
        EquipeFactory(course=self.course, categorie=self.cat, nom='A', position_generale=1, position_categorie=1)
        EquipeFactory(course=self.course, categorie=cat2, nom='B', position_generale=2, position_categorie=1)
        response = self.client.get(self.url(), {'by_categories': '1', 'categorie': 'DUO'})
        self.assertEqual([e.nom for e in response.context['equipes']], ['B'])
        self.assertTrue(response.context['split_categories'])

    def test_renders_tours_penalty_distance_and_time(self):
        EquipeFactory(course=self.course, categorie=self.cat, position_generale=1, position_categorie=1,
                      tours=10, penalite=-1, temps=Decimal('3725'))
        response = self.client.get(self.url())
        self.assertContains(response, '<td>9</td>', html=True)  # tours_total = 10 - 1
        self.assertContains(response, '18 km')
        self.assertContains(response, '1:02:05.000')

    def test_no_stats_and_not_staff_for_anonymous(self):
        response = self.client.get(self.url())
        self.assertIsNone(response.context['stats'])
        self.assertFalse(response.context['user_is_staff'])


class PublicResultatsEquipeTestCase(ResultsTestCase):
    def setUp(self):
        super().setUp()
        self.equipe = EquipeFactory(
            course=self.course, categorie=self.cat, nom='Les Rapides', club='RollerClub',
            position_generale=3, position_categorie=2, tours=10, penalite=-2,
            penalite_info='Depassement', temps=Decimal('3725'))
        self.url = reverse('inscriptions_resultats_equipe',
                           kwargs={'course_uid': self.course.uid, 'numero': self.equipe.numero})

    def test_404_unknown_numero_or_other_course(self):
        url = reverse('inscriptions_resultats_equipe',
                      kwargs={'course_uid': self.course.uid, 'numero': 9999})
        self.assertEqual(self.client.get(url).status_code, 404)
        other = CourseFactory()
        url = reverse('inscriptions_resultats_equipe',
                      kwargs={'course_uid': other.uid, 'numero': self.equipe.numero})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_summary_without_tours(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Les Rapides')
        self.assertContains(response, 'RollerClub')
        self.assertContains(response, '1:02:05.000')
        self.assertNotContains(response, 'Meilleur temps')  # no tours -> no equipiers panel

    def test_penalty_label_plural_and_info(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Pénalités :')
        self.assertContains(response, 'Depassement')

    def test_penalty_label_singular(self):
        Equipe.objects.filter(pk=self.equipe.pk).update(penalite=-1)
        self.assertContains(self.client.get(self.url), 'Pénalité :')

    def test_bonus_label(self):
        Equipe.objects.filter(pk=self.equipe.pk).update(penalite=3)
        response = self.client.get(self.url)
        self.assertContains(response, 'Bonus :')
        self.assertContains(response, '+3')

    def test_no_penalty_row_when_zero(self):
        Equipe.objects.filter(pk=self.equipe.pk).update(penalite=0)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'Bonus :')
        self.assertNotContains(response, 'Pénalité')

    def test_six_equipiers_each_get_a_distinct_colour_class(self):
        equipiers = [EquipierFactory(equipe=self.equipe, numero=n) for n in range(1, 7)]
        for eq in equipiers:
            Tour.objects.create(equipier=eq, timestamp=Decimal(eq.numero * 100), duree=Decimal('60'))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['tours'].count(), 6)
        for n, colour in enumerate(['danger', 'success', 'warning', 'info', 'primary', 'purple'], 1):
            self.assertContains(response, 'equipier%d %s' % (n, colour))
        self.assertNotContains(response, 'color7')

    def test_equipiers_stats_and_tours_ordered_by_timestamp(self):
        e1 = EquipierFactory(equipe=self.equipe, numero=1)
        e2 = EquipierFactory(equipe=self.equipe, numero=2)
        Tour.objects.create(equipier=e2, timestamp=Decimal('200'), duree=Decimal('130'))
        Tour.objects.create(equipier=e1, timestamp=Decimal('100'), duree=Decimal('70'))
        Tour.objects.create(equipier=e1, timestamp=Decimal('300'), duree=Decimal('65'))
        response = self.client.get(self.url)
        self.assertEqual([t.timestamp for t in response.context['tours']],
                         [Decimal('100'), Decimal('200'), Decimal('300')])
        self.assertEqual([e.numero for e in response.context['equipiers']], [1, 2])
        self.assertContains(response, 'Meilleur temps')
        self.assertContains(response, '1:05.000')  # best lap of e1


class AdminResultatsImportTestCase(ResultsTestCase):
    def setUp(self):
        super().setUp()
        self.url = '/course/resultats/'
        self.user = login_as_organizer(self.client, self.course)
        self.e1 = EquipeFactory(course=self.course, categorie=self.cat, nom='E1')
        self.e2 = EquipeFactory(course=self.course, categorie=self.cat, nom='E2')
        self.e3 = EquipeFactory(course=self.course, categorie=self.cat, nom='E3')

    def post(self, csv_content, tours_content='', **kw):
        # NB: an empty tours file is rejected by the form (FileField) even though
        # `tours_csv` is required=False, so always send a header-only file and skip
        # the first line of both files.
        kw.setdefault('skip_first', 'on')
        return self.client.post(
            self.url, import_data('h\n' + csv_content, 'h\n' + tours_content, **kw))

    def test_requires_login_and_accreditation(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        stranger = User.objects.create_user('x', 'x@example.com', 'pass1234', is_staff=True)
        self.client.force_login(stranger)
        self.client.cookies['course_uid'] = self.course.uid
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_get_shows_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/import_resultat_form.html')

    def test_invalid_form_rerenders_without_touching_data(self):
        Equipe.objects.filter(pk=self.e1.pk).update(tours=5)
        response = self.client.post(self.url, {'delimiter': ','})
        self.assertTemplateUsed(response, 'admin/import_resultat_form.html')
        self.e1.refresh_from_db()
        self.assertEqual(self.e1.tours, 5)

    def test_import_with_positions(self):
        csv = '%d,10,3600.5,1,2\n%d,9,3700,2,1\n' % (self.e1.numero, self.e2.numero)
        response = self.post(
            csv, nbtours_column='2', time_column='3',
            position_generale_column='4', position_categorie_column='5')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/import_resultat_done.html')
        self.e1.refresh_from_db()
        self.e2.refresh_from_db()
        self.e3.refresh_from_db()
        self.assertEqual((self.e1.tours, self.e1.temps, self.e1.position_generale, self.e1.position_categorie),
                         (10, Decimal('3600.5'), 1, 2))
        self.assertEqual((self.e2.tours, self.e2.position_generale, self.e2.position_categorie), (9, 2, 1))
        self.assertIsNone(self.e3.tours)
        self.assertEqual(list(response.context['equipes_manquantes']), [self.e3])
        self.assertEqual(list(response.context['equipes']), [self.e1, self.e2])

    def test_import_resets_previous_results(self):
        Equipe.objects.filter(pk=self.e3.pk).update(
            tours=4, penalite=-1, penalite_info='old', temps=Decimal('10'),
            position_generale=7, position_categorie=7)
        self.post('%d,10\n' % self.e1.numero, nbtours_column='2')
        self.e3.refresh_from_db()
        self.assertEqual((self.e3.tours, self.e3.penalite, self.e3.penalite_info, self.e3.temps,
                          self.e3.position_generale, self.e3.position_categorie),
                         (None, 0, '', None, None, None))

    def test_penalty_columns(self):
        self.post('%d,10,-2,Depassement\n' % self.e1.numero,
                  nbtours_column='2', penalite_column='3', penalite_info_column='4',
                  position_generale_column='1')
        self.e1.refresh_from_db()
        self.assertEqual((self.e1.penalite, self.e1.penalite_info), (-2, 'Depassement'))
        self.assertEqual(self.e1.tours_total(), 8)

    def test_positions_computed_from_position_generale_only(self):
        # only a general position column: category positions are derived
        cat2 = CategorieFactory(course=self.course, code='DUO', numero_debut=100, numero_fin=199)
        e4 = EquipeFactory(course=self.course, categorie=cat2, nom='E4')
        csv = '%d,3\n%d,1\n%d,2\n%d,4\n' % (self.e1.numero, self.e2.numero, self.e3.numero, e4.numero)
        self.post(csv, position_generale_column='2')
        for e in (self.e1, self.e2, self.e3, e4):
            e.refresh_from_db()
        self.assertEqual([self.e2.position_categorie, self.e3.position_categorie,
                          self.e1.position_categorie, e4.position_categorie], [1, 2, 3, 1])

    def test_hms_time_format(self):
        self.post('%d,1:02:03.5\n' % self.e1.numero, time_column='2', time_format='HMS')
        self.e1.refresh_from_db()
        self.assertEqual(self.e1.temps, Decimal('3723.5'))

    def test_bad_time_aborts_and_rolls_back(self):
        Equipe.objects.filter(pk=self.e3.pk).update(tours=4)
        response = self.post('%d,abc\n' % self.e1.numero, time_column='2')
        self.assertTemplateUsed(response, 'admin/import_resultat_form.html')
        self.assertIn('Temps incorrect', [str(m) for m in response.context['messages']][0])
        self.e3.refresh_from_db()
        self.assertEqual(self.e3.tours, 4)  # reset rolled back

    def test_bad_numero_aborts(self):
        response = self.post('xx,10\n', nbtours_column='2')
        self.assertTemplateUsed(response, 'admin/import_resultat_form.html')
        self.assertIn('Numéro', [str(m) for m in response.context['messages']][0])

    def test_semicolon_delimiter_and_latin1(self):
        content = 'h\n%d;7;Pénalité\n' % self.e1.numero
        data = import_data('', 'h\n', delimiter=';', skip_first='on', nbtours_column='2',
                           penalite_info_column='3')
        data['csv'] = SimpleUploadedFile('f.csv', content.encode('iso8859-1'))
        response = self.client.post(self.url, data)
        self.assertTemplateUsed(response, 'admin/import_resultat_done.html')
        self.e1.refresh_from_db()
        self.assertEqual((self.e1.tours, self.e1.penalite_info), (7, 'Pénalité'))

    def test_unregistered_team_is_created_in_category_range(self):
        response = self.post('50,6,Invitee\n', nbtours_column='2', nom_column='3',
                             position_generale_column='1')
        self.assertTemplateUsed(response, 'admin/import_resultat_done.html')
        e = Equipe.objects.get(course=self.course, numero=50)
        self.assertEqual((e.nom, e.categorie, e.tours), ('Invitee', self.cat, 6))

    def test_unregistered_team_without_nom_column_gets_default_name(self):
        self.post('51,6\n', nbtours_column='2')
        self.assertEqual(Equipe.objects.get(course=self.course, numero=51).nom, 'Equipe non inscrite 51')

    def test_category_column_moves_team(self):
        cat2 = CategorieFactory(course=self.course, code='DUO', numero_debut=100, numero_fin=199)
        self.post('%d,DUO\n' % self.e1.numero, categorie_column='2')
        self.e1.refresh_from_db()
        self.assertEqual(self.e1.categorie, cat2)

    def test_tours_import_creates_laps(self):
        eq = EquipierFactory(equipe=self.e1, numero=1)
        tours = '%d,60.5,100\n%d,61.5,200\n' % (eq.dossard(), eq.dossard())
        response = self.post('%d,2\n' % self.e1.numero, tours, nbtours_column='2',
                             tours_dossard_column='1', tours_duree_column='2',
                             tours_timestamp_column='3')
        self.assertTemplateUsed(response, 'admin/import_resultat_done.html')
        laps = list(Tour.objects.filter(equipier=eq).order_by('timestamp'))
        self.assertEqual([(t.duree, t.timestamp) for t in laps],
                         [(Decimal('60.5'), Decimal('100')), (Decimal('61.5'), Decimal('200'))])

    def test_reimport_replaces_laps(self):
        eq = EquipierFactory(equipe=self.e1, numero=1)
        Tour.objects.create(equipier=eq, timestamp=Decimal('1'), duree=Decimal('1'))
        self.post('%d,2\n' % self.e1.numero, '%d,60,100\n' % eq.dossard(), nbtours_column='2',
                  tours_dossard_column='1', tours_duree_column='2', tours_timestamp_column='3')
        self.assertEqual(Tour.objects.filter(equipier=eq).count(), 1)

    def test_other_course_untouched(self):
        other = CourseFactory()
        oe = EquipeFactory(course=other, tours=3, position_generale=1)
        Tour.objects.create(equipier=EquipierFactory(equipe=oe), timestamp=Decimal('1'), duree=Decimal('1'))
        self.post('%d,10\n' % self.e1.numero, nbtours_column='2')
        oe.refresh_from_db()
        self.assertEqual((oe.tours, oe.position_generale), (3, 1))
        self.assertEqual(Tour.objects.filter(equipier__equipe=oe).count(), 1)

    # ---- suspected bugs ----

    def test_positions_computed_from_time_and_tours(self):
        """The view tests `data.get('tours_column')`, but the form field is
        `nbtours_column`, so positions are never derived from time + laps."""
        csv = '%d,10,3700\n%d,10,3600\n%d,11,4000\n' % (self.e1.numero, self.e2.numero, self.e3.numero)
        self.post(csv, nbtours_column='2', time_column='3')
        for e in (self.e1, self.e2, self.e3):
            e.refresh_from_db()
        self.assertEqual([self.e3.position_generale, self.e2.position_generale, self.e1.position_generale],
                         [1, 2, 3])

    def test_import_without_tours_csv_is_accepted(self):
        """`tours_csv` is `required=False` in the form but the view does
        `request.FILES['tours_csv']` unconditionally (MultiValueDictKeyError)."""
        data = import_data('h\n%d,10\n' % self.e1.numero, '', skip_first='on', nbtours_column='2')
        del data['tours_csv']
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)

    def test_tours_import_with_timestamp_only(self):
        """Without a duration column `duree` is never bound -> UnboundLocalError."""
        eq = EquipierFactory(equipe=self.e1, numero=1)
        self.post('%d,2\n' % self.e1.numero, '%d,100\n' % eq.dossard(), nbtours_column='2',
                  tours_dossard_column='1', tours_timestamp_column='2')
        self.assertEqual(Tour.objects.filter(equipier=eq).count(), 1)
