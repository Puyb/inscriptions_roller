import importlib

from django.apps import apps
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile

from inscriptions.admin_course import CategorieAdmin
from inscriptions.admin_course import CourseAdmin as OrganizerCourseAdmin
from inscriptions.admin_main import CourseAdmin as SuperuserCourseAdmin
from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.models import (
    Accreditation, Course, DuplicateTranspondeurException,
    InvalidTranspondeurFileException, NotEnoughTranspondeursException,
    Transpondeur, parse_transpondeurs_file,
)
from inscriptions.tests.base import BaseTestCase


def uploaded_file(content):
    return SimpleUploadedFile('transpondeurs.txt', content.encode('ascii'))


def login_as_organizer(client, course, role='admin'):
    user = User.objects.create_user(
        'organizer%d' % course.id, 'organizer%d@example.com' % course.id, 'pass1234',
    )
    Accreditation.objects.create(user=user, course=course, role=role)
    client.force_login(user)
    client.cookies['course_uid'] = course.uid
    client.cookies['course_id'] = str(course.id)
    return user


class ParseTranspondeursFileTestCase(BaseTestCase):
    def test_parses_one_code_per_line_stripped_and_skips_blank_lines(self):
        codes = parse_transpondeurs_file(uploaded_file('A1\n A2 \n\nA3\n'))
        self.assertEqual(codes, ['A1', 'A2', 'A3'])

    def test_rejects_non_ascii_content(self):
        f = SimpleUploadedFile('t.txt', 'café'.encode('utf-8'))
        with self.assertRaises(InvalidTranspondeurFileException):
            parse_transpondeurs_file(f)

    def test_rejects_non_printable_ascii_content(self):
        f = SimpleUploadedFile('t.txt', b'A1\nA2\x01\n')
        with self.assertRaises(InvalidTranspondeurFileException):
            parse_transpondeurs_file(f)


class AssignTranspondeursEquipeModeTestCase(BaseTestCase):
    """Mode 'par équipe' : chaque équipe reçoit N transpondeurs (N = catégorie),
    consécutifs, dans l'ordre des numéros de dossard."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.categorie = CategorieFactory(course=self.course, nombre_transpondeurs=2)

    def test_assigns_consecutive_transpondeurs_per_equipe_in_dossard_order(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie)

        self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['T1', 'T2', 'T3', 'T4'])

        transpondeurs = list(Transpondeur.objects.filter(course=self.course).order_by('ordre'))
        self.assertEqual([t.numero for t in transpondeurs], ['T1', 'T2', 'T3', 'T4'])
        self.assertEqual([t.equipe_id for t in transpondeurs], [e1.id, e1.id, e2.id, e2.id])
        self.assertTrue(all(t.equipier_id is None for t in transpondeurs))
        self.course.refresh_from_db()
        self.assertEqual(self.course.transpondeur_mode, Course.TRANSPONDEUR_MODE_EQUIPE)

    def test_category_with_zero_transpondeurs_gets_none(self):
        categorie0 = CategorieFactory(course=self.course, nombre_transpondeurs=0, numero_debut=500, numero_fin=599)
        EquipeFactory(course=self.course, categorie=categorie0)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie)

        self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['T1', 'T2'])

        transpondeurs = list(Transpondeur.objects.filter(course=self.course).order_by('ordre'))
        self.assertEqual([t.equipe_id for t in transpondeurs], [e2.id, e2.id])

    def test_surplus_codes_are_created_unassigned(self):
        EquipeFactory(course=self.course, categorie=self.categorie)

        self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['T1', 'T2', 'T3'])

        transpondeurs = list(Transpondeur.objects.filter(course=self.course).order_by('ordre'))
        self.assertEqual(transpondeurs[-1].numero, 'T3')
        self.assertIsNone(transpondeurs[-1].equipe_id)

    def test_duplicate_codes_raise_and_nothing_is_created(self):
        EquipeFactory(course=self.course, categorie=self.categorie)

        with self.assertRaises(DuplicateTranspondeurException):
            self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['T1', 'T1', 'T2'])
        self.assertEqual(Transpondeur.objects.filter(course=self.course).count(), 0)

    def test_not_enough_codes_raise_and_nothing_is_created_or_modified(self):
        EquipeFactory(course=self.course, categorie=self.categorie)
        EquipeFactory(course=self.course, categorie=self.categorie)

        with self.assertRaises(NotEnoughTranspondeursException):
            self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['T1', 'T2', 'T3'])
        self.assertEqual(Transpondeur.objects.filter(course=self.course).count(), 0)
        self.course.refresh_from_db()
        self.assertIsNone(self.course.transpondeur_mode)

    def test_reset_then_reupload_regenerates_the_full_list(self):
        EquipeFactory(course=self.course, categorie=self.categorie)
        self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['T1', 'T2'])

        self.course.transpondeurs.all().delete()
        self.course.transpondeur_mode = None
        self.course.save(update_fields=['transpondeur_mode'])

        self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['U1', 'U2'])

        transpondeurs = list(Transpondeur.objects.filter(course=self.course).order_by('ordre'))
        self.assertEqual([t.numero for t in transpondeurs], ['U1', 'U2'])


class AssignTranspondeursEquipierModeTestCase(BaseTestCase):
    """Mode 'par équipier' : chaque équipier actif (numero <= equipe.nombre)
    reçoit ses propres transpondeurs."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.categorie = CategorieFactory(course=self.course, min_equipiers=1, max_equipiers=2, nombre_transpondeurs=1)

    def test_assigns_one_transpondeur_per_active_equipier_in_order(self):
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2)
        eq1 = EquipierFactory(equipe=equipe, numero=1)
        eq2 = EquipierFactory(equipe=equipe, numero=2)
        # leftover row beyond equipe.nombre must be ignored, like elsewhere in the codebase
        EquipierFactory(equipe=equipe, numero=3)

        self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPIER, ['A1', 'A2'])

        transpondeurs = list(Transpondeur.objects.filter(course=self.course).order_by('ordre'))
        self.assertEqual([t.numero for t in transpondeurs], ['A1', 'A2'])
        self.assertEqual([t.equipier_id for t in transpondeurs], [eq1.id, eq2.id])
        self.assertTrue(all(t.equipe_id is None for t in transpondeurs))
        self.course.refresh_from_db()
        self.assertEqual(self.course.transpondeur_mode, Course.TRANSPONDEUR_MODE_EQUIPIER)


class TranspondeurUploadViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.categorie = CategorieFactory(course=self.course, nombre_transpondeurs=1)
        self.equipe = EquipeFactory(course=self.course, categorie=self.categorie)
        self.user = login_as_organizer(self.client, self.course)

    def test_get_shows_upload_form_when_no_transpondeurs_exist(self):
        response = self.client.get('/course/transpondeurs/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.categorie, response.context['categories'])

    def test_post_valid_file_assigns_and_redirects_to_changelist(self):
        response = self.client.post('/course/transpondeurs/', {
            'mode': Course.TRANSPONDEUR_MODE_EQUIPE,
            'fichier': uploaded_file('T1\n'),
            'nombre_transpondeurs_%d' % self.categorie.id: '1',
        })
        self.assertRedirects(response, '/course/inscriptions/transpondeur/')
        self.assertEqual(Transpondeur.objects.filter(course=self.course).count(), 1)
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.nombre_transpondeurs, 1)

    def test_post_insufficient_file_shows_error_and_creates_nothing(self):
        response = self.client.post('/course/transpondeurs/', {
            'mode': Course.TRANSPONDEUR_MODE_EQUIPE,
            'fichier': uploaded_file('T1\n'),
            'nombre_transpondeurs_%d' % self.categorie.id: '2',
        }, follow=True)
        self.assertContains(response, 'assez')
        self.assertEqual(Transpondeur.objects.filter(course=self.course).count(), 0)
        # rolled back atomically: the per-category count entered on the form is not persisted either
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.nombre_transpondeurs, 1)

    def test_post_duplicate_codes_shows_error_and_creates_nothing(self):
        response = self.client.post('/course/transpondeurs/', {
            'mode': Course.TRANSPONDEUR_MODE_EQUIPE,
            'fichier': uploaded_file('T1\nT1\n'),
            'nombre_transpondeurs_%d' % self.categorie.id: '1',
        }, follow=True)
        self.assertContains(response, 'double')
        self.assertEqual(Transpondeur.objects.filter(course=self.course).count(), 0)

    def test_redirects_to_changelist_when_transpondeurs_already_exist(self):
        Transpondeur.objects.create(course=self.course, ordre=1, numero='X1')
        response = self.client.get('/course/transpondeurs/')
        self.assertRedirects(response, '/course/inscriptions/transpondeur/')


class TranspondeurAdminTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.categorie = CategorieFactory(course=self.course, nombre_transpondeurs=1)
        self.equipe = EquipeFactory(course=self.course, categorie=self.categorie)
        self.user = login_as_organizer(self.client, self.course)
        self.course.assign_transpondeurs(Course.TRANSPONDEUR_MODE_EQUIPE, ['T1'])
        self.transpondeur = Transpondeur.objects.get(course=self.course)

    def test_changelist_shows_the_list_once_assigned(self):
        response = self.client.get('/course/inscriptions/transpondeur/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'T1')

    def test_manual_edit_changes_numero(self):
        response = self.client.post('/course/inscriptions/transpondeur/%d/change/' % self.transpondeur.id, {
            'numero': 'T1-EDITED',
            'equipe': str(self.equipe.id),
            'equipier': '',
            '_save': 'Enregistrer',
        })
        self.assertRedirects(response, '/course/inscriptions/transpondeur/')
        self.transpondeur.refresh_from_db()
        self.assertEqual(self.transpondeur.numero, 'T1-EDITED')

    def test_manual_edit_rejects_both_equipe_and_equipier(self):
        equipier = EquipierFactory(equipe=self.equipe, numero=1)
        response = self.client.post('/course/inscriptions/transpondeur/%d/change/' % self.transpondeur.id, {
            'numero': 'T1',
            'equipe': str(self.equipe.id),
            'equipier': str(equipier.id),
            '_save': 'Enregistrer',
        })
        self.assertEqual(response.status_code, 200)
        self.transpondeur.refresh_from_db()
        self.assertIsNone(self.transpondeur.equipier_id)

    def test_manual_add_gets_the_next_ordre(self):
        response = self.client.post('/course/inscriptions/transpondeur/add/', {
            'numero': 'T2',
            'equipe': '',
            'equipier': '',
            '_save': 'Enregistrer',
        })
        self.assertRedirects(response, '/course/inscriptions/transpondeur/')
        added = Transpondeur.objects.get(numero='T2')
        self.assertEqual(added.ordre, 2)

    def test_reset_view_deletes_all_and_resets_mode(self):
        response = self.client.post('/course/inscriptions/transpondeur/reset/')
        self.assertRedirects(response, '/course/inscriptions/transpondeur/', target_status_code=302)
        self.assertEqual(Transpondeur.objects.filter(course=self.course).count(), 0)
        self.course.refresh_from_db()
        self.assertIsNone(self.course.transpondeur_mode)

    def test_changelist_redirects_to_upload_after_reset(self):
        self.client.post('/course/inscriptions/transpondeur/reset/')
        response = self.client.get('/course/inscriptions/transpondeur/')
        self.assertRedirects(response, '/course/transpondeurs/')


class TranspondeurAccessTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.cookies['course_uid'] = self.course.uid
        response = self.client.get('/course/inscriptions/transpondeur/')
        self.assertEqual(response.status_code, 302)

    def test_user_without_accreditation_is_redirected_to_login(self):
        # CourseAdminSite.admin_view() treats "no accreditation for this course"
        # the same as "not logged in": redirect_to_login(), not a 403.
        user = User.objects.create_user('outsider', 'outsider@example.com', 'pass1234')
        self.client.force_login(user)
        self.client.cookies['course_uid'] = self.course.uid
        response = self.client.get('/course/inscriptions/transpondeur/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/course/login/', response.url)


class CourseCategorieFormNonRegressionTestCase(BaseTestCase):
    """`transpondeur_mode`/`nombre_transpondeurs` must stay out of the regular
    Course/Categorie admin forms (they're only editable via the upload form
    and the `Transpondeur` admin, see docs/transpondeurs-plan.md §3.5)."""

    def test_organizer_course_admin_excludes_transpondeur_mode(self):
        self.assertIn('transpondeur_mode', OrganizerCourseAdmin.exclude)

    def test_superuser_course_admin_excludes_transpondeur_mode(self):
        self.assertIn('transpondeur_mode', SuperuserCourseAdmin.exclude)

    def test_categorie_admin_fieldsets_do_not_expose_nombre_transpondeurs(self):
        all_fields = []
        for _title, opts in CategorieAdmin.fieldsets:
            for f in opts['fields']:
                if isinstance(f, (tuple, list)):
                    all_fields.extend(f)
                else:
                    all_fields.append(f)
        self.assertNotIn('nombre_transpondeurs', all_fields)


class TranspondeurPermissionsTestCase(BaseTestCase):
    def test_new_user_receives_transpondeur_permissions_automatically(self):
        user = User.objects.create_user('newuser', 'newuser@example.com', 'pass1234')
        self.assertTrue(user.user_permissions.filter(codename='add_transpondeur').exists())
        self.assertTrue(user.user_permissions.filter(codename='change_transpondeur').exists())
        self.assertTrue(user.user_permissions.filter(codename='delete_transpondeur').exists())

    def test_migration_grants_permissions_to_pre_existing_users(self):
        user = User.objects.create_user('preexisting', 'preexisting@example.com', 'pass1234')
        user.user_permissions.remove(*Permission.objects.filter(
            codename__in=('add_transpondeur', 'change_transpondeur', 'delete_transpondeur'),
        ))
        self.assertFalse(user.user_permissions.filter(codename='add_transpondeur').exists())

        migration = importlib.import_module('inscriptions.migrations.0083_transpondeur')
        migration.grant_transpondeur_permissions(apps, None)

        self.assertTrue(user.user_permissions.filter(codename='add_transpondeur').exists())
        self.assertTrue(user.user_permissions.filter(codename='change_transpondeur').exists())
        self.assertTrue(user.user_permissions.filter(codename='delete_transpondeur').exists())
