from django.test import Client, TestCase
from datetime import date, timedelta
from inscriptions.models import Course, Equipe

tomorrow = date.today() + timedelta(days=1)
tomorrow2 = date.today() + timedelta(days=2)
yesterday = date.today() - timedelta(days=1)
yesterday2 = date.today() - timedelta(days=2)

class InscriptionsTestCase(TestCase):
    fixtures = ('course1.json', )
    def setUp(self):
        self.course = Course.objects.get(id=1)
        self.course.date_ouverture = date.today()
        self.course.date_fermeture = tomorrow2
        self.course.save()

        self.client = Client()

    def test_not_open(self):
        self.course.date_ouverture = tomorrow
        self.course.date_fermeture = tomorrow2
        self.course.save()

        response = self.client.get('/course1/')

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.templates[0].name, 'not_opened_yet.html')

    def test_closed(self):
        self.course.date_ouverture = yesterday2
        self.course.date_fermeture = yesterday
        self.course.save()

        response = self.client.get('/course1/')

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.templates[0].name, 'closed.html')

    def test_open(self):
        response = self.client.get('/course1/')

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.templates[0].name, 'form.html')
        self.assertEqual(response.context['instance'], None)
        self.assertEqual(response.context['update'], False)
        self.assertEqual(response.context['course'], self.course)
        self.assertEqual(response.context['message'], '')
        self.assertEqual(response.context['errors'], {})
        self.assertEqual(response.context['nombres_par_tranche'], {'0-199': 0, '200-249': 1, '300-369': 0})
    
    def test_inscription(self):
        response = self.client.post('/course1/', {
            'prix': '60',
            'nom': 'Equipe 1',
            'club': 'Club 1',
            'gerant_nom': 'Dylan',
            'gerant_prenom': 'Bob',
            'gerant_adresse1': '123 rue',
            'gerant_adress2': '',
            'gerant_ville': 'Somewhere',
            'gerant_code_postal': '12345',
            'gerant_pays': 'FR',
            'gerant_email': 'bob.dylan@example.fr',
            'gerant_email2': 'bob.dylan@example.fr',
            'gerant_telephone': '0123456789',
            'nombre': '2',
            'connu': 'Bouche à oreille',
            'form-0-id': '',
            'form-0-nom': 'Dylan',
            'form-0-prenom': 'Bob',
            'form-0-sexe': 'H',
            'form-0-adresse1': '123 rue',
            'form-0-adresse2': '',
            'form-0-ville': 'Somewhere',
            'form-0-code_postal': '12345',
            'form-0-pays': 'FR',
            'form-0-email': 'bob.dylan@example.fr',
            'form-0-date_de_naissance_day': '1',
            'form-0-date_de_naissance_month': '1',
            'form-0-date_de_naissance_year': '1989',
            'form-0-autorisation': '',
            'form-0-justificatif': 'certificat',
            'form-0-num_licence': '',
            'form-0-piece_jointe': '',
            'form-0-transpondeur': '123',
            'form-0-taille_tshirt': 'L',
            'form-1-id': '',
            'form-1-nom': 'Joplin',
            'form-1-prenom': 'Janis',
            'form-1-sexe': 'F',
            'form-1-adresse1': '456 avenue',
            'form-1-adresse2': '',
            'form-1-ville': 'Elsewhere',
            'form-1-code_postal': '67890',
            'form-1-pays': 'FR',
            'form-1-email': 'janis.joplin@example.com',
            'form-1-date_de_naissance_day': '1',
            'form-1-date_de_naissance_month': '1',
            'form-1-date_de_naissance_year': '1980',
            'form-1-autorisation': '',
            'form-1-justificatif': 'licence',
            'form-1-num_licence': '123456',
            'form-1-piece_jointe': '',
            'form-1-transpondeur': '',
            'form-1-taille_tshirt': '',
            'form-2-id': '',
            'form-2-nom': '',
            'form-2-prenom': '',
            'form-2-sexe': '',
            'form-2-adresse1': '',
            'form-2-adresse2': '',
            'form-2-ville': '',
            'form-2-code_postal': '',
            'form-2-pays': 'FR',
            'form-2-email': '',
            'form-2-date_de_naissance_day': '1',
            'form-2-date_de_naissance_month': '1',
            'form-2-date_de_naissance_year': '2006',
            'form-2-autorisation': '',
            'form-2-num_licence': '',
            'form-2-piece_jointe': '',
            'form-2-transpondeur': '',
            'form-2-taille_tshirt': '',
            'categorie': '3',
            'conditions': 'on',
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        })
        self.assertRedirects(response, '/course1/300/done/')
        equipe = self.course.equipe_set.get(numero=300)
        self.assertEqual(equipe.categorie.code, 'DUX')
        self.assertEqual(equipe.equipier_set.count(), 2)
        self.assertIn(response.cookies['code_%s' % equipe.id].value, equipe.password)

        # categorie full
        # send mail

    def test_wrong_pass(self):
        response = self.client.get('/course1/201/wrong/')

        self.assertEqual(response.status_code, 404)
    
    def test_edit(self):
        equipe = self.course.equipe_set.get(numero=201)
        response = self.client.get('/course1/201/123456/')

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.templates[0].name, 'form.html')
        self.assertEqual(response.context['instance'], equipe)
        self.assertEqual(response.context['update'], True)
        self.assertEqual(response.context['course'], self.course)
        self.assertEqual(response.context['message'], '')
        self.assertEqual(response.context['errors'], {})
        self.assertEqual(response.context['nombres_par_tranche'], {'0-199': 0, '200-249': 1, '300-369': 0})
    

    def test_modification(self):
        response = self.client.post('/course1/201/123456/', {
            'id': 1,
            'prix': '60',
            'nom': 'Equipe 2',
            'club': 'Club 1',
            'gerant_nom': 'Dylan',
            'gerant_prenom': 'Bob',
            'gerant_adresse1': '123 rue',
            'gerant_adress2': '',
            'gerant_ville': 'Somewhere',
            'gerant_code_postal': '12345',
            'gerant_pays': 'FR',
            'gerant_email': 'bob.dylan@example.fr',
            'gerant_email2': 'bob.dylan@example.fr',
            'gerant_telephone': '0123456789',
            'nombre': '2',
            'connu': 'Bouche à oreille',
            'form-0-id': '1',
            'form-0-nom': 'Dylan',
            'form-0-prenom': 'Bob',
            'form-0-sexe': 'H',
            'form-0-adresse1': '123 rue',
            'form-0-adresse2': '',
            'form-0-ville': 'Somewhere',
            'form-0-code_postal': '12345',
            'form-0-pays': 'FR',
            'form-0-email': 'bob.dylan@example.fr',
            'form-0-date_de_naissance_day': '1',
            'form-0-date_de_naissance_month': '1',
            'form-0-date_de_naissance_year': '1989',
            'form-0-autorisation': '',
            'form-0-justificatif': 'certificat',
            'form-0-num_licence': '',
            'form-0-piece_jointe': '',
            'form-0-transpondeur': '123',
            'form-0-taille_tshirt': 'L',
            'form-1-id': '',
            'form-1-nom': 'Joplin',
            'form-1-prenom': 'Janis',
            'form-1-sexe': 'F',
            'form-1-adresse1': '456 avenue',
            'form-1-adresse2': '',
            'form-1-ville': 'Elsewhere',
            'form-1-code_postal': '67890',
            'form-1-pays': 'FR',
            'form-1-email': 'janis.joplin@example.com',
            'form-1-date_de_naissance_day': '1',
            'form-1-date_de_naissance_month': '1',
            'form-1-date_de_naissance_year': '1980',
            'form-1-autorisation': '',
            'form-1-justificatif': 'licence',
            'form-1-num_licence': '123456',
            'form-1-piece_jointe': '',
            'form-1-transpondeur': '',
            'form-1-taille_tshirt': '',
            'form-2-id': '',
            'form-2-nom': '',
            'form-2-prenom': '',
            'form-2-sexe': '',
            'form-2-adresse1': '',
            'form-2-adresse2': '',
            'form-2-ville': '',
            'form-2-code_postal': '',
            'form-2-pays': 'FR',
            'form-2-email': '',
            'form-2-date_de_naissance_day': '1',
            'form-2-date_de_naissance_month': '1',
            'form-2-date_de_naissance_year': '2006',
            'form-2-autorisation': '',
            'form-2-num_licence': '',
            'form-2-piece_jointe': '',
            'form-2-transpondeur': '',
            'form-2-taille_tshirt': '',
            'categorie': '3',
            'conditions': 'on',
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        })
        self.assertRedirects(response, '/course1/300/done/')
        equipe = self.course.equipe_set.get(numero=300)
        self.assertEqual(equipe.categorie.code, 'DUX')
        self.assertEqual(equipe.equipier_set.count(), 2)

    def test_categorie_full(self):
        self.course.categories.filter(id__in=[1,2]).update(numero_fin=201)
        response = self.client.post('/course1/', {
            'prix': '60',
            'nom': 'Equipe 1',
            'club': 'Club 1',
            'gerant_nom': 'Dylan',
            'gerant_prenom': 'Bob',
            'gerant_adresse1': '123 rue',
            'gerant_adress2': '',
            'gerant_ville': 'Somewhere',
            'gerant_code_postal': '12345',
            'gerant_pays': 'FR',
            'gerant_email': 'bob.dylan@example.fr',
            'gerant_email2': 'bob.dylan@example.fr',
            'gerant_telephone': '0123456789',
            'nombre': '1',
            'connu': 'Bouche à oreille',
            'form-0-id': '',
            'form-0-nom': 'Dylan',
            'form-0-prenom': 'Bob',
            'form-0-sexe': 'H',
            'form-0-adresse1': '123 rue',
            'form-0-adresse2': '',
            'form-0-ville': 'Somewhere',
            'form-0-code_postal': '12345',
            'form-0-pays': 'FR',
            'form-0-email': 'bob.dylan@example.fr',
            'form-0-date_de_naissance_day': '1',
            'form-0-date_de_naissance_month': '1',
            'form-0-date_de_naissance_year': '1989',
            'form-0-autorisation': '',
            'form-0-justificatif': 'certificat',
            'form-0-num_licence': '',
            'form-0-piece_jointe': '',
            'form-0-transpondeur': '123',
            'form-0-taille_tshirt': 'L',
            'categorie': '1',
            'conditions': 'on',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(response.context['message'], "Désolé, il n'y a plus de place dans cette catégorie")

        # send mail



