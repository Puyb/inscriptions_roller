"""Extra question form (`custom_admin/extraquestion.js`): which fields are
shown depends on the question type; the course field is set from the cookie."""
import re

from playwright.sync_api import expect

ADD_URL = '/course/inscriptions/extraquestion/add/'


def test_course_field_is_filled_from_cookie(admin_page):
    admin_page.goto(ADD_URL)
    course_id = next(c['value'] for c in admin_page.context.cookies() if c['name'] == 'course_id')
    expect(admin_page.locator('#id_course')).to_have_value(course_id)
    expect(admin_page.locator('#id_course')).to_be_hidden()


def test_text_type_shows_required_only(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.select_option('#id_type', 'text')
    expect(admin_page.locator('.form-row.field-required')).to_be_visible()
    expect(admin_page.locator('.form-row.field-prices')).to_be_hidden()
    expect(admin_page.locator('#choices-group')).to_be_hidden()


def test_radio_and_list_types_show_choices(admin_page):
    admin_page.goto(ADD_URL)
    for type_ in ('radio', 'list'):
        admin_page.select_option('#id_type', type_)
        expect(admin_page.locator('.form-row.field-required')).to_be_visible()
        expect(admin_page.locator('.form-row.field-prices')).to_be_hidden()
        expect(admin_page.locator('#choices-group')).to_be_visible()


def test_checkbox_type_shows_prices_and_hides_required_and_choices(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.select_option('#id_type', 'checkbox')
    expect(admin_page.locator('.form-row.field-required')).to_be_hidden()
    expect(admin_page.locator('.form-row.field-prices')).to_be_visible()
    expect(admin_page.locator('#choices-group')).to_be_hidden()


def test_create_a_radio_question_with_choices(admin_page):
    admin_page.goto(ADD_URL)
    admin_page.select_option('#id_page', 'Equipier')
    admin_page.select_option('#id_type', 'radio')
    admin_page.fill('#id_label', 'Repas e2e')
    admin_page.locator('#choices-group .add-row a').click()
    admin_page.fill('#id_choices-0-label', 'Vegetarien')
    admin_page.fill('#id_choices-0-prices', '0')
    admin_page.click('[name=_save]')
    expect(admin_page).to_have_url(re.compile(r'/course/inscriptions/extraquestion/$'))
    expect(admin_page.locator('#result_list')).to_contain_text('Repas e2e')
