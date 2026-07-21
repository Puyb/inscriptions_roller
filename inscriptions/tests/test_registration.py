from datetime import date, timedelta
from decimal import Decimal

from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory, ExtraQuestionFactory
from inscriptions.models import Equipe
from inscriptions.tests.base import BaseTestCase, equipe_form_data, equipier_formset_data

TOMORROW = date.today() + timedelta(days=1)
YESTERDAY = date.today() - timedelta(days=1)


class RegistrationTestCase(BaseTestCase):
    """End-to-end (through the Django test client, no browser/JS) coverage
    of the public registration form: `views.form()`. Mirrors and extends the
    scenarios that used to live in the now-removed `fixtures/course1.json` +
    `inscriptions/tests.py`, rebuilt on factories so it survives schema
    changes instead of silently bit-rotting."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(
            uid='course1',
            date_ouverture=date.today(),
            date_fermeture=date.today() + timedelta(days=2),
            limite_participants=700,
        )
        self.solo = CategorieFactory(
            course=self.course, code='IDH', nom='Individuel Homme',
            min_equipiers=1, max_equipiers=1, sexe='H', min_age=18,
            numero_debut=200, numero_fin=249,
            prices_base=[Decimal('40.00')], prices_equipier=[],
        )
        self.duo = CategorieFactory(
            course=self.course, code='DUX', nom='Duo Homme ou Mixte',
            min_equipiers=2, max_equipiers=2, sexe='HX', min_age=18,
            numero_debut=300, numero_fin=369,
            prices_base=[Decimal('50.00')], prices_equipier=[Decimal('10.00')],
        )

    def _duo_payload(self, **overrides):
        data = equipe_form_data(nom='Equipe 1', nombre='2', categorie=str(self.duo.id))
        data.update(equipier_formset_data([
            dict(nom='Dylan', prenom='Bob', sexe='H', date_de_naissance=date(1989, 1, 1), justificatif='certificat'),
            dict(nom='Joplin', prenom='Janis', sexe='F', date_de_naissance=date(1980, 1, 1), justificatif='licence', num_licence='123456'),
        ]))
        data.update(overrides)
        return data

    def test_course_not_open_yet(self):
        self.course.date_ouverture = TOMORROW
        self.course.date_fermeture = TOMORROW + timedelta(days=1)
        self.course.save()

        response = self.client.get('/course1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'not_opened_yet.html')

    def test_course_closed(self):
        self.course.date_ouverture = YESTERDAY - timedelta(days=1)
        self.course.date_fermeture = YESTERDAY
        self.course.save()

        response = self.client.get('/course1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'closed.html')

    def test_open_registration_form(self):
        response = self.client.get('/course1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'form.html')
        self.assertIsNone(response.context['instance'])
        self.assertFalse(response.context['update'])
        self.assertEqual(response.context['nombres_par_tranche'], {})

    def test_create_inscription(self):
        response = self.client.post('/course1/', self._duo_payload())
        equipe = self.course.equipe_set.get(nom='Equipe 1')
        self.assertRedirects(response, '/course1/%s/done/' % equipe.numero)
        self.assertEqual(equipe.numero, 300)
        self.assertEqual(equipe.categorie, self.duo)
        self.assertEqual(equipe.equipier_set.count(), 2)
        # server recomputes the price from the category/team size - it does
        # not trust the (hidden, but client-controlled) `prix` field.
        self.assertEqual(equipe.prix, Decimal('70.00'))
        self.assertIn(response.cookies['code_%s' % equipe.id].value, equipe.password)

    def test_price_is_not_trusted_from_the_client(self):
        response = self.client.post('/course1/', self._duo_payload(prix='1'))
        equipe = self.course.equipe_set.get(nom='Equipe 1')
        self.assertRedirects(response, '/course1/%s/done/' % equipe.numero)
        self.assertEqual(equipe.prix, Decimal('70.00'))

    def test_wrong_password_is_404(self):
        equipe = EquipeFactory(course=self.course, categorie=self.solo, nombre=1, numero=201, password='123456')
        response = self.client.get('/course1/%s/wrong/' % equipe.numero)
        self.assertEqual(response.status_code, 404)

    def test_edit_page_shows_existing_team(self):
        equipe = EquipeFactory(course=self.course, categorie=self.solo, nombre=1, numero=201, password='123456')
        response = self.client.get('/course1/%s/123456/' % equipe.numero)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'form.html')
        self.assertEqual(response.context['instance'], equipe)
        self.assertTrue(response.context['update'])

    def test_locked_equipe_cannot_be_edited_by_the_public(self):
        equipe = EquipeFactory(course=self.course, categorie=self.solo, nombre=1, numero=201, password='123456', verrou=True)
        response = self.client.get('/course1/%s/123456/' % equipe.numero)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'locked.html')

    def test_modification_changes_category_and_recomputes_bib_number(self):
        equipe = EquipeFactory(course=self.course, categorie=self.solo, nombre=1, numero=201, password='123456')
        existing = EquipierFactory(equipe=equipe, numero=1, sexe='H', date_de_naissance=date(1989, 1, 1))

        # form-0 must reference the existing equipier's id (the formset's
        # queryset is `instance.equipier_set.all()`, one row) or Django
        # treats it as a brand new row instead of editing the existing one.
        data = equipe_form_data(nom='Equipe 1', nombre='2', categorie=str(self.duo.id))
        data.update(equipier_formset_data([
            dict(id=existing.id, nom='Dylan', prenom='Bob', sexe='H', date_de_naissance=date(1989, 1, 1), justificatif='certificat'),
            dict(nom='Joplin', prenom='Janis', sexe='F', date_de_naissance=date(1980, 1, 1), justificatif='licence', num_licence='123456'),
        ]))

        response = self.client.post('/course1/%s/123456/' % equipe.numero, data)
        equipe.refresh_from_db()
        self.assertRedirects(response, '/course1/%s/done/' % equipe.numero)
        self.assertEqual(equipe.categorie, self.duo)
        self.assertEqual(equipe.numero, 300)
        self.assertEqual(equipe.equipier_set.count(), 2)

    def test_categorie_full(self):
        EquipeFactory(course=self.course, categorie=self.solo, nombre=1, numero=249)  # fills 200-249

        data = equipe_form_data(nom='Equipe 1', nombre='1', categorie=str(self.solo.id))
        data.update(equipier_formset_data([
            dict(nom='Dylan', prenom='Bob', sexe='H', date_de_naissance=date(1989, 1, 1), justificatif='certificat'),
        ]))
        response = self.client.post('/course1/', data)
        self.assertEqual(response.context['message'], "Désolé, il n'y a plus de place dans cette catégorie")
        self.assertFalse(Equipe.objects.filter(nom='Equipe 1').exists())

    def test_registration_closed_once_limite_participants_reached(self):
        self.course.limite_participants = 2
        self.course.save()
        EquipeFactory(course=self.course, categorie=self.duo, nombre=2, numero=300)

        response = self.client.post('/course1/', self._duo_payload())
        self.assertRedirects(response, '/')
        self.assertFalse(Equipe.objects.filter(nom='Equipe 1').exists())

    def test_extra_question_price_is_added_server_side(self):
        extra = ExtraQuestionFactory(
            course=self.course, page='Equipe', type='checkbox', label='T-shirt',
            prices=[Decimal('15.00')], required=False,
        )
        data = equipe_form_data(nom='Equipe 1', nombre='1', categorie=str(self.solo.id))
        data[extra.getId()] = 'on'
        data.update(equipier_formset_data([
            dict(nom='Dylan', prenom='Bob', sexe='H', date_de_naissance=date(1989, 1, 1), justificatif='certificat'),
        ]))
        self.client.post('/course1/', data)
        equipe = self.course.equipe_set.get(nom='Equipe 1')
        self.assertEqual(equipe.prix, Decimal('55.00'))  # 40 (IDH) + 15 (t-shirt)
