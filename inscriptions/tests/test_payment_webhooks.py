import json
from decimal import Decimal
from unittest import mock

import stripe

from inscriptions.factories import CourseFactory, EquipeFactory
from inscriptions.models import Paiement
from inscriptions.tests.base import BaseTestCase


class FakeStripeEvent:
    def __init__(self, event_type, obj):
        self._d = {'type': event_type, 'data': {'object': obj}}

    def to_dict(self):
        return self._d


class StripeWebhookTestCase(BaseTestCase):
    """`views.stripe_webhook` never talks to the real Stripe API in tests:
    `stripe.Webhook.construct_event` (signature verification) is mocked, the
    rest (finding the Paiement, updating it, sending mail through the real
    Redis-backed channel layer) runs for real."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(stripe_secret='sk_test_xxx', stripe_endpoint_secret='whsec_xxx')
        self.equipe = EquipeFactory(course=self.course, prix=Decimal('70.00'))
        self.paiement = Paiement.objects.create(type='stripe', montant=None, intent_id='pi_123')
        self.paiement.equipes.create(equipe=self.equipe, montant=Decimal('70.00'))

    def _post(self, event):
        with mock.patch('stripe.Webhook.construct_event', return_value=event):
            return self.client.post(
                '/%s/stripe/webhook/' % self.course.uid,
                data='{}', content_type='application/json',
                HTTP_STRIPE_SIGNATURE='irrelevant-because-mocked',
            )

    def test_invalid_signature_is_rejected(self):
        with mock.patch('stripe.Webhook.construct_event', side_effect=stripe.error.SignatureVerificationError('bad sig', 'sig_header')):
            response = self.client.post(
                '/%s/stripe/webhook/' % self.course.uid,
                data='{}', content_type='application/json',
                HTTP_STRIPE_SIGNATURE='wrong',
            )
        self.assertEqual(response.status_code, 400)
        self.paiement.refresh_from_db()
        self.assertIsNone(self.paiement.montant)

    def test_payment_succeeded_records_the_amount(self):
        event = FakeStripeEvent('payment_intent.succeeded', {'id': 'pi_123', 'amount': 7000})
        response = self._post(event)
        self.assertEqual(response.status_code, 200)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('70.00'))

    def test_payment_failed_records_the_error_without_setting_an_amount(self):
        event = FakeStripeEvent('payment_intent.payment_failed', {
            'id': 'pi_123', 'last_payment_error': {'message': 'Card declined'},
        })
        response = self._post(event)
        self.assertEqual(response.status_code, 200)
        self.paiement.refresh_from_db()
        self.assertIsNone(self.paiement.montant)
        self.assertIn('Card declined', self.paiement.detail)

    def test_unknown_intent_id_does_not_crash(self):
        event = FakeStripeEvent('payment_intent.succeeded', {'id': 'pi_does_not_exist', 'amount': 100})
        response = self._post(event)
        self.assertEqual(response.status_code, 200)


class HelloAssoWebhookTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(helloasso_organisation='org', helloasso_id='id', helloasso_secret='secret')
        self.equipe = EquipeFactory(course=self.course, prix=Decimal('55.00'))
        self.paiement = Paiement.objects.create(type='helloasso', montant=None, intent_id='order-uuid-1', detail='')
        self.paiement.equipes.create(equipe=self.equipe, montant=Decimal('55.00'))

    def _post(self, body):
        return self.client.post(
            '/%s/helloasso/webhook/' % self.course.uid,
            data=json.dumps(body), content_type='application/json',
        )

    def test_authorized_payment_records_the_amount(self):
        response = self._post({
            'eventType': 'Order',
            'metadata': {'uuid': 'order-uuid-1'},
            'data': {'payments': [{'state': 'Authorized', 'amount': 5500, 'paymentReceiptUrl': 'http://x'}]},
        })
        self.assertEqual(response.status_code, 200)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('55.00'))

    def test_non_authorized_payment_does_not_set_an_amount(self):
        response = self._post({
            'eventType': 'Order',
            'metadata': {'uuid': 'order-uuid-1'},
            'data': {'payments': [{'state': 'Refused', 'amount': 5500, 'paymentReceiptUrl': 'http://x'}]},
        })
        self.assertEqual(response.status_code, 200)
        self.paiement.refresh_from_db()
        self.assertIsNone(self.paiement.montant)

    def test_missing_metadata_is_ignored(self):
        response = self._post({'eventType': 'Order', 'data': {}})
        self.assertEqual(response.status_code, 200)


class PaypalIpnTestCase(BaseTestCase):
    """`confirm_ipn_data` performs the real PayPal IPN round-trip HTTP call -
    it's mocked here so the test never touches the network."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(paypal='organisateur@example.com', frais_paypal_inclus=True)
        self.equipe = EquipeFactory(course=self.course, prix=Decimal('70.00'))

    def _post(self, **overrides):
        data = {
            'payment_status': 'Completed',
            'invoice': '%sXXXX' % self.equipe.id,
            'mc_gross': '70.00',
        }
        data.update(overrides)
        with mock.patch('inscriptions.views.confirm_ipn_data', return_value=True):
            return self.client.post('/%s/ipn/' % self.course.uid, data)

    def test_completed_payment_creates_a_paiement(self):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        paiement = Paiement.objects.get(type='paypal')
        self.assertEqual(paiement.montant, Decimal('70.00'))
        self.assertEqual(paiement.equipes.get().equipe, self.equipe)

    def test_non_completed_status_is_ignored(self):
        self._post(payment_status='Pending')
        self.assertFalse(Paiement.objects.filter(type='paypal').exists())

    def test_rejected_ipn_signature_is_ignored(self):
        with mock.patch('inscriptions.views.confirm_ipn_data', return_value=False):
            self.client.post('/%s/ipn/' % self.course.uid, {
                'payment_status': 'Completed',
                'invoice': '%sXXXX' % self.equipe.id,
                'mc_gross': '70.00',
            })
        self.assertFalse(Paiement.objects.filter(type='paypal').exists())
