"""Backoffice payment form (`templates/admin/paiement/add.html`): team search
(AJAX), split of the amount across teams, remaining-amount computation and the
"offert" type. Each test uses its own seeded "Paiement N" teams (see
`setup_e2e_data`): odd N cost 40, even N cost 60."""
import re

from playwright.sync_api import expect

ADD_URL = '/course/inscriptions/paiement/add/'


def search(page, text):
    """Type into the search box key by key: the JS listens to `keyup`
    (which `fill()` does not fire) and sends one AJAX request per key.
    Each response re-renders the results, so wait for all of them before
    interacting with the rows."""
    done = []
    handler = lambda r: done.append(r) if r.url.endswith('/paiement/search/equipe/') else None
    page.on('response', handler)
    try:
        page.fill('#id_search', '')
        page.locator('#id_search').press_sequentially(text)
        deadline = 10000
        while len(done) < len(text) and deadline > 0:
            page.wait_for_timeout(50)
            deadline -= 50
        assert len(done) == len(text), 'missing search responses'
    finally:
        page.remove_listener('response', handler)
    # Let jQuery finish rendering the last response
    page.wait_for_timeout(100)


def add_team(page, name):
    """Search a team by name and click it in the results."""
    search(page, name)
    row = page.locator('#search_results tbody tr', has_text=name)
    expect(row).to_be_visible()
    row.click()


def reste(page):
    return page.locator('#reste')


def test_search_adds_team_and_prefills_amount(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.fill('#id_montant', '40')
    admin_page.locator('#id_montant').dispatch_event('change')
    add_team(admin_page, 'Paiement 1')

    expect(admin_page.locator('#repartition-div')).to_be_visible()
    expect(admin_page.locator('#results-div')).to_be_hidden()
    expect(admin_page.locator('.repartition-montant')).to_have_value('40')
    expect(reste(admin_page)).to_have_text('Reste à répartir : 0')
    expect(admin_page.locator('[name=_save]')).to_be_enabled()


def test_submit_disabled_while_amount_not_fully_split(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.fill('#id_montant', '100')
    admin_page.locator('#id_montant').dispatch_event('change')
    add_team(admin_page, 'Paiement 3')

    # 100 paid but team 3 only owes 40
    expect(admin_page.locator('.repartition-montant')).to_have_value('40')
    expect(reste(admin_page)).to_have_text('Reste à répartir : 60')
    expect(admin_page.locator('[name=_save]')).to_be_disabled()


def test_split_payment_over_two_teams_then_remove_one(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.fill('#id_montant', '100')
    admin_page.locator('#id_montant').dispatch_event('change')
    add_team(admin_page, 'Paiement 5')   # 40
    add_team(admin_page, 'Paiement 6')   # 60 (remaining)

    montants = admin_page.locator('.repartition-montant')
    expect(montants).to_have_count(2)
    expect(montants.nth(0)).to_have_value('40')
    expect(montants.nth(1)).to_have_value('60')
    expect(reste(admin_page)).to_have_text('Reste à répartir : 0')

    admin_page.locator('#repartition tbody tr', has_text='Paiement 6').locator('button').click()
    expect(montants).to_have_count(1)
    expect(reste(admin_page)).to_have_text('Reste à répartir : 60')
    expect(admin_page.locator('[name=_save]')).to_be_disabled()


def test_already_selected_team_is_not_offered_again(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.fill('#id_montant', '40')
    admin_page.locator('#id_montant').dispatch_event('change')
    add_team(admin_page, 'Paiement 7')

    search(admin_page, 'Paiement 7')
    expect(admin_page.locator('#results-div')).to_be_visible()
    # empty <tr> accumulate (one batch per keystroke): only count filled rows
    expect(admin_page.locator('#search_results tbody tr', has_text='Paiement 7')).to_have_count(0)


def test_clearing_search_returns_to_repartition(admin_page):
    admin_page.goto(ADD_URL)
    search(admin_page, 'Paiement')
    expect(admin_page.locator('#results-div')).to_be_visible()
    admin_page.fill('#id_search', '')
    admin_page.locator('#id_search').dispatch_event('keyup')
    expect(admin_page.locator('#repartition-div')).to_be_visible()
    expect(admin_page.locator('#results-div')).to_be_hidden()


def test_offert_makes_amounts_readonly_and_zero(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.fill('#id_montant', '40')
    admin_page.locator('#id_montant').dispatch_event('change')
    add_team(admin_page, 'Paiement 2')

    admin_page.check('input[name=type][value=offert]')
    expect(admin_page.locator('#id_montant')).to_have_value('')
    expect(admin_page.locator('#id_montant')).to_have_attribute('readonly', re.compile('.*'))
    expect(admin_page.locator('.repartition-montant')).to_have_value('0')
    expect(admin_page.locator('.repartition-montant')).to_have_attribute('readonly', re.compile('.*'))
    expect(reste(admin_page)).to_have_text('Reste à répartir : 0')


def test_save_payment_redirects_to_list_and_shows_in_team(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.check('input[name=type][value=espèce]')
    admin_page.fill('#id_montant', '40')
    admin_page.locator('#id_montant').dispatch_event('change')
    add_team(admin_page, 'Paiement 4')   # price 60: 40 paid, 20 left
    admin_page.click('[name=_save]')

    expect(admin_page).to_have_url(re.compile(r'/course/inscriptions/paiement/$'))
    expect(admin_page.locator('#result_list')).to_contain_text('Paiement 4')


def open_seeded_payment(page):
    """Open the payment seeded on team "Paiement 8" (20 EUR) from the list."""
    page.goto('/course/inscriptions/paiement/')
    page.locator('#result_list tbody tr', has_text='Paiement 8').locator('a').first.click()
    expect(page).to_have_url(re.compile(r'/paiement/\d+/change/$'))


def test_edit_existing_payment_shows_its_repartition(admin_page):
    open_seeded_payment(admin_page)
    expect(admin_page.locator('#id_montant')).to_have_value(re.compile(r'^20[.,]00$'))
    expect(admin_page.locator('.repartition-montant')).to_have_value(re.compile(r'^20[.,]00$'))
    expect(reste(admin_page)).to_have_text('Reste à répartir : 0')


def test_search_while_editing_counts_this_payments_share(admin_page):
    """The payment id must reach the search endpoint so the amount already
    split by *this* payment is not counted as "already paid"."""
    open_seeded_payment(admin_page)
    paiement_id = re.search(r'/paiement/(\d+)/change/', admin_page.url).group(1)
    res = admin_page.request.post('/course/inscriptions/paiement/search/equipe/',
                                  form=dict(search='Paiement 8', id=paiement_id))
    equipe = [e for e in res.json()['equipes'] if e['nom'] == 'Paiement 8'][0]
    assert equipe['paiement'] == '20.00'
    assert equipe['montant'] == '20.00'
