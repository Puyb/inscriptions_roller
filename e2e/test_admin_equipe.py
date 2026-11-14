"""Team form (`custom_admin/equipe.js` + inline script in
`equipe/change_form.html`): AJAX "autre" block, attachment links, parental
authorisation row hidden for adults, extra answers and the payment block."""
import re

from playwright.sync_api import expect


def open_team(page, name):
    page.goto('/course/inscriptions/equipe/?q=' + name.replace(' ', '+'))
    page.locator('#result_list tbody tr', has_text=name).locator('a').first.click()
    expect(page).to_have_url(re.compile(r'/equipe/\d+/change/'))


def next_row_after_age(page):
    age_row = page.locator('.form-row', has=page.locator('.field-age')).first
    return age_row.locator('xpath=following-sibling::div[contains(@class, "form-row")][1]')


def test_autre_block_is_loaded_by_ajax(admin_page):
    open_team(admin_page, 'Extra 1')
    expect(admin_page.locator('#autre')).to_contain_text('Liens de paiement')
    expect(admin_page.locator('#autre')).to_contain_text('Envoyer un email "e2e"')


def test_extra_answers_are_displayed(admin_page):
    open_team(admin_page, 'Extra 1')
    row = admin_page.locator('.form-row', has_text='Taille t-shirt')
    expect(row).to_contain_text('XL')


def test_payment_block_links_to_payments_and_to_a_new_one(admin_page):
    open_team(admin_page, 'Extra 1')
    expect(admin_page.get_by_text('voir les paiements')).to_have_attribute('href', re.compile(r'paiement/\?equipe_id=\d+$'))
    admin_page.get_by_role('button', name='Ajouter un paiement').click()
    expect(admin_page).to_have_url(re.compile(r'/paiement/add/\?equipe_id=\d+$'))
    # the team is preselected and the amount proposed is its price
    expect(admin_page.locator('#repartition tbody tr', has_text='Extra 1')).to_have_count(1)
    expect(admin_page.locator('#id_montant')).to_have_value(re.compile(r'^40([.,]00)?$'))
    expect(admin_page.locator('#reste')).to_have_text('Reste à répartir : 0')


def test_attachment_is_a_link_or_a_placeholder(admin_page):
    open_team(admin_page, 'Document 1')
    link = admin_page.locator('.field-piece_jointe a[href^="/uploads/"]')
    expect(link.first).to_contain_text('certificat')


def test_adult_hides_the_authorisation_row_minor_keeps_it(admin_page):
    open_team(admin_page, 'Document 2')      # born 1990
    expect(next_row_after_age(admin_page)).to_be_hidden()

    open_team(admin_page, 'Mineur 1')        # 12 years old
    expect(next_row_after_age(admin_page)).to_be_visible()


def test_send_mail_link_opens_the_composer(admin_page):
    admin_page.route('https://tinymce.cachefly.net/**', lambda route: route.fulfill(
        status=200, content_type='application/javascript', body='window.tinymce = { init: function() {} };'))
    open_team(admin_page, 'Extra 1')
    expect(admin_page.locator('#autre select')).to_be_visible()
    admin_page.select_option('#autre select', label='Envoyer un email "e2e"')
    expect(admin_page).to_have_url(re.compile(r'/equipe/\d+/send/\d+/$'))
    expect(admin_page.locator('textarea').first).to_contain_text('Equipe numero')


def test_mail_history_option_navigates_to_the_team_mails(admin_page):
    open_team(admin_page, 'Extra 1')
    expect(admin_page.locator('#autre select')).to_be_visible()
    admin_page.select_option('#autre select', label='Historique des mails envoyés')
    expect(admin_page).to_have_url(re.compile(r'/course/inscriptions/mail/\?equipe=\d+'))
