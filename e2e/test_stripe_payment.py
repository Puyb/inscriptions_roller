"""Paiement par carte Stripe (`templates/_stripe.html`, vues `intent_paiement`,
`stripe_webhook`, `equipe_payee`) contre l'API Stripe en mode TEST, avec les cartes de
https://docs.stripe.com/testing.

Les cartes 3D Secure ne sont pas couvertes : Stripe y oppose un hCaptcha au navigateur
automatise.

Necessite un acces reseau (js.stripe.com / api.stripe.com) et les cles de test
`E2E_STRIPE_PUBLIC` / `E2E_STRIPE_SECRET` (fichier `.env`, voir docker-compose.yml) : sans
elles le cours 'e2estripe' n'est pas seme et ces tests sont ignores.

Stripe ne peut pas joindre le serveur e2e : la confirmation (webhook
`payment_intent.succeeded`) est simulee par un POST signe avec le secret d'endpoint du seed.
Chaque test utilise sa propre equipe "Stripe N" (prix 40, soit 40,82 EUR avec les frais).
"""
import hashlib
import hmac
import json
import os
import re
import time

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.skipif(
    not os.environ.get('E2E_STRIPE_PUBLIC'), reason='cles Stripe de test (E2E_STRIPE_*) non definies')

COURSE = 'e2estripe'
ENDPOINT_SECRET = os.environ.get('STRIPE_ENDPOINT_SECRET', 'whsec_e2e_local')

VISA = '4242424242424242'
DECLINED = '4000000000000002'
INSUFFICIENT_FUNDS = '4000000000009995'
INCORRECT_CVC = '4000000000000127'
EXPIRED_CARD = '4000000000000069'


def open_done(page, numero):
    page.goto('/%s/%d/done/' % (COURSE, numero))


def open_card_form(page):
    page.click('#stripe-btn')
    expect(page.locator('#paymentModal')).to_be_visible()
    # les trois champs sont des iframes Stripe Elements
    for selector in ('#card-number', '#card-expiry', '#card-cvc'):
        expect(page.locator(selector + ' iframe[name^="__privateStripeFrame"]')).to_be_visible(timeout=20000)


def fill_card(page, number, expiry='1234', cvc='123'):
    page.frame_locator('#card-number iframe[name^="__privateStripeFrame"]').locator('input[name=cardnumber]').fill(number)
    page.frame_locator('#card-expiry iframe[name^="__privateStripeFrame"]').locator('input[name=exp-date]').fill(expiry)
    page.frame_locator('#card-cvc iframe[name^="__privateStripeFrame"]').locator('input[name=cvc]').fill(cvc)


def pay(page, number, **kwargs):
    open_card_form(page)
    fill_card(page, number, **kwargs)
    page.click('#payment-form button[type=submit]')


def signed_post(page, numero_course_uid, payload, secret=ENDPOINT_SECRET):
    body = json.dumps(payload)
    timestamp = int(time.time())
    signature = hmac.new(secret.encode(), ('%d.%s' % (timestamp, body)).encode(), hashlib.sha256).hexdigest()
    return page.request.post(
        '/%s/stripe/webhook/' % numero_course_uid, data=body,
        headers={'Content-Type': 'application/json',
                 'Stripe-Signature': 't=%d,v1=%s' % (timestamp, signature)})


def intent_event(event_type, intent_id, amount=4082, error=None):
    intent = {'id': intent_id, 'object': 'payment_intent', 'amount': amount, 'currency': 'eur'}
    if error:
        intent['last_payment_error'] = {'message': error}
    return {'id': 'evt_e2e_%d' % time.time_ns(), 'object': 'event',
            'type': event_type, 'data': {'object': intent}}


def test_card_button_shows_amount_with_fees(page):
    open_done(page, 1)
    expect(page.locator('#stripe-btn')).to_contain_text(re.compile(r'40[.,]82'))
    expect(page.get_by_text('de frais seront ajoutés')).to_be_visible()


def test_successful_card_payment_waits_for_webhook_then_marks_team_paid(page):
    open_done(page, 2)
    with page.expect_response(re.compile(r'/%s/intent/stripe/' % COURSE)) as intent_response:
        page.click('#stripe-btn')
    client_secret = intent_response.value.json()['client_secret']
    intent_id = client_secret.split('_secret_')[0]
    assert intent_id.startswith('pi_')

    for selector in ('#card-number', '#card-expiry', '#card-cvc'):
        expect(page.locator(selector + ' iframe[name^="__privateStripeFrame"]')).to_be_visible(timeout=20000)
    fill_card(page, VISA)
    page.click('#payment-form button[type=submit]')

    # Stripe a accepte la carte ; l'inscription attend la confirmation du webhook
    expect(page.locator('#paymentModal2')).to_be_visible(timeout=30000)
    expect(page.locator('#stripe-btn')).to_have_text('Paiement par carte en attente de validation')
    assert page.request.get('/%s/2/payee/' % COURSE).json() == {'success': False}

    response = signed_post(page, COURSE, intent_event('payment_intent.succeeded', intent_id))
    assert response.status == 200

    assert page.request.get('/%s/2/payee/' % COURSE).json() == {'success': True}
    # la page interroge /payee/ toutes les 5 s puis se recharge : plus de bouton de paiement
    expect(page.locator('#stripe-btn')).to_have_count(0, timeout=20000)


@pytest.mark.parametrize('number, message', [
    (DECLINED, r'declin|refus'),
    (INSUFFICIENT_FUNDS, r'insufficient|insuffisant'),
    (INCORRECT_CVC, r'security code|code de s.curit.|cvc'),
    (EXPIRED_CARD, r'expired|expir'),
], ids=['declined', 'insufficient-funds', 'incorrect-cvc', 'expired'])
def test_refused_card_shows_error_and_allows_retry(page, number, message):
    open_done(page, 3)
    pay(page, number)
    error = page.locator('#payment-form .error')
    expect(error).to_have_text(re.compile(message, re.I), timeout=30000)
    expect(error).to_have_class(re.compile('visible'))
    # on reste sur le formulaire de carte, qui redevient utilisable
    expect(page.locator('#paymentModal')).to_be_visible()
    expect(page.locator('#paymentModal2')).not_to_be_visible()
    expect(page.locator('#payment-form')).not_to_have_class(re.compile('submitting'))


def test_card_can_be_retried_after_a_refusal(page):
    open_done(page, 4)
    pay(page, DECLINED)
    expect(page.locator('#payment-form .error')).to_have_text(re.compile('declin|refus', re.I), timeout=30000)
    # Stripe garde le meme PaymentIntent : une carte valide doit passer
    page.frame_locator('#card-number iframe[name^="__privateStripeFrame"]').locator('input[name=cardnumber]').fill(VISA)
    page.click('#payment-form button[type=submit]')
    expect(page.locator('#paymentModal2')).to_be_visible(timeout=30000)


def test_webhook_with_invalid_signature_is_rejected(page):
    response = signed_post(page, COURSE, intent_event('payment_intent.succeeded', 'pi_x'), secret='whsec_wrong')
    assert response.status == 400
    # rien n'a ete enregistre pour autant
    assert page.request.get('/%s/5/payee/' % COURSE).json() == {'success': False}


def test_webhook_payment_failed_leaves_team_unpaid(page):
    open_done(page, 5)
    with page.expect_response(re.compile(r'/%s/intent/stripe/' % COURSE)) as intent_response:
        page.click('#stripe-btn')
    intent_id = intent_response.value.json()['client_secret'].split('_secret_')[0]

    response = signed_post(page, COURSE, intent_event(
        'payment_intent.payment_failed', intent_id, error='Your card was declined.'))
    assert response.status == 200
    assert page.request.get('/%s/5/payee/' % COURSE).json() == {'success': False}
    page.reload()
    expect(page.locator('#stripe-btn')).to_be_visible()

