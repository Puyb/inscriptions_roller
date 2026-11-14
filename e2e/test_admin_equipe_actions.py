"""Team list bulk actions that land on JS-enhanced pages: grouped mail
(`equipe/send_mails.html`, AJAX preview) and export (`equipe/export.html`,
column list depends on the exported object)."""
import re

from playwright.sync_api import expect


def run_action(page, action, names):
    page.goto('/course/inscriptions/equipe/?q=Paiement')
    for name in names:
        page.locator('#result_list tbody tr', has_text=name).locator('input.action-select').check()
    page.select_option('select[name=action]', action)
    page.locator('.actions button[type=submit], .actions input[type=submit]').first.click()


# --- grouped mail ---------------------------------------------------------

def choose_preview(page, index):
    value = page.locator('select[name=preview] option').nth(index).get_attribute('value')
    page.select_option('select[name=preview]', value)


def test_mail_preview_renders_the_template_for_the_chosen_team(admin_page):
    run_action(admin_page, 'send_mails', ['Paiement 1', 'Paiement 2'])
    expect(admin_page.locator('h1', has_text='Envoyer un mail à 2 equipes')).to_be_visible()
    expect(admin_page.locator('select[name=template] option')).to_have_text(['e2e'])

    choose_preview(admin_page, 0)
    admin_page.click('#preview_button')
    first = admin_page.locator('#preview h1')
    expect(first).to_contain_text('Bonjour Paiement')
    expect(admin_page.locator('#preview h2')).to_contain_text('@example.com')
    expect(admin_page.locator('#preview div')).to_contain_text('Equipe numero')

    before = first.inner_text()
    choose_preview(admin_page, 1)
    admin_page.click('#preview_button')
    expect(first).not_to_have_text(before)


def test_sending_a_grouped_mail_confirms_and_returns_to_the_list(admin_page):
    run_action(admin_page, 'send_mails', ['Paiement 3', 'Paiement 4'])
    admin_page.get_by_role('button', name=re.compile('Envoyer à 2')).click()
    expect(admin_page).to_have_url(re.compile(r'/course/inscriptions/equipe/$'))
    expect(admin_page.locator('.messagelist')).to_contain_text('Message envoyé à 2 équipes')


# --- export ---------------------------------------------------------------

def test_equipier_columns_are_hidden_unless_exporting_equipiers(admin_page):
    run_action(admin_page, 'export', ['Paiement 5'])
    equipier_cols = admin_page.locator('input[name=colonnes][value^="equipier."]')
    assert equipier_cols.count() > 0
    expect(equipier_cols.first).to_be_hidden()
    expect(admin_page.locator('input[name=colonnes][value^="equipe."]').first).to_be_visible()

    admin_page.select_option('#id_objet', 'equipiers')
    expect(equipier_cols.first).to_be_visible()
    admin_page.select_option('#id_objet', 'equipes')
    expect(equipier_cols.first).to_be_hidden()


def test_all_columns_checkbox_checks_everything_and_export_downloads_csv(admin_page):
    run_action(admin_page, 'export', ['Paiement 6'])
    admin_page.get_by_label('Toutes les colonnes').check()
    expect(admin_page.locator('input[name=colonnes]:not(:checked)')).to_have_count(0)

    with admin_page.expect_download() as download:
        admin_page.click('[name=_save]')
    path = download.value.path()
    content = open(path, encoding='utf-8', errors='replace').read()
    assert 'Paiement 6' in content
    assert 'Paiement 5' not in content
