"""Course form: increase-date editor (inline script in
`course/change_form.html`) and the Stripe webhook helper
(`custom_admin/course.js`, which calls api.stripe.com straight from the
browser: mocked here with `page.route`)."""
import json
import re

from playwright.sync_api import expect

COURSE_URL = '/course/inscriptions/edition/'
COURSE_SETTINGS_URL = '/course/inscriptions/course/'
CORS = {
    'access-control-allow-origin': '*',
    'access-control-allow-headers': '*',
    'access-control-allow-methods': '*',
}


def dates(page):
    return page.locator('#dates_augmentation_table input')


def hidden_dates(page):
    return page.locator('input[name=dates_augmentation]')


def stripe_mock(page, webhooks=(), secret='whsec_e2e'):
    """Mock api.stripe.com; returns the list of recorded (method, url)."""
    calls = []

    def handler(route, request):
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        calls.append((request.method, request.url))
        if request.method == 'GET':
            body = {'data': list(webhooks)}
        elif request.method == 'DELETE':
            body = {'deleted': True}
        else:
            body = {'secret': secret}
        route.fulfill(status=200, headers=CORS, content_type='application/json', body=json.dumps(body))

    page.route('https://api.stripe.com/**', handler)
    return calls


def set_stripe_keys(page, secret, public):
    page.fill('#id_stripe_secret', secret)
    page.locator('#id_stripe_secret').dispatch_event('change')
    page.fill('#id_stripe_public', public)
    page.locator('#id_stripe_public').dispatch_event('change')


# --- increase dates -------------------------------------------------------

def test_existing_increase_date_is_listed_and_hidden_field_is_replaced(admin_page):
    admin_page.goto(COURSE_URL)
    expect(dates(admin_page)).to_have_count(1)
    expect(hidden_dates(admin_page)).to_be_hidden()
    expect(admin_page.get_by_text("Ajouter une date d'augmentation")).to_be_visible()


def test_added_dates_are_normalised_to_iso_and_sorted(admin_page):
    admin_page.goto(COURSE_URL)
    admin_page.get_by_text("Ajouter une date d'augmentation").click()
    admin_page.get_by_text("Ajouter une date d'augmentation").click()
    expect(dates(admin_page)).to_have_count(3)
    dates(admin_page).nth(1).fill('05/01/2099')    # dd/mm/yyyy -> ISO
    dates(admin_page).nth(1).blur()
    dates(admin_page).nth(2).fill('2098-02-01')    # ISO kept; sorted before
    dates(admin_page).nth(2).blur()
    value = hidden_dates(admin_page).input_value()
    parts = value.split(',')
    assert parts[-2:] == ['2098-02-01', '2099-01-05'], value
    assert parts == sorted(parts)


def test_invalid_date_is_ignored_and_remove_button_drops_the_row(admin_page):
    admin_page.goto(COURSE_URL)
    before = hidden_dates(admin_page).input_value()
    admin_page.get_by_text("Ajouter une date d'augmentation").click()
    dates(admin_page).nth(1).fill('pas une date')
    dates(admin_page).nth(1).blur()
    expect(hidden_dates(admin_page)).to_have_value(before)

    dates(admin_page).nth(1).fill('2099-03-03')
    dates(admin_page).nth(1).blur()
    expect(hidden_dates(admin_page)).to_have_value(before + ',2099-03-03')
    admin_page.locator('#dates_augmentation_table tr').nth(1).locator('.deletelink').click()
    expect(dates(admin_page)).to_have_count(1)
    expect(hidden_dates(admin_page)).to_have_value(before)


def test_increase_dates_are_saved_and_reloaded(admin_page):
    admin_page.goto(COURSE_URL)
    original = hidden_dates(admin_page).input_value()
    admin_page.get_by_text("Ajouter une date d'augmentation").click()
    dates(admin_page).nth(1).fill('2099-04-04')
    dates(admin_page).nth(1).blur()
    admin_page.click('[name=_save]')
    expect(admin_page.locator('.errornote')).to_have_count(0)

    admin_page.goto(COURSE_URL)
    expect(dates(admin_page)).to_have_count(2)
    expect(hidden_dates(admin_page)).to_have_value(original + ',2099-04-04')

    # restore
    admin_page.locator('#dates_augmentation_table tr').nth(1).locator('.deletelink').click()
    admin_page.click('[name=_save]')
    admin_page.goto(COURSE_URL)
    expect(hidden_dates(admin_page)).to_have_value(original)


# --- stripe webhook helper ------------------------------------------------

def test_stripe_no_keys_shows_nothing(admin_page):
    calls = stripe_mock(admin_page)
    admin_page.goto(COURSE_SETTINGS_URL)
    expect(admin_page.locator('#stripe')).to_have_text('')
    assert calls == []


def test_stripe_rejects_malformed_secret_key_without_calling_stripe(admin_page):
    calls = stripe_mock(admin_page)
    admin_page.on('dialog', lambda d: d.dismiss())
    admin_page.goto(COURSE_SETTINGS_URL)
    admin_page.fill('#id_stripe_secret', 'abc')
    admin_page.locator('#id_stripe_secret').dispatch_event('change')
    expect(admin_page.locator('#stripe')).to_contain_text('commence par sk_live_ ou sk_test_')
    assert calls == []


def test_stripe_requires_public_key(admin_page):
    stripe_mock(admin_page)
    admin_page.on('dialog', lambda d: d.dismiss())
    admin_page.goto(COURSE_SETTINGS_URL)
    set_stripe_keys(admin_page, 'sk_test_abc', '')
    expect(admin_page.locator('#stripe')).to_contain_text('clef public Stripe doit être entrée')


def test_stripe_missing_webhook_can_be_installed_with_button(admin_page):
    calls = stripe_mock(admin_page, webhooks=[])
    admin_page.on('dialog', lambda d: d.dismiss())
    admin_page.goto(COURSE_SETTINGS_URL)
    set_stripe_keys(admin_page, 'sk_test_abc', 'pk_test_abc')
    expect(admin_page.locator('#stripe')).to_contain_text("n'est pas installé")
    expect(admin_page.locator('#stripe')).to_contain_text('(mode test)')

    admin_page.locator('#stripe button', has_text='Installer').click()
    expect(admin_page.locator('#stripe')).to_contain_text('correctement installé')
    expect(admin_page.locator('#id_stripe_endpoint_secret')).to_have_value('whsec_e2e')
    assert ('POST', 'https://api.stripe.com/v1/webhook_endpoints') in calls


def test_stripe_confirm_dialog_installs_automatically(admin_page):
    stripe_mock(admin_page, webhooks=[])
    messages = []
    admin_page.on('dialog', lambda d: (messages.append(d.message), d.accept()))
    admin_page.goto(COURSE_SETTINGS_URL)
    set_stripe_keys(admin_page, 'sk_test_abc', 'pk_test_abc')
    expect(admin_page.locator('#id_stripe_endpoint_secret')).to_have_value('whsec_e2e')
    assert any('configurer le webhook' in m for m in messages)


def test_stripe_existing_webhook_without_secret_offers_reinstall(admin_page):
    admin_page.goto(COURSE_SETTINGS_URL)
    url = '%s/e2e/e2e/stripe/webhook/' % re.match(r'(https?://[^/]+)', admin_page.url).group(1)
    calls = stripe_mock(admin_page, webhooks=[{'id': 'we_123', 'url': url}], secret='whsec_new')
    admin_page.on('dialog', lambda d: d.dismiss())
    admin_page.fill('#id_stripe_endpoint_secret', '')
    set_stripe_keys(admin_page, 'sk_test_abc', 'pk_test_abc')
    expect(admin_page.locator('#stripe')).to_contain_text('sa clef de sécurité ne l')

    admin_page.locator('#stripe button', has_text='Réinstaller').click()
    expect(admin_page.locator('#id_stripe_endpoint_secret')).to_have_value('whsec_new')
    assert ('DELETE', 'https://api.stripe.com/v1/webhook_endpoints/we_123') in calls


def test_stripe_existing_webhook_with_secret_is_reported_installed(admin_page):
    admin_page.goto(COURSE_SETTINGS_URL)
    url = '%s/e2e/e2e/stripe/webhook/' % re.match(r'(https?://[^/]+)', admin_page.url).group(1)
    stripe_mock(admin_page, webhooks=[{'id': 'we_123', 'url': url}])
    admin_page.on('dialog', lambda d: d.dismiss())
    admin_page.fill('#id_stripe_endpoint_secret', 'whsec_already')
    set_stripe_keys(admin_page, 'sk_live_abc', 'pk_live_abc')
    expect(admin_page.locator('#stripe')).to_have_text('Le webhook stripe est correctement installé.')
