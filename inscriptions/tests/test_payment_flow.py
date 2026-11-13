import json
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model

from inscriptions.factories import CourseFactory, EquipeFactory
from inscriptions.models import Mail, Paiement, TemplateMail
from inscriptions.templatetags import stripe as stripe_templatetags
from inscriptions.tests.base import BaseTestCase


def pay(equipe, montant, type='chèque'):
    """Record a confirmed payment of `montant` for `equipe`."""
    paiement = Paiement.objects.create(type=type, montant=Decimal(montant))
    paiement.equipes.create(equipe=equipe, montant=Decimal(montant))
    return paiement


def make_equipe(**kwargs):
    """Team with a non-zero number (the first team of a category range would get
    number 0 otherwise) and a password, as the registration form would set."""
    kwargs.setdefault('categorie__numero_debut', 100)
    kwargs.setdefault('password', 'abc123')
    return EquipeFactory(**kwargs)


class FakeStripeIntent:
    id = 'pi_fake_1'
    client_secret = 'pi_fake_1_secret_abc'


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class IntentPaiementStripeTestCase(BaseTestCase):
    """`stripe.PaymentIntent.create` is mocked: no request ever reaches Stripe."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(stripe_secret='sk_test_xxx', frais_stripe_inclus=False)
        self.equipe = make_equipe(course=self.course, prix=Decimal('40.00'))
        patcher = mock.patch('stripe.PaymentIntent.create', return_value=FakeStripeIntent())
        self.create = patcher.start()
        self.addCleanup(patcher.stop)

    def _get(self, *equipes, methode='stripe'):
        qs = '&'.join('equipe=%d' % e.numero for e in equipes)
        return self.client.get('/%s/intent/%s/?%s' % (self.course.uid, methode, qs))

    def test_no_equipe_is_404(self):
        response = self.client.get('/%s/intent/stripe/' % self.course.uid)
        self.assertEqual(response.status_code, 404)

    def test_unknown_equipe_number_is_404(self):
        response = self.client.get('/%s/intent/stripe/?equipe=99999' % self.course.uid)
        self.assertEqual(response.status_code, 404)

    def test_equipe_of_another_course_is_ignored(self):
        other = make_equipe(prix=Decimal('40.00'), numero=555)
        response = self.client.get('/%s/intent/stripe/?equipe=%d' % (self.course.uid, other.numero))
        self.assertEqual(response.status_code, 404)
        self.create.assert_not_called()

    def test_fees_added_when_not_included(self):
        frais = stripe_templatetags.frais(Decimal('40.00'))
        self.assertGreater(frais, 0)
        response = self._get(self.equipe)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['client_secret'], FakeStripeIntent.client_secret)
        self.assertEqual(self.create.call_args[1]['amount'], int((Decimal('40.00') + frais) * 100))
        self.assertEqual(self.create.call_args[1]['currency'], 'EUR')

    def test_fees_not_added_when_included(self):
        self.course.frais_stripe_inclus = True
        self.course.save()
        response = self._get(self.equipe)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.create.call_args[1]['amount'], 4000)
        paiement = Paiement.objects.get()
        self.assertIsNone(paiement.montant_frais)
        self.assertIsNone(paiement.equipes.get().montant_frais or None)

    def test_paypal_fee_flag_does_not_change_stripe_amount(self):
        self.course.frais_paypal_inclus = True
        self.course.save()
        self._get(self.equipe)
        frais = stripe_templatetags.frais(Decimal('40.00'))
        self.assertEqual(self.create.call_args[1]['amount'], int((Decimal('40.00') + frais) * 100))

    def test_creates_pending_paiement_and_repartition(self):
        self._get(self.equipe)
        frais = stripe_templatetags.frais(Decimal('40.00'))
        paiement = Paiement.objects.get()
        self.assertEqual(paiement.type, 'stripe')
        self.assertEqual(paiement.intent_id, FakeStripeIntent.id)
        self.assertIsNone(paiement.montant)  # confirmed later by the webhook
        self.assertEqual(paiement.montant_frais, Decimal(frais))
        rep = paiement.equipes.get()
        self.assertEqual(rep.equipe, self.equipe)
        self.assertEqual(rep.montant, Decimal('40.00'))
        self.assertEqual(rep.montant_frais, Decimal(frais))
        # a pending payment does not count as paid
        self.assertEqual(self.equipe.reste_a_payer, Decimal('40.00'))

    def test_amount_is_the_remaining_amount_after_partial_payment(self):
        pay(self.equipe, '15.00')
        self._get(self.equipe)
        frais = stripe_templatetags.frais(Decimal('25.00'))
        self.assertEqual(self.create.call_args[1]['amount'], int((Decimal('25.00') + frais) * 100))
        rep = Paiement.objects.get(type='stripe').equipes.get()
        self.assertEqual(rep.montant, Decimal('25.00'))

    def test_already_paid_redirects_to_done_without_stripe_call(self):
        pay(self.equipe, '40.00')
        response = self._get(self.equipe)
        self.assertRedirects(
            response, '/%s/%d/done/' % (self.course.uid, self.equipe.numero),
            fetch_redirect_response=False)
        self.create.assert_not_called()
        self.assertFalse(Paiement.objects.filter(type='stripe').exists())

    def test_grouped_payment_of_several_teams(self):
        equipe2 = make_equipe(course=self.course, prix=Decimal('60.00'))
        response = self._get(self.equipe, equipe2)
        self.assertEqual(response.status_code, 200)
        frais = stripe_templatetags.frais(Decimal('100.00'))
        self.assertEqual(self.create.call_args[1]['amount'], int((Decimal('100.00') + frais) * 100))
        description = self.create.call_args[1]['description']
        self.assertIn(str(self.equipe), description)
        self.assertIn(str(equipe2), description)

        paiement = Paiement.objects.get()  # a single Paiement for both teams
        reps = {r.equipe_id: r for r in paiement.equipes.all()}
        self.assertEqual(set(reps), {self.equipe.id, equipe2.id})
        self.assertEqual(reps[self.equipe.id].montant, Decimal('40.00'))
        self.assertEqual(reps[equipe2.id].montant, Decimal('60.00'))
        # fees are split between the teams and add up to the total fee
        total = sum(r.montant_frais for r in reps.values())
        self.assertEqual(total, Decimal(frais))
        self.assertEqual(paiement.montant_frais, Decimal(frais))

    def test_grouped_payment_skips_amounts_already_paid(self):
        equipe2 = make_equipe(course=self.course, prix=Decimal('60.00'))
        pay(self.equipe, '40.00')
        self._get(self.equipe, equipe2)
        frais = stripe_templatetags.frais(Decimal('60.00'))
        self.assertEqual(self.create.call_args[1]['amount'], int((Decimal('60.00') + frais) * 100))

    def test_stripe_error_returns_500_and_no_paiement(self):
        self.create.side_effect = Exception('stripe down')
        response = self._get(self.equipe)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(json.loads(response.content)['success'])
        self.assertFalse(Paiement.objects.exists())

    def test_unknown_method_returns_500(self):
        response = self._get(self.equipe, methode='bitcoin')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Paiement.objects.exists())

    def test_secret_key_of_the_course_is_used(self):
        import stripe
        self._get(self.equipe)
        self.assertEqual(stripe.api_key, 'sk_test_xxx')


class IntentPaiementHelloAssoTestCase(BaseTestCase):
    """`requests.post` is mocked in `inscriptions.views`: the first call is the
    OAuth token, the second one the checkout-intent creation."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(
            helloasso_organisation='my-org', helloasso_id='cid', helloasso_secret='csecret',
            helloasso_sandbox=True)
        self.equipe = make_equipe(course=self.course, prix=Decimal('40.00'))

    def _patch(self, checkout):
        patcher = mock.patch('inscriptions.views.requests.post', side_effect=[
            FakeResponse({'access_token': 'tok123'}),
            FakeResponse(checkout),
        ])
        post = patcher.start()
        self.addCleanup(patcher.stop)
        return post

    def _get(self, *equipes):
        qs = '&'.join('equipe=%d' % e.numero for e in equipes)
        return self.client.get('/%s/intent/helloasso/?%s' % (self.course.uid, qs))

    def test_redirects_to_helloasso_and_creates_pending_paiement(self):
        post = self._patch({'redirectUrl': 'https://pay.helloasso.example/checkout/1'})
        response = self._get(self.equipe)
        self.assertRedirects(response, 'https://pay.helloasso.example/checkout/1',
                             fetch_redirect_response=False)
        self.assertEqual(post.call_count, 2)
        token_url = post.call_args_list[0][0][0]
        self.assertEqual(token_url, 'https://api.helloasso-sandbox.com/oauth2/token')
        url = post.call_args_list[1][0][0]
        self.assertEqual(url, 'https://api.helloasso-sandbox.com/v5/organizations/my-org/checkout-intents')
        self.assertEqual(post.call_args_list[1][1]['headers']['Authorization'], 'Bearer tok123')
        body = json.loads(post.call_args_list[1][0][1])
        self.assertEqual(body['totalAmount'], 4000)
        self.assertEqual(body['initialAmount'], 4000)
        self.assertEqual(body['payer']['email'], self.equipe.gerant_email)
        self.assertTrue(body['returnUrl'].startswith('https://'))
        self.assertTrue(body['returnUrl'].endswith('/%s/%d/done/' % (self.course.uid, self.equipe.numero)))

        paiement = Paiement.objects.get()
        self.assertEqual(paiement.type, 'helloasso')
        self.assertIsNone(paiement.montant)
        self.assertIsNone(paiement.montant_frais)  # HelloAsso: no fees added
        self.assertEqual(paiement.intent_id, body['metadata']['uuid'])
        self.assertEqual(paiement.equipes.get().montant, Decimal('40.00'))

    def test_production_url_when_not_sandbox(self):
        self.course.helloasso_sandbox = False
        self.course.save()
        post = self._patch({'redirectUrl': 'https://x.example/'})
        self._get(self.equipe)
        self.assertEqual(post.call_args_list[0][0][0], 'https://api.helloasso.com/oauth2/token')
        self.assertTrue(post.call_args_list[1][0][0].startswith('https://api.helloasso.com/v5/'))

    def test_frais_stripe_flag_is_ignored(self):
        self.course.frais_stripe_inclus = False
        self.course.save()
        post = self._patch({'redirectUrl': 'https://x.example/'})
        self._get(self.equipe)
        body = json.loads(post.call_args_list[1][0][1])
        self.assertEqual(body['totalAmount'], 4000)

    def test_grouped_payment_uses_total_and_first_team_as_payer(self):
        equipe2 = make_equipe(course=self.course, prix=Decimal('60.00'))
        post = self._patch({'redirectUrl': 'https://x.example/'})
        self._get(self.equipe, equipe2)
        body = json.loads(post.call_args_list[1][0][1])
        self.assertEqual(body['totalAmount'], 10000)
        paiement = Paiement.objects.get()
        self.assertEqual(
            {r.equipe_id: r.montant for r in paiement.equipes.all()},
            {self.equipe.id: Decimal('40.00'), equipe2.id: Decimal('60.00')})

    def test_api_errors_redirect_to_edit_page_with_messages(self):
        self._patch({'errors': [{'message': 'Montant invalide'}]})
        response = self._get(self.equipe)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/%s/%d/' % (self.course.uid, self.equipe.numero), response.url)
        self.assertIn(self.equipe.password, response.url)
        self.assertIn('message=Montant+invalide', response.url)

    def test_network_error_returns_500(self):
        with mock.patch('inscriptions.views.requests.post', side_effect=Exception('boom')):
            response = self._get(self.equipe)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Paiement.objects.exists())


class GetHelloAssoTokenTestCase(BaseTestCase):
    def test_returns_access_token_and_sends_credentials(self):
        from inscriptions.views import get_helloasso_token
        course = CourseFactory(helloasso_id='cid', helloasso_secret='csecret', helloasso_sandbox=True)
        with mock.patch('inscriptions.views.requests.post',
                        return_value=FakeResponse({'access_token': 'abc'})) as post:
            token = get_helloasso_token(course)
        self.assertEqual(token, 'abc')
        self.assertEqual(post.call_args[0][0], 'https://api.helloasso-sandbox.com/oauth2/token')
        sent = post.call_args[0][1]
        self.assertIn('grant_type=client_credentials', sent)
        self.assertIn('client_id=cid', sent)
        self.assertIn('client_secret=csecret', sent)

    def test_production_base_url(self):
        from inscriptions.views import get_helloasso_token
        course = CourseFactory(helloasso_id='cid', helloasso_secret='s', helloasso_sandbox=False)
        with mock.patch('inscriptions.views.requests.post',
                        return_value=FakeResponse({'access_token': 'abc'})) as post:
            get_helloasso_token(course)
        self.assertEqual(post.call_args[0][0], 'https://api.helloasso.com/oauth2/token')

    def test_missing_access_token_raises(self):
        from inscriptions.views import get_helloasso_token
        course = CourseFactory()
        with mock.patch('inscriptions.views.requests.post',
                        return_value=FakeResponse({'error': 'invalid_client'})):
            with self.assertRaises(KeyError):
                get_helloasso_token(course)


class DoneViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.equipe = make_equipe(course=self.course, prix=Decimal('40.00'))

    def _url(self, numero=None):
        return '/%s/%d/done/' % (self.course.uid, numero or self.equipe.numero)

    def test_renders_done_page(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'done.html')
        self.assertEqual(response.context['instance'], self.equipe)
        self.assertIn('/%s/%d/' % (self.course.uid, self.equipe.numero), response.context['url'])
        self.assertIn(self.equipe.password, response.context['url'])
        self.assertTrue(response.context['paypal_ipn_url'].endswith('/%s/ipn/' % self.course.uid))

    def test_unknown_team_is_404(self):
        self.assertEqual(self.client.get(self._url(99999)).status_code, 404)

    def test_unknown_course_is_404(self):
        self.assertEqual(self.client.get('/nope/1/done/').status_code, 404)

    def test_team_of_another_course_is_404(self):
        other = make_equipe(prix=Decimal('40.00'))
        course2 = CourseFactory()
        response = self.client.get('/%s/%d/done/' % (course2.uid, other.numero))
        self.assertEqual(response.status_code, 404)

    def test_closed_course_shows_closed_page_to_anonymous(self):
        self.course.date_fermeture = date.today() - timedelta(days=1)
        self.course.save()
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, 'closed.html')

    def test_not_yet_open_course_shows_not_opened_page(self):
        self.course.date_ouverture = date.today() + timedelta(days=5)
        self.course.save()
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, 'not_opened_yet.html')

    def test_staff_can_see_done_page_on_closed_course(self):
        self.course.date_fermeture = date.today() - timedelta(days=1)
        self.course.save()
        staff = get_user_model().objects.create_user('staff', 'staff@example.com', 'pw', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, 'done.html')


class EquipePayeeTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.equipe = make_equipe(course=self.course, prix=Decimal('40.00'))

    def _get(self, numero=None):
        return self.client.get('/%s/%d/payee/' % (self.course.uid, numero or self.equipe.numero))

    def test_unpaid(self):
        self.assertEqual(json.loads(self._get().content), {'success': False})

    def test_pending_payment_is_not_paid(self):
        paiement = Paiement.objects.create(type='stripe', montant=None, intent_id='pi_1')
        paiement.equipes.create(equipe=self.equipe, montant=Decimal('40.00'))
        self.assertEqual(json.loads(self._get().content), {'success': False})

    def test_partially_paid(self):
        pay(self.equipe, '39.99')
        self.assertEqual(json.loads(self._get().content), {'success': False})

    def test_fully_paid(self):
        pay(self.equipe, '40.00')
        self.assertEqual(json.loads(self._get().content), {'success': True})

    def test_offered_team_is_paid(self):
        paiement = Paiement.objects.create(type='offert', montant=Decimal('0.00'))
        paiement.equipes.create(equipe=self.equipe, montant=Decimal('0.00'))
        self.assertEqual(json.loads(self._get().content), {'success': True})

    def test_unknown_team_is_404(self):
        self.assertEqual(self._get(99999).status_code, 404)

    def test_team_of_another_course_is_404(self):
        other = make_equipe(prix=Decimal('40.00'))
        course2 = CourseFactory()
        response = self.client.get('/%s/%d/payee/' % (course2.uid, other.numero))
        self.assertEqual(response.status_code, 404)


class FactureViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.equipe = make_equipe(course=self.course, prix=Decimal('40.00'))
        self.base = '/%s/%d/facture/' % (self.course.uid, self.equipe.numero)

    def _template_mail(self):
        return TemplateMail.objects.create(
            course=self.course, nom='paiement', destinataire='Equipe',
            sujet='Paiement recu', message='Merci {{ instance.nom }}')

    def test_unpaid_team_is_404_without_code(self):
        self.assertEqual(self.client.get(self.base).status_code, 404)

    def test_unpaid_team_is_404_even_with_valid_code(self):
        response = self.client.get('%s%s/' % (self.base, self.equipe.password))
        self.assertEqual(response.status_code, 404)

    def test_partially_paid_team_is_404(self):
        pay(self.equipe, '10.00')
        self.assertEqual(self.client.get(self.base).status_code, 404)

    def test_paid_without_code_shows_request_page(self):
        pay(self.equipe, '40.00')
        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'facture_new_url.html')
        self.assertEqual(response.context['instance'], self.equipe)

    def test_post_without_code_sends_the_payment_mail(self):
        pay(self.equipe, '40.00')
        self._template_mail()
        response = self.client.post(self.base)
        self.assertRedirects(response, self.base + 'thankyou/', fetch_redirect_response=False)
        mail = Mail.objects.get(equipe=self.equipe)
        self.assertEqual(mail.template.nom, 'paiement')
        self.assertEqual(mail.destinataires, [self.equipe.gerant_email])

    def test_post_on_unpaid_team_sends_nothing(self):
        self._template_mail()
        self.assertEqual(self.client.post(self.base).status_code, 404)
        self.assertFalse(Mail.objects.exists())

    def test_wrong_code_is_404(self):
        pay(self.equipe, '40.00')
        response = self.client.get('%swrong/' % self.base)
        self.assertEqual(response.status_code, 404)
        self.equipe.refresh_from_db()
        self.assertIsNone(self.equipe.date_facture)

    def test_valid_code_renders_invoice_and_stamps_date(self):
        pay(self.equipe, '40.00')
        self.assertIsNone(self.equipe.date_facture)
        response = self.client.get('%s%s/' % (self.base, self.equipe.password))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'facture.html')
        self.equipe.refresh_from_db()
        self.assertEqual(self.equipe.date_facture, date.today())

    def test_existing_invoice_date_is_kept(self):
        pay(self.equipe, '40.00')
        old = date.today() - timedelta(days=10)
        self.equipe.date_facture = old
        self.equipe.save()
        self.client.get('%s%s/' % (self.base, self.equipe.password))
        self.equipe.refresh_from_db()
        self.assertEqual(self.equipe.date_facture, old)

    def test_team_of_another_course_is_404(self):
        pay(self.equipe, '40.00')
        course2 = CourseFactory()
        response = self.client.get('/%s/%d/facture/' % (course2.uid, self.equipe.numero))
        self.assertEqual(response.status_code, 404)


class ContactViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(email_contact='orga@example.com')
        self.url = '/%s/contact/' % self.course.uid
        patcher = mock.patch('inscriptions.views.send_mail')
        self.send_mail = patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_shows_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contact.html')
        self.send_mail.assert_not_called()

    def test_unknown_course_is_404(self):
        self.assertEqual(self.client.get('/nope/contact/').status_code, 404)

    def test_valid_post_sends_mail_to_organizer_and_redirects(self):
        response = self.client.post(self.url, {
            'name': 'Alice', 'email': 'alice@example.com',
            'subject': 'Question', 'message': 'Bonjour',
        })
        self.assertRedirects(response, '/%s/contact/thankyou/' % self.course.uid,
                             fetch_redirect_response=False)
        self.send_mail.assert_called_once()
        kwargs = self.send_mail.call_args[1]
        self.assertEqual(kwargs['to'], ['orga@example.com'])
        self.assertEqual(kwargs['reply_to'], ['alice@example.com'])
        self.assertIn(self.course.uid, kwargs['subject'])
        self.assertIn('Question', kwargs['subject'])
        self.assertIn('Bonjour', kwargs['body'])
        self.assertIn('alice@example.com', kwargs['body'])

    def test_missing_message_shows_form_again(self):
        response = self.client.post(self.url, {'name': 'A', 'email': 'a@example.com', 'message': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contact.html')
        self.send_mail.assert_not_called()

    def test_missing_email_shows_form_again(self):
        response = self.client.post(self.url, {'name': 'A', 'message': 'hello'})
        self.assertEqual(response.status_code, 200)
        self.send_mail.assert_not_called()

    def test_contact_done_page(self):
        response = self.client.get('/%s/contact/thankyou/' % self.course.uid)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contact_done.html')
        self.assertEqual(response.context['course'], self.course)

    def test_contact_done_unknown_course_is_404(self):
        self.assertEqual(self.client.get('/nope/contact/thankyou/').status_code, 404)
