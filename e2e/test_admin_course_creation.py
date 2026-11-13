"""Course creation form (`admin_create_course.js`): course models loaded from
`../models/`, price table generated per category and per price step, and the
whole chain down to the prices stored on the new course's categories."""
import re

from playwright.sync_api import expect

ADD_URL = '/course/inscriptions/course/add/'


def fill_course(page, uid='e2enew'):
    page.fill('#id_nom', 'Course creee par e2e')
    page.fill('#id_uid', uid)
    page.fill('#id_organisateur', 'Club E2E')
    page.fill('#id_ville', 'Paris')
    page.fill('#id_date', '01/06/2099')
    page.fill('#id_url', 'http://example.com')
    page.fill('#id_url_reglement', 'http://example.com/reglement')
    page.fill('#id_email_contact', 'orga@example.com')
    page.fill('#id_date_ouverture', '01/01/2099')
    page.fill('#id_date_fermeture', '30/05/2099')
    page.fill('#id_limite_participants', '300')
    page.fill('#id_ordre', 'Club E2E')
    page.fill('#id_delai_paiement', '10')


def models(page):
    return page.locator('[name=course_model]')


def test_models_are_loaded_and_include_own_courses(admin_page):
    admin_page.goto(ADD_URL)
    values = [m.get_attribute('value') for m in models(admin_page).all()]
    assert {'paris', 'grol', 'centre'} <= set(values)
    # the organizer's own course can be cloned: its id is a numeric value
    assert any(v.isdigit() for v in values), values
    expect(admin_page.get_by_text('Course E2E')).to_be_visible()


def test_no_price_table_until_a_model_is_chosen(admin_page):
    admin_page.goto(ADD_URL)
    fill_course(admin_page)
    expect(models(admin_page).first).to_be_visible()
    expect(admin_page.locator('.form-prices input')).to_have_count(0)


def test_choosing_a_model_builds_one_row_per_category(admin_page):
    admin_page.goto(ADD_URL)
    fill_course(admin_page)
    admin_page.check('[name=course_model][value=paris]')
    rows = admin_page.locator('.form-prices tr', has=admin_page.locator('th', has_text=re.compile('^IDH$')))
    expect(rows).to_have_count(1)
    # no increase date: one step => base + per-equipier inputs only
    expect(rows.locator('input')).to_have_count(2)
    expect(rows.locator('input[name=IDH__prices_base__0]')).to_have_value('40.00')
    prix = admin_page.locator('[name=course_prix]').input_value()
    assert '"IDH"' in prix and '"prices_base":[40' in prix.replace(' ', '').replace('"40', '40').replace('.00"', '')


def test_adding_an_increase_date_adds_a_price_step(admin_page):
    admin_page.goto(ADD_URL)
    fill_course(admin_page)
    admin_page.check('[name=course_model][value=paris]')
    admin_page.get_by_text("Ajouter une date d'augmentation").click()
    admin_page.locator('#dates_augmentation_table input').first.fill('01/04/2099')
    admin_page.locator('#dates_augmentation_table input').first.blur()
    row = admin_page.locator('.form-prices tr', has=admin_page.locator('th', has_text=re.compile('^IDH$')))
    expect(row.locator('input')).to_have_count(4)
    # model price of the second step (50) is proposed
    expect(row.locator('input[name=IDH__prices_base__1]')).to_have_value(re.compile(r'^50(\.00)?$'))


def test_create_course_end_to_end_with_edited_price(admin_page):
    admin_page.goto(ADD_URL)
    fill_course(admin_page)
    admin_page.check('[name=course_model][value=paris]')
    admin_page.fill('input[name=IDH__prices_base__0]', '44')
    admin_page.locator('input[name=IDH__prices_base__0]').blur()
    admin_page.click('[name=_save]')

    expect(admin_page).to_have_url(re.compile(r'/course/$'))
    cookies = {c['name']: c['value'] for c in admin_page.context.cookies()}
    assert cookies['course_uid'] == 'e2enew'

    admin_page.goto('/course/inscriptions/categorie/')
    admin_page.locator('#result_list tbody tr', has_text='IDH').locator('a').first.click()
    expect(admin_page.locator('input[name=prices_base__0]')).to_have_value(re.compile(r'^44(\.00)?$'))
