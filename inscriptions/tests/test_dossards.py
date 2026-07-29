from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from inscriptions.admin_course import CategorieAdmin
from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.models import Accreditation
from inscriptions.tests.base import BaseTestCase


def flatten_fieldsets_fields(fieldsets):
    fields = []
    for _label, opts in fieldsets:
        for field in opts['fields']:
            if isinstance(field, (list, tuple)):
                fields.extend(field)
            else:
                fields.append(field)
    return fields


def login_as_organizer(client, course, role='admin'):
    user = User.objects.create_user(
        'organizer%d' % course.id, 'organizer%d@example.com' % course.id, 'pass1234',
    )
    Accreditation.objects.create(user=user, course=course, role=role)
    client.force_login(user)
    client.cookies['course_uid'] = course.uid
    client.cookies['course_id'] = str(course.id)
    return user


class DossardsFormTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        login_as_organizer(self.client, self.course)

    def test_get_shows_upload_form(self):
        response = self.client.get('/course/dossards/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Générer')

    def test_post_without_file_keeps_existing_background_and_returns_print_page(self):
        equipe = EquipeFactory(course=self.course, numero=12)
        equipier = EquipierFactory(equipe=equipe, numero=1, prenom='Alice', nom='Martin')

        response = self.client.post('/course/dossards/', {})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dossards_print.html')
        self.assertContains(response, str(equipier.dossard()))
        self.assertContains(response, 'Alice')
        self.course.refresh_from_db()
        self.assertFalse(self.course.fond_dossard)

    def test_post_with_file_saves_background_image(self):
        image = SimpleUploadedFile(
            'fond.png',
            (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02'
                b'\x08\x02\x00\x00\x00\xfd\xd4\x9as\x00\x00\x00\x16IDATx\x9cc\xfc\xcf'
                b'\xc0\xc0\xc0\xc0\xc0\xc4\xc0\xc0\xc0\xc0\xc0\x00\x00\r\x1d\x01\x03j'
                b'\xc2\x9b\xe9\x00\x00\x00\x00IEND\xaeB`\x82'
            ),
            content_type='image/png',
        )
        response = self.client.post('/course/dossards/', {'fond_dossard': image})

        self.assertEqual(response.status_code, 200)
        self.course.refresh_from_db()
        self.assertTrue(self.course.fond_dossard)

    def test_get_shows_category_color_input_defaulting_to_black(self):
        categorie = CategorieFactory(course=self.course, code='CAT1')

        response = self.client.get('/course/dossards/')

        self.assertContains(response, 'couleur_dossard_%d' % categorie.id)
        self.assertContains(response, 'value="black"')

    def test_post_saves_category_color_and_applies_it_in_print_page(self):
        categorie = CategorieFactory(course=self.course, code='CAT1')
        equipe = EquipeFactory(course=self.course, categorie=categorie, numero=1)
        EquipierFactory(equipe=equipe, numero=1)

        response = self.client.post('/course/dossards/', {
            'couleur_dossard_%d' % categorie.id: 'red',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dossards_print.html')
        self.assertContains(response, '.CAT1 .dossard { color: red; }')
        categorie.refresh_from_db()
        self.assertEqual(categorie.couleur_dossard, 'red')


class CategorieFormNonRegressionTestCase(BaseTestCase):
    def test_categorie_admin_excludes_couleur_dossard(self):
        self.assertNotIn('couleur_dossard', flatten_fieldsets_fields(CategorieAdmin.fieldsets))
